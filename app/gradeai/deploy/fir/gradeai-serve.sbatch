#!/bin/bash
# GradeAI model job for Fir: serves your fine-tuned model with vLLM on one H100, so GradeAI on
# your laptop can reach it through an SSH tunnel.
#
# You normally don't submit this yourself: `npm run model:connect` (or `npm run model:start`)
# on your laptop does it for you. By hand, on Fir:
#   bash ~/gradeai/fir-ctl.sh start 4        # 4 hours
#SBATCH --job-name=gradeai-serve
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=0-04:00:00
#SBATCH --output=%x-%j.out

set -euo pipefail
G="${GRADEAI_HOME:-$HOME/gradeai}"
set -a; source "$G/gradeai.env"; set +a

module load ${MODULES:-opencv/4.11 python/3.12}
source "${VLLM_VENV:-$G/vllm_env}/bin/activate"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # weights come from disk only

# A random port and key for this job. Your laptop reads them over SSH to open the tunnel;
# nobody without the key can use the model, even from inside the cluster.
PORT="$(python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1])')"
KEY="$(python -c 'import secrets; print(secrets.token_hex(24))')"
END="$(date -d "$(squeue -h -j "$SLURM_JOB_ID" -o %e 2>/dev/null)" +%s 2>/dev/null || true)"

mkdir -p "$G/jobs" && chmod 700 "$G/jobs"
INFO="$G/jobs/$SLURM_JOB_ID.env"
(umask 077; printf 'MODEL_PORT=%s\nMODEL_KEY=%s\nMODEL_NAME=%s\nMODEL_END=%s\n' "$PORT" "$KEY" "$MODEL_NAME" "$END" > "$INFO")
trap 'rm -f "$INFO"' EXIT
export VLLM_API_KEY="$KEY"   # vLLM reads the key from here (a command-line flag would show in `ps` to others on the node)

# Optional unmerged LoRA adapter on top of MODEL_PATH (the base). A merged model is safer for Qwen3.8.
SERVED_NAME="$MODEL_NAME"
LORA_ARGS=()
if [[ -n "${LORA_PATH:-}" ]]; then
  RANK="$(python -c 'import json,sys; print(json.load(open(sys.argv[1] + "/adapter_config.json")).get("r", 16))' "$LORA_PATH")"
  MAX_RANK=16
  for r in 8 16 32 64 128 256 320 512; do if (( r >= RANK )); then MAX_RANK=$r; break; fi; done
  LORA_ARGS=(--enable-lora --lora-modules "${MODEL_NAME}=${LORA_PATH}" --max-lora-rank "$MAX_RANK")
  SERVED_NAME="${MODEL_NAME}-base"
  echo "LoRA adapter ${LORA_PATH} (rank ${RANK}) on base ${MODEL_PATH}"
fi

echo "GradeAI model job ${SLURM_JOB_ID} on $(hostname), port ${PORT}: ${MODEL_PATH}"
vllm serve "$MODEL_PATH" \
  --served-model-name "$SERVED_NAME" \
  "${LORA_ARGS[@]}" \
  --host 0.0.0.0 --port "$PORT" \
  --max-model-len "${MAX_MODEL_LEN:-8192}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.90}" \
  ${VLLM_EXTRA_ARGS:-} &
VLLM_PID=$!
trap 'kill "$VLLM_PID" 2>/dev/null || true' TERM INT

# Once it answers, make sure it refuses requests without the key.
(
  for _ in $(seq 360); do
    if curl -sf -m 5 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
      if curl -sf -m 5 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
        echo "vLLM answered without the API key, so the model isn't protected. Stopping." >&2
        kill "$VLLM_PID"
      else
        echo "Model is ready (job $SLURM_JOB_ID on $(hostname), port $PORT)."
      fi
      exit 0
    fi
    sleep 10
  done
) &
wait "$VLLM_PID"
