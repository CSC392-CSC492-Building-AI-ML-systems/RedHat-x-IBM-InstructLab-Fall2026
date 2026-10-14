#!/bin/bash
# Build the model environment (vLLM) in env/model/.venv on Fir.
# Run from a login node:  bash env/setup_model.sh
# Everything comes from Fir's own package collection, following
# https://docs.alliancecan.ca/wiki/VLLM

module load opencv/4.13 python/3.13
set -e
cd "$(dirname "$0")/.."

if [ -d env/model/.venv ]; then
  echo "env/model/.venv already exists. Delete it first if you want to rebuild it."
  exit 1
fi

virtualenv --no-download env/model/.venv
source env/model/.venv/bin/activate
pip install --no-index --upgrade pip
pip install --no-index -r env/model/requirements.txt

python -c "import vllm; print('vllm', vllm.__version__)"
