#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=8:00:00
#SBATCH --job-name=sdg
#SBATCH --output=/home/%u/%x-%j.log
#
# Generate synthetic training data with ilab, using Qwen (served by vLLM) as the teacher.
# Everything runs inside this one job: start Qwen, wait until it's ready, validate the
# taxonomy, run `ilab data generate`, then shut Qwen down.
#
# Submit from the repo folder on Fir:
#   sbatch jobs/generate_data.sh program_correctness           # one topic
#   sbatch jobs/generate_data.sh induction recurrences         # several topics
#   sbatch jobs/generate_data.sh all                           # the whole taxonomy/ folder
#
# Optional settings (put them before sbatch, e.g. `SCALE=30 sbatch jobs/generate_data.sh all`):
#   SCALE   --sdg-scale-factor (default 5, small for testing)
#   OUT     output folder (default ~/scratch/sdg/<topics>). Reuse the same OUT to resume.
# To change the time limit:  sbatch --time=12:00:00 jobs/generate_data.sh ...
# To avoid known bad nodes:  sbatch --exclude=fc10518,fc10515 jobs/generate_data.sh ...
#
# Before the first run, do the one-time docling setup in docs/data-generation.md.
# Progress:  tail -f ~/sdg-<jobid>.log      (this script)
#            tail -f <OUT>/vllm.log         (Qwen)

set -eo pipefail
cd "$SLURM_SUBMIT_DIR"
REPO="$(pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: sbatch jobs/generate_data.sh <topic> [<topic> ...] | all"
    exit 1
fi

TOPICS=("$@")
SCALE="${SCALE:-5}"
OUT="${OUT:-$HOME/scratch/sdg/$(
    IFS=_
    echo "${TOPICS[*]}"
)}"
MODEL_PATH="$REPO/models/Qwen3.8-27B"
# Other jobs can share this node, so pick a port from the job ID instead of always 8000.
PORT=$((8000 + SLURM_JOB_ID % 1000))
ENDPOINT="http://localhost:$PORT/v1"
mkdir -p "$OUT"

echo "Job $SLURM_JOB_ID on $(hostname), started $(date)"
echo "Topics: ${TOPICS[*]}   Scale factor: $SCALE   Output: $OUT   Port: $PORT"

# ---- Checks that need no GPU -------------------------------------------------------
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
    mkdir -p "$TAXONOMY/knowledge/computer_science/csc236"
    for t in "${TOPICS[@]}"; do
        SRC="$REPO/taxonomy/knowledge/computer_science/csc236/$t"
        if [ ! -f "$SRC/qna.yaml" ]; then
            echo "ERROR: $SRC/qna.yaml not found. Check the topic name."
            exit 1
        fi
        cp -r "$SRC" "$TAXONOMY/knowledge/computer_science/csc236/"
    done
fi
echo "Taxonomy: $TAXONOMY"

# ---- Start Qwen ----------------------------------------------------------------------
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
    --served-model-name qwen3.8-27b "$MODEL_PATH" \
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

if [ ! -f "$HOME/.config/instructlab/config.yaml" ]; then
    ilab config init --non-interactive --taxonomy-path "$REPO/taxonomy" --taxonomy-base empty
fi

echo "Validating taxonomy..."
ilab taxonomy diff --taxonomy-path "$TAXONOMY" --taxonomy-base empty

echo "Generating data, started $(date)"
ilab data generate \
    --endpoint-url "$ENDPOINT" \
    --model "$MODEL_PATH" \
    --taxonomy-path "$TAXONOMY" \
    --taxonomy-base empty \
    --sdg-scale-factor "$SCALE" \
    --output-dir "$OUT"

echo "Done at $(date). Output is in $OUT"
echo "Scratch is purged of old files: copy anything worth keeping to the team folder."
