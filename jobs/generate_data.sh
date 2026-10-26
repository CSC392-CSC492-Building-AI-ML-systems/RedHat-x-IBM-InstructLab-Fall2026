#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=8:00:00
#SBATCH --job-name=sdg
#SBATCH --output=/home/%u/%x-%j.log
#
# Generate synthetic training data with ilab, using a teacher model served by vLLM.
# Everything runs inside this one job: validate the taxonomy, start the teacher, wait until
# it's ready, run `ilab data generate`, then shut the teacher down.
#
# Submit from the repo folder on Fir:
#   sbatch jobs/generate_data.sh program_correctness           # one topic
#   sbatch jobs/generate_data.sh induction recurrences         # several topics
#   sbatch jobs/generate_data.sh proof_grading                 # the grading skill only
#   sbatch jobs/generate_data.sh all                           # the whole taxonomy/ folder
#
# Optional settings (put them before sbatch, e.g. `SCALE=30 sbatch jobs/generate_data.sh all`):
#   TEACHER mistral (default) or qwen. Mistral-7B-Instruct is ilab's default teacher and
#           matches sdg's prompt format. Qwen thinks out loud with sdg's prompts (slow, and
#           <think> text ends up in the data), so only use it if that's been fixed.
#   MODEL   path to the teacher model folder (overrides the TEACHER default path)
#   SCALE   --sdg-scale-factor (default 5, small for testing)
#   OUT     output folder (default ~/scratch/sdg/<teacher>/<topics>). Reuse the same OUT to resume.
# To change the time limit:  sbatch --time=12:00:00 jobs/generate_data.sh ...
# To avoid known bad nodes:  sbatch --exclude=fc10518,fc10515 jobs/generate_data.sh ...
#
# Before the first run, do the one-time docling setup in docs/data-generation.md.
# Progress:  tail -f ~/sdg-<jobid>.log      (this script)
#            tail -f <OUT>/vllm.log         (the teacher model)

set -eo pipefail
cd "$SLURM_SUBMIT_DIR"
REPO="$(pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: sbatch jobs/generate_data.sh <topic> [<topic> ...] | all"
    exit 1
fi

TOPICS=("$@")
SCALE="${SCALE:-5}"
TEACHER="${TEACHER:-mistral}"
case "$TEACHER" in
mistral)
    MODEL_FAMILY=mistral
    DEFAULT_MODEL="$REPO/models/Mistral-7B-Instruct-v0.2"
    [ -d "$DEFAULT_MODEL" ] || DEFAULT_MODEL="$HOME/scratch/models/Mistral-7B-Instruct-v0.2"
    ;;
qwen)
    MODEL_FAMILY="" # sdg has no Qwen prompt template; it falls back to merlinite
    DEFAULT_MODEL="$REPO/models/Qwen3.8-27B"
    ;;
*)
    echo "ERROR: TEACHER must be mistral or qwen, not '$TEACHER'"
    exit 1
    ;;
esac
MODEL_PATH="${MODEL:-$DEFAULT_MODEL}"
SERVED_NAME="$(basename "$MODEL_PATH" | tr '[:upper:]' '[:lower:]')"
OUT="${OUT:-$HOME/scratch/sdg/$TEACHER/$(
    IFS=_
    echo "${TOPICS[*]}"
)}"
# Other jobs can share this node, so pick a port from the job ID instead of always 8000.
PORT=$((8000 + SLURM_JOB_ID % 1000))
ENDPOINT="http://localhost:$PORT/v1"
mkdir -p "$OUT"

echo "Job $SLURM_JOB_ID on $(hostname), started $(date)"
echo "Topics: ${TOPICS[*]}   Scale factor: $SCALE   Output: $OUT   Port: $PORT"
echo "Teacher: $TEACHER ($MODEL_PATH)"

# ---- Checks that need no GPU -------------------------------------------------------
if [ ! -f "$MODEL_PATH/config.json" ]; then
    echo "ERROR: no model found at $MODEL_PATH (see docs/data-generation.md for downloading it)."
    exit 1
fi
DOCLING_CONFIG="$HOME/.local/share/instructlab/sdg/models/config.yaml"
if [ ! -f "$DOCLING_CONFIG" ]; then
    echo "ERROR: $DOCLING_CONFIG not found. Do the one-time docling setup in docs/data-generation.md first."
    exit 1
fi

# ---- Build the taxonomy to generate from -------------------------------------------
if [ "${TOPICS[0]}" = "all" ]; then
    TAXONOMY="$REPO/taxonomy"
