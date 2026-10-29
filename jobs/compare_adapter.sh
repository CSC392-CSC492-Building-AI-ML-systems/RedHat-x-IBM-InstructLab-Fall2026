#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=1:00:00
#SBATCH --job-name=compare-adapter
#SBATCH --output=/home/%u/%x-%j.log
# Ask the original model and a fine-tuned one the same questions, using training/compare_adapter.py.
# Submit from the repo folder:  sbatch jobs/compare_adapter.sh models/adapters/stage1_2026-10-28
# The answers go to the log (in your home folder) and to comparison.md in the adapter's folder.

# Same modules as jobs/train_lora.sh, for the same reasons.
module load gcc arrow/25.0.0 python/3.13 cuda/12.9
set -e
cd "$SLURM_SUBMIT_DIR"
source env/train/.venv/bin/activate
python -u training/compare_adapter.py "$@"
