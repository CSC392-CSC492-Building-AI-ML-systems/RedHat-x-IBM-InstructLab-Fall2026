#!/bin/bash
# One-time setup on a Fir login node. Run it from this folder:
#   bash setup-fir.sh
# It creates ~/gradeai with a vLLM virtualenv (from the Alliance wheelhouse), the worker and the job script.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${GRADEAI_HOME:-$HOME/gradeai}"
mkdir -p "$DEST"

module load ${MODULES:-opencv/4.11 python/3.12}

if [[ -n "${VLLM_VENV:-}" ]]; then
  # Reuse an existing environment (set VLLM_VENV and MODULES, and put the same two lines in gradeai.env).
  echo "Using your existing environment $VLLM_VENV"
  source "$VLLM_VENV/bin/activate"
else
  if [[ ! -x "$DEST/vllm_env/bin/python" ]]; then
    echo "Creating the vLLM environment in $DEST/vllm_env (a few minutes)…"
    virtualenv --no-download "$DEST/vllm_env"
  fi
  source "$DEST/vllm_env/bin/activate"
  pip install --no-index --upgrade pip
  pip install --no-index vllm${VLLM_VERSION:+==$VLLM_VERSION}
fi
python -c "import vllm; print('vLLM', vllm.__version__, 'installed')"
python - <<'PY'
import vllm
major, minor = (int(x) for x in vllm.__version__.split('.')[:2])
if (major, minor) < (0, 17):
    print(f"Warning: vLLM {vllm.__version__} is older than 0.17, which Qwen3.5/3.6/3.8 models need.")
    print("Try: pip install --no-index 'vllm>=0.17'  (or, from a login node: pip install 'vllm>=0.17')")
PY

cp "$HERE/gradeai_worker.py" "$HERE/gradeai-model.sbatch" "$HERE/merge_lora.py" "$HERE/merge-lora.sbatch" "$DEST/"
chmod +x "$DEST/gradeai_worker.py"
if [[ ! -f "$DEST/gradeai.env" ]]; then
  cp "$HERE/gradeai.env.example" "$DEST/gradeai.env"
  chmod 600 "$DEST/gradeai.env"
  echo "Created $DEST/gradeai.env — fill in MODEL_PATH, GRADEAI_URL and GRADEAI_WORKER_TOKEN."
fi

cat <<EOF

Next:
  1. nano $DEST/gradeai.env          # model path, server URL, worker token
  2. nano $DEST/gradeai-model.sbatch # set --account=def-yourpi and --time
  3. sbatch $DEST/gradeai-model.sbatch
  4. tail -f gradeai-model-<jobid>.out   # "vLLM is up" then GradeAI shows the model online
EOF