else
    TAXONOMY="$OUT/taxonomy"
    rm -rf "$TAXONOMY"
    mkdir -p "$TAXONOMY"
    for t in "${TOPICS[@]}"; do
        # Find the leaf folder with this name anywhere in the taxonomy (knowledge or skills),
        # e.g. program_correctness or proof_grading, and copy it with its folder path.
        mapfile -t MATCHES < <(cd "$REPO/taxonomy" && find . -type d -name "$t" -exec test -f {}/qna.yaml \; -print)
        if [ ${#MATCHES[@]} -eq 0 ]; then
            echo "ERROR: no taxonomy folder named '$t' with a qna.yaml. Check the topic name."
            exit 1
        fi
        if [ ${#MATCHES[@]} -gt 1 ]; then
            echo "ERROR: more than one taxonomy folder named '$t' has a qna.yaml:"
            printf '  taxonomy/%s\n' "${MATCHES[@]#./}"
            echo "Remove or rename the extra one(s)."
            exit 1
        fi
        REL="${MATCHES[0]}"
        mkdir -p "$TAXONOMY/$(dirname "$REL")"
        cp -r "$REPO/taxonomy/$REL" "$TAXONOMY/$(dirname "$REL")/"
        echo "Using taxonomy/${REL#./}"
    done
fi
echo "Taxonomy: $TAXONOMY"

# ---- Validate before using the GPU's time on vLLM -------------------------------------
module load python/3.11.5
source "$REPO/env/ilab/.venv/bin/activate"
if [ ! -f "$HOME/.config/instructlab/config.yaml" ]; then
    ilab config init --non-interactive --taxonomy-path "$REPO/taxonomy" --taxonomy-base empty
fi
echo "Validating taxonomy..."
ilab taxonomy diff --taxonomy-path "$TAXONOMY" --taxonomy-base empty
deactivate

# ---- Start the teacher ----------------------------------------------------------------------
module load opencv/4.13 python/3.13 cuda/13.2
source "$REPO/env/model/.venv/bin/activate"

# Catch bad nodes before waiting for vLLM (nvidia-smi can look fine when CUDA doesn't work).
nvidia-smi -L
if ! python -c "import torch, sys; ok = torch.cuda.is_available(); print('CUDA OK:', ok, torch.cuda.get_device_name(0) if ok else ''); sys.exit(0 if ok else 1)"; then
    echo "ERROR: CUDA doesn't work on node $(hostname). Resubmit with --exclude=$(hostname) and report the node to support@tech.alliancecan.ca."
    exit 1
fi

# The second served name (the full path) is required: ilab sends --model as the model name
# and also loads the tokenizer from that path.
vllm serve "$MODEL_PATH" \
    --served-model-name "$SERVED_NAME" "$MODEL_PATH" \
    --max-model-len 32768 --max-num-seqs 256 --port "$PORT" \
    >"$OUT/vllm.log" 2>&1 &
VLLM_PID=$!
trap 'echo "Stopping vLLM"; kill $VLLM_PID 2>/dev/null || true' EXIT

echo "Waiting for vLLM to load (log: $OUT/vllm.log)..."
for i in $( # up to 45 minutes
    seq 1 270
); do
    if curl -sf "$ENDPOINT/models" >/dev/null; then
        echo "vLLM ready after $((i * 10)) seconds"
        break
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "ERROR: vLLM stopped while loading. Last lines of its log:"
        tail -n 30 "$OUT/vllm.log"
        exit 1
    fi
    sleep 10
done
if ! curl -sf "$ENDPOINT/models" >/dev/null; then
    echo "ERROR: vLLM was not ready after 45 minutes. Last lines of its log:"
    tail -n 30 "$OUT/vllm.log"
    exit 1
fi

# ---- Switch to ilab --------------------------------------------------------------------
deactivate
module load python/3.11.5
source "$REPO/env/ilab/.venv/bin/activate"

FAMILY_ARGS=()
[ -n "$MODEL_FAMILY" ] && FAMILY_ARGS=(--model-family "$MODEL_FAMILY")

echo "Generating data, started $(date)"
ilab data generate \
    --endpoint-url "$ENDPOINT" \
    --model "$MODEL_PATH" \
    "${FAMILY_ARGS[@]}" \
    --taxonomy-path "$TAXONOMY" \
    --taxonomy-base empty \
    --sdg-scale-factor "$SCALE" \
    --output-dir "$OUT"

echo "Done at $(date). Output is in $OUT"
echo "Scratch is purged of old files: copy anything worth keeping to the team folder."
