#!/bin/bash
# GradeAI model job for Fir: serves your fine-tuned checkpoint with vLLM on one H100
# and runs the worker that pulls grading tasks from your GradeAI server.
#
#   sbatch ~/gradeai/gradeai-model.sbatch
#
# Edit --account and --time below. Fir allows jobs from 1 hour up to 7 days.
#SBATCH --job-name=gradeai-model
#SBATCH --account=def-CHANGEME
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=1-00:00:00
#SBATCH --signal=B:TERM@600
#SBATCH --output=%x-%j.out

set -euo pipefail
GRADEAI_HOME="${GRADEAI_HOME:-$HOME/gradeai}"
set -a; source "$GRADEAI_HOME/gradeai.env"; set +a

module load opencv/4.11 python/3.12
source "$GRADEAI_HOME/vllm_env/bin/activate"

# Weights are read from disk only.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
# vLLM listens on this node only, behind a key generated for this job.
export VLLM_API_KEY="$(python -c 'import secrets; print(secrets.token_hex(16))')"
PORT="$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
export VLLM_URL="http://127.0.0.1:${PORT}/v1"

echo "GradeAI model job ${SLURM_JOB_ID} on $(hostname) — model ${MODEL_PATH}"
vllm serve "$MODEL_PATH" \
  --served-model-name "$MODEL_NAME" \
  --host 127.0.0.1 --port "$PORT" \
  --api-key "$VLLM_API_KEY" \
  --max-model-len "${MAX_MODEL_LEN:-8192}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.90}" \
  ${VLLM_EXTRA_ARGS:-} \
  > "vllm-${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!

python "$GRADEAI_HOME/gradeai_worker.py" &
WORKER_PID=$!

# Slurm sends TERM 10 minutes before the time limit: finish current work, then stop.
shutdown() {
  echo "Stopping: letting the worker finish its current tasks"
  kill -TERM "$WORKER_PID" 2>/dev/null || true
  wait "$WORKER_PID" 2>/dev/null || true
  kill "$VLLM_PID" 2>/dev/null || true
}
trap shutdown TERM INT

# Optional: queue the next job now so the model comes back right after this one ends.
if [[ "${RESUBMIT:-0}" == "1" ]]; then
  sbatch --dependency=afterany:"${SLURM_JOB_ID}" "$GRADEAI_HOME/gradeai-model.sbatch" || true
fi

wait "$WORKER_PID" || true
kill "$VLLM_PID" 2>/dev/null || true
wait "$VLLM_PID" 2>/dev/null || true
