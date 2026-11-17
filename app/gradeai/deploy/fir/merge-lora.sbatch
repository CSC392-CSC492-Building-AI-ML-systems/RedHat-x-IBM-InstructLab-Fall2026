#!/bin/bash
# Merge a LoRA adapter into its base model (CPU only, no GPU needed).
#   sbatch merge-lora.sbatch <base folder> <adapter folder> <output folder>
# Activate the environment you trained with below (it must have torch, transformers, peft).
#SBATCH --job-name=gradeai-merge
#SBATCH --account=def-CHANGEME
#SBATCH --cpus-per-task=8
#SBATCH --mem=160G
#SBATCH --time=0-03:00:00
#SBATCH --output=%x-%j.out
set -euo pipefail
BASE="$1"; ADAPTER="$2"; OUT="$3"

module load opencv/4.11 python/3.12
# CHANGE THIS to the virtualenv you trained the adapter with:
source "${TRAIN_VENV:?Set TRAIN_VENV to your training virtualenv, e.g. sbatch --export=ALL,TRAIN_VENV=/path/to/venv ...}/bin/activate"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

python "$(dirname "$0")/merge_lora.py" --base "$BASE" --adapter "$ADAPTER" --out "$OUT"
