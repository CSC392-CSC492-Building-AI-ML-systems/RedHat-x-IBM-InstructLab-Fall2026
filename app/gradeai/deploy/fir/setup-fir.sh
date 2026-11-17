#!/bin/bash
# One-time setup on a Fir login node. Run it from this folder:
#   bash setup-fir.sh
# It creates ~/gradeai with a vLLM virtualenv (from the Alliance wheelhouse), the worker and the job script.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${GRADEAI_HOME:-$HOME/gradeai}"
mkdir -p "$DEST"

module load opencv/4.11 python/3.12

if [[ ! -x "$DEST/vllm_env/bin/python" ]]; then
  echo "Creating the vLLM environment in $DEST/vllm_env (a few minutes)…"
  virtualenv --no-download "$DEST/vllm_env"
fi
source "$DEST/vllm_env/bin/activate"
pip install --no-index --upgrade pip
pip install --no-index vllm${VLLM_VERSION:+==$VLLM_VERSION}
python -c "import vllm; print('vLLM', vllm.__version__, 'installed')"

cp "$HERE/gradeai_worker.py" "$HERE/gradeai-model.sbatch" "$DEST/"
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
