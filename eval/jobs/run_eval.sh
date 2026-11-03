#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=3:00:00
#SBATCH --job-name=gradeai-eval
#SBATCH --output=/home/%u/%x-%j.log
#
# Evaluate the base model and the fine-tuned LoRA on the test set, and compare them.
# Everything runs inside this one job:
#   1. check the repo, test set, packages, model, adapter and output folder (no GPU needed);
#   2. start vLLM with the base model, plus the adapter if there is one;
#   3. run the base model, then the fine-tuned model, with the same options;
#   4. compare the two runs (this checks that both got identical prompts and decoding settings);
#   5. shut vLLM down, also when a step fails.
# If the job stops early (time limit, failure), submit it again: it starts fresh in a new folder.
# Uses the same SLURM settings, modules and environment as jobs/serve_model.sh and
# jobs/generate_data.sh.
#
# Submit from the repo folder on Fir:
#   ADAPTER=models/adapters/<name> sbatch eval/jobs/run_eval.sh
#   ADAPTER=models/adapters/<name> sbatch eval/jobs/run_eval.sh -- --test-type paraphrase,sensitivity
#   sbatch eval/jobs/run_eval.sh          # no ADAPTER: base model only, no comparison
# Check the setup without a GPU, on a login node:
#   ADAPTER=models/adapters/<name> bash eval/jobs/run_eval.sh --check
#
# Options after -- go to both runs: --test-type, --topic, --question-id, --temperature, --top-p,
# --max-tokens, --seed, --n-boot, --boot-seed. The job sets everything else itself.
#
# Settings (put them before sbatch):
#   ADAPTER     the fine-tuned LoRA folder, from training/train_lora.py. Optional. The job never
#               assumes a grading-skills adapter exists: it checks the folder, and the adapter's
#               training data is printed so you can confirm it.
#   BASE_MODEL  base model folder (default models/Qwen3.8-27B, as in jobs/serve_model.sh)
#   EVAL_OUT    where results go (default ~/scratch/gradeai-eval). Must be outside the repo: the
#               outputs contain test-set text. Each job writes EVAL_OUT/<job id>/.
#   PORT        vLLM port (default 8000 + job ID % 1000, as in jobs/generate_data.sh)
#   VENV        Python environment (default env/model/.venv)
#   HEALTH_TIMEOUT, HEALTH_INTERVAL  whole seconds to wait for vLLM, and between checks (default 2700, 10)
#   STOP_TIMEOUT  seconds to wait for vLLM to stop before killing it (default 20)
# To change the time limit:  sbatch --time=6:00:00 eval/jobs/run_eval.sh ...
#
# Progress:  tail -f ~/gradeai-eval-<jobid>.log      (this script)
#            tail -f <EVAL_OUT>/<jobid>/vllm.log      (the model server)

set -eo pipefail

CHECK_ONLY=0
if [ "${1:-}" = "--check" ]; then
    CHECK_ONLY=1
    shift
fi
if [ "${1:-}" = "--" ]; then
    shift
fi
EVAL_ARGS=("$@")

# Under sbatch the script runs from a copy, so the repo is the folder the job was submitted from.
REPO="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$REPO"

BASE_MODEL="${BASE_MODEL:-models/Qwen3.8-27B}"
ADAPTER="${ADAPTER:-}"
EVAL_OUT="${EVAL_OUT:-$HOME/scratch/gradeai-eval}"
VENV="${VENV:-env/model/.venv}"
JOB_TAG="${SLURM_JOB_ID:-local-$(date +%Y%m%d-%H%M%S)}"
PORT="${PORT:-$((8000 + ${SLURM_JOB_ID:-0} % 1000))}"
ENDPOINT="http://127.0.0.1:$PORT/v1"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-2700}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-10}"
STOP_TIMEOUT="${STOP_TIMEOUT:-20}"
VLLM_PID=""

