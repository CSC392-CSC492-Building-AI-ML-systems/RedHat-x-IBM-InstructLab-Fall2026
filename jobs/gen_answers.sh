#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=3:00:00
#SBATCH --job-name=gradeai-gen
#SBATCH --output=/home/%u/%x-%j.log
#
# Write graded practice answers for the proof topics, with each grade chosen before the answer
# is written (see tools/gen_answers.py). The job reads the seeds from the taxonomy, starts vLLM
# with Qwen3.8-27B the same way eval/jobs/run_eval.sh does, runs the generator, and stops vLLM
# however the job ends. Nothing is trained here. The output is checked by people first.
#
# Submit from the repo folder on Fir:
#   sbatch jobs/gen_answers.sh
#   sbatch jobs/gen_answers.sh --limit-seeds 2 --per-question 3 --refs 1     # small test
#
# Progress:  tail -f ~/gradeai-gen-<jobid>.log
# Results:   ~/scratch/gradeai-gen/<jobid>/ (summary.json, review.md, candidates.jsonl)

set -eo pipefail
# Under sbatch the script runs from a copy, so the repo is the folder the job was submitted from.
REPO="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
OUT="$HOME/scratch/gradeai-gen/${SLURM_JOB_ID:-local}"
PORT=$((8000 + ${SLURM_JOB_ID:-0} % 1000))
ENDPOINT="http://127.0.0.1:$PORT/v1"
TOPICS="asymptotic_analysis induction_simple induction_complete structural_induction recurrences program_correctness"

echo "GradeAI answer generation, job ${SLURM_JOB_ID:-local} on $(hostname), started $(date)"
cd "$REPO"
module load opencv/4.13 python/3.13 cuda/13.2
source env/model/.venv/bin/activate
mkdir -p "$OUT"

python tools/extract_seeds.py "$REPO" "$OUT/seeds.json" $TOPICS

nvidia-smi -L
if ! python -c "import torch, sys; ok = torch.cuda.is_available(); print('CUDA OK:', ok); sys.exit(0 if ok else 1)"; then
    echo "ERROR: CUDA doesn't work on node $(hostname). Resubmit with --exclude=$(hostname)."
    exit 1
fi

vllm serve "$REPO/models/Qwen3.8-27B" --served-model-name qwen3.8-27b \
    --max-model-len 32768 --max-num-seqs 256 --host 127.0.0.1 --port "$PORT" \
    >"$OUT/vllm.log" 2>&1 &
VLLM_PID=$!
stop_vllm() {
    pkill -TERM -P "$VLLM_PID" 2>/dev/null || true
    kill -TERM "$VLLM_PID" 2>/dev/null || true
}
trap stop_vllm EXIT

echo "Waiting for vLLM on port $PORT (log: $OUT/vllm.log)..."
waited=0
until curl -sf "$ENDPOINT/models" >/dev/null 2>&1; do
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "ERROR: vLLM stopped while loading. Last lines of its log:"
        tail -n 30 "$OUT/vllm.log"
        exit 1
    fi
    if [ "$waited" -ge 2700 ]; then
        echo "ERROR: vLLM was not ready after 2700s. Last lines of its log:"
        tail -n 30 "$OUT/vllm.log"
        exit 1
    fi
    sleep 10
    waited=$((waited + 10))
done
echo "vLLM ready after about ${waited}s"

python -u tools/gen_answers.py --seeds "$OUT/seeds.json" --endpoint "$ENDPOINT" \
    --model qwen3.8-27b --out "$OUT" "$@"
echo "Done at $(date). Results: $OUT"
