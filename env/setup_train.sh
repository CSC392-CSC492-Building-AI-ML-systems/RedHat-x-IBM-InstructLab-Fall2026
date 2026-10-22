#!/bin/bash
# Build the training environment (Unsloth) in env/train/.venv on Fir.
# Run from a login node:  bash env/setup_train.sh
# Everything comes from Fir's own package collection. pyarrow can't be
# installed with pip there, so it comes from Fir's arrow module instead.
module load gcc arrow/25.0.0 python/3.13
set -e
cd "$(dirname "$0")/.."
if [ -d env/train/.venv ]; then
  echo "env/train/.venv already exists. Delete it first if you want to rebuild it."
  exit 1
fi
virtualenv --no-download env/train/.venv
source env/train/.venv/bin/activate
pip install --no-index --upgrade pip
pip install --no-index -r env/train/requirements.txt
# Unsloth itself can only be imported on a GPU node, so this checks the rest.
python -c "import peft, trl; print('trl', trl.__version__)"