echo "GradeAI evaluation, job $JOB_TAG on $(hostname), started $(date)"
echo "Base model: $BASE_MODEL   Adapter: ${ADAPTER:-none}   Output: $EVAL_OUT"
[ ${#EVAL_ARGS[@]} -gt 0 ] && echo "Options for both runs: ${EVAL_ARGS[*]}"

# ---- Environment (the same modules as jobs/serve_model.sh) ----------------------------------
if type module >/dev/null 2>&1; then
    module load opencv/4.13 python/3.13 cuda/13.2
else
    echo "Note: no 'module' command here; using the current environment."
fi
if [ ! -f "$VENV/bin/activate" ]; then
    echo "ERROR: no Python environment at $VENV (see env/README.md)."
    exit 1
fi
source "$VENV/bin/activate"

# ---- Checks that need no GPU ------------------------------------------------------------------
if ! PREFLIGHT="$(python -m eval.jobs.preflight --base-model "$BASE_MODEL" --adapter "$ADAPTER" \
    --out "$EVAL_OUT" -- "${EVAL_ARGS[@]}")"; then
    exit 1
fi
eval "$PREFLIGHT"
RUN_ROOT="$OUT/$JOB_TAG"
if [ -e "$RUN_ROOT" ]; then
    echo "ERROR: $RUN_ROOT already exists; results are never overwritten."
    exit 1
fi
[ -n "$ADAPTER_DATA" ] && echo "Adapter training data: $ADAPTER_DATA"
if [ "$CHECK_ONLY" = 1 ]; then
    echo "Checks passed ($MODE). Results would go to $RUN_ROOT."
    exit 0
fi

# Collect the bootstrap options for the compare step (only --n-boot and --boot-seed apply).
COMPARE_ARGS=()
i=0
while [ $i -lt ${#EVAL_ARGS[@]} ]; do
    case "${EVAL_ARGS[$i]}" in
    --n-boot | --boot-seed) COMPARE_ARGS+=("${EVAL_ARGS[$i]}" "${EVAL_ARGS[$((i + 1))]}"); i=$((i + 1)) ;;
    --n-boot=* | --boot-seed=*) COMPARE_ARGS+=("${EVAL_ARGS[$i]}") ;;
    esac
    i=$((i + 1))
done

# ---- Stop vLLM however the job ends ------------------------------------------------------
stop_vllm() {
    if [ -n "$VLLM_PID" ] && kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "Stopping vLLM (pid $VLLM_PID)"
        pkill -TERM -P "$VLLM_PID" 2>/dev/null || true
        kill -TERM "$VLLM_PID" 2>/dev/null || true
        for _ in $(seq 1 "$STOP_TIMEOUT"); do
            kill -0 "$VLLM_PID" 2>/dev/null || break
            sleep 1
        done
        if kill -0 "$VLLM_PID" 2>/dev/null; then
            echo "vLLM did not stop after ${STOP_TIMEOUT}s; killing it"
            pkill -KILL -P "$VLLM_PID" 2>/dev/null || true
            kill -KILL "$VLLM_PID" 2>/dev/null || true
        fi
    fi
}
finish() {
    status=$?
    stop_vllm
    if [ "$status" -ne 0 ]; then
        echo "FAILED (exit $status) at $(date). What was saved is in $RUN_ROOT."
        echo "Submit the job again to start a fresh evaluation."
    fi
}
trap finish EXIT
# SLURM sends SIGTERM at the time limit; exiting runs the EXIT trap, which stops vLLM.
trap 'echo "Received a stop signal"; exit 143' TERM INT

mkdir -p "$RUN_ROOT"
echo "Results: $RUN_ROOT"

# ---- GPU ---------------------------------------------------------------------------------
# Catch bad nodes before waiting for vLLM (nvidia-smi can look fine when CUDA doesn't work).
nvidia-smi -L
if ! python -c "import torch, sys; ok = torch.cuda.is_available(); print('CUDA OK:', ok, torch.cuda.get_device_name(0) if ok else ''); sys.exit(0 if ok else 1)"; then
    echo "ERROR: CUDA doesn't work on node $(hostname). Resubmit with --exclude=$(hostname)."
    exit 1
fi

# ---- Start vLLM ---------------------------------------------------------------------------
LORA_ARGS=()
WANTED="$BASE_NAME"
if [ "$MODE" = "base_and_fine_tuned" ]; then
    LORA_ARGS=(--enable-lora --lora-modules "$FT_NAME=$ADAPTER_PATH" --max-lora-rank "$LORA_RANK")
    WANTED="$BASE_NAME $FT_NAME"
fi
# Only reachable from this node: student answers stay inside the job.
vllm serve "$BASE_MODEL_PATH" \
    --served-model-name "$BASE_NAME" \
    --max-model-len 32768 --max-num-seqs 256 \
    --host 127.0.0.1 --port "$PORT" \
    "${LORA_ARGS[@]}" \
    >"$RUN_ROOT/vllm.log" 2>&1 &
VLLM_PID=$!

echo "Waiting for vLLM to load on port $PORT (log: $RUN_ROOT/vllm.log)..."
waited=0
until curl -sf "$ENDPOINT/models" >"$RUN_ROOT/served_models.json" 2>/dev/null; do
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "ERROR: vLLM stopped while loading. Last lines of its log:"
        tail -n 30 "$RUN_ROOT/vllm.log"
        exit 1
    fi
    if [ "$waited" -ge "$HEALTH_TIMEOUT" ]; then
        echo "ERROR: vLLM was not ready after ${HEALTH_TIMEOUT}s. Last lines of its log:"
        tail -n 30 "$RUN_ROOT/vllm.log"
        exit 1
    fi
    sleep "$HEALTH_INTERVAL"
    waited=$((waited + HEALTH_INTERVAL))
done
echo "vLLM ready after about ${waited}s"
python - "$RUN_ROOT/served_models.json" $WANTED <<'PY'
import json, sys
served = {m["id"] for m in json.load(open(sys.argv[1]))["data"]}
missing = [name for name in sys.argv[2:] if name not in served]
if missing:
    sys.exit(f"ERROR: vLLM is not serving {missing}; it serves {sorted(served)}")
print("Serving:", ", ".join(sorted(served)))
PY

# ---- Evaluate -----------------------------------------------------------------------------
only_run() {
    # The one run folder a run_eval.py call made under $1.
    found=("$1"/*_*)
    if [ ${#found[@]} -ne 1 ] || [ ! -f "${found[0]}/config.json" ]; then
        echo "ERROR: expected exactly one run folder in $1" >&2
        return 1
    fi
    echo "${found[0]}"
}

echo "Base model run, started $(date)"
python -u eval/run_eval.py --model base --out "$RUN_ROOT/base" \
    --endpoint "$ENDPOINT" --base-model "$BASE_MODEL_RECORD" "${EVAL_ARGS[@]}"
BASE_RUN="$(only_run "$RUN_ROOT/base")"

if [ "$MODE" = "base_only" ]; then
    echo "Done at $(date). No adapter, so no comparison. Results: $BASE_RUN"
    exit 0
fi

echo "Fine-tuned run, started $(date)"
python -u eval/run_eval.py --model fine_tuned --out "$RUN_ROOT/fine_tuned" \
    --endpoint "$ENDPOINT" --adapter "$ADAPTER_PATH" "${EVAL_ARGS[@]}"
FT_RUN="$(only_run "$RUN_ROOT/fine_tuned")"

python -u eval/compare.py --base "$BASE_RUN" --fine-tuned "$FT_RUN" --out "$RUN_ROOT/compare" \
    "${COMPARE_ARGS[@]}"

echo "Done at $(date). Results are in $RUN_ROOT"
echo "All results are provisional: the Group B labels are not human-verified yet."
echo "Scratch is purged of old files: copy anything worth keeping to the team folder."
