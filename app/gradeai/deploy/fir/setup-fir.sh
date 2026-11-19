#!/bin/bash
# One-time setup on a Fir login node. From your laptop:
#   rsync -a --delete deploy/fir/ <you>@fir.alliancecan.ca:gradeai-setup/
#   ssh <you>@fir.alliancecan.ca 'bash -l gradeai-setup/setup-fir.sh'
# It puts the model job and its helper in ~/gradeai and checks the vLLM environment named in gradeai.env.
# Safe to run again after updating GradeAI.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${GRADEAI_HOME:-$HOME/gradeai}"
mkdir -p "$DEST/logs" "$DEST/jobs"
chmod 700 "$DEST/logs" "$DEST/jobs"

cp "$HERE/gradeai-serve.sbatch" "$HERE/fir-ctl.sh" "$HERE/merge_lora.py" "$HERE/merge-lora.sbatch" "$DEST/"
chmod +x "$DEST/fir-ctl.sh"
# Files from the older setup, where the worker ran on Fir and the website on a server.
rm -f "$DEST/gradeai-model.sbatch" "$DEST/gradeai_worker.py"

# Settings from an older GradeAI version don't fit the current model job: keep a copy and start fresh.
if [[ -f "$DEST/gradeai.env" ]] && ! grep -q '^# ~/gradeai/gradeai.env on Fir: what the model job serves' "$DEST/gradeai.env"; then
  mv "$DEST/gradeai.env" "$DEST/gradeai.env.old"
  echo "Moved your older settings to $DEST/gradeai.env.old and created new ones."
fi
if [[ ! -f "$DEST/gradeai.env" ]]; then
  (umask 077; cp "$HERE/gradeai.env.example" "$DEST/gradeai.env")
  echo "Created $DEST/gradeai.env"
fi

set -a; source "$DEST/gradeai.env"; set +a
if [[ -z "${VLLM_VENV:-}" || ! -f "${VLLM_VENV}/bin/activate" ]]; then
  echo "VLLM_VENV in $DEST/gradeai.env must point to a virtualenv with vLLM (now: '${VLLM_VENV:-}')." >&2
  exit 1
fi
if [[ -n "${MODULES:-}" ]]; then module load $MODULES; fi
source "$VLLM_VENV/bin/activate"
python - <<'PY'
import vllm
v = vllm.__version__
print("vLLM", v)
major, minor = (int(x) for x in v.split(".")[:2])
if (major, minor) < (0, 17):
    print(f"Warning: vLLM {v} is older than 0.17, which Qwen3.5/3.6/3.8 models need.")
PY

[[ -f "${MODEL_PATH:-/nonexistent}/config.json" ]] \
  && echo "Model folder OK: $MODEL_PATH" \
  || echo "Note: $MODEL_PATH has no config.json yet (run the merge first, or fix MODEL_PATH in $DEST/gradeai.env)."

cat <<EOF

Fir is ready. On your laptop, in the gradeai folder:
  npm run model:connect
EOF
