#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=8:00:00
#SBATCH --job-name=train-lora
#SBATCH --output=/home/%u/%x-%j.log
# Fine-tune Qwen3.8-27B with LoRA on one H100, using the settings in training/lora.yaml.
# Submit from the repo folder:  sbatch jobs/train_lora.sh
# For a quick test on a small file, which stops after 10 steps:
#   sbatch --time=1:00:00 jobs/train_lora.sh --data data/generated/seed_qna.jsonl --output models/adapters/test --max-steps 10
# The log (in your home folder) shows the training loss as it goes.

# The arrow module provides pyarrow, and the training code compiles some GPU
# code when it starts, so it needs CUDA too. The PyTorch in this environment
# was built for CUDA 12.9, so the CUDA module has to match it.
module load gcc arrow/25.0.0 python/3.13 cuda/12.9
set -e
cd "$SLURM_SUBMIT_DIR"
source env/train/.venv/bin/activate
python training/train_lora.py training/lora.yaml "$@"
