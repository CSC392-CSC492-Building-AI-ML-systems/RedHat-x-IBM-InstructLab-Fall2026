#!/bin/bash
# Merge a LoRA adapter into its base model (CPU only, no GPU needed). On Fir:
#   M=/project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026/models
#   sbatch ~/gradeai/merge-lora.sbatch $M/Qwen3.8-27B $M/adapters/stage2_v2clean_2026-11-15 $M/merged-v2clean
# Uses your training environment (torch, transformers, peft). Override with TRAIN_VENV / TRAIN_MODULES.
#SBATCH --job-name=gradeai-merge
#SBATCH --account=def-engine14
#SBATCH --cpus-per-task=8
#SBATCH --mem=160G
#SBATCH --time=0-03:00:00
#SBATCH --output=%x-%j.out
set -euo pipefail
BASE="$1"; ADAPTER="$2"; OUT="$3"
REPO=/project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026

module load ${TRAIN_MODULES:-gcc arrow/25.0.0 python/3.13 cuda/12.9}
source "${TRAIN_VENV:-$REPO/env/train/.venv}/bin/activate"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

python "${GRADEAI_HOME:-$HOME/gradeai}/merge_lora.py" --base "$BASE" --adapter "$ADAPTER" --out "$OUT"
