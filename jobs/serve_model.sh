#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=3:00:00
#SBATCH --job-name=serve-qwen
#SBATCH --output=/home/%u/%x-%j.log
# Start Qwen3.8-27B on one H100 with vLLM, as a server on port 8000.
# Submit from the repo folder:  sbatch jobs/serve_model.sh
# The log (in your home folder) shows which computer it's running on.

# vLLM compiles some GPU code when it starts, which needs the CUDA module.
module load opencv/4.13 python/3.13 cuda/13.2
set -e
cd "$SLURM_SUBMIT_DIR"
source env/model/.venv/bin/activate

echo "Qwen will be at http://$(hostname):8000/v1 once it has loaded"
vllm serve models/Qwen3.8-27B \
  --served-model-name qwen3.8-27b \
  --max-model-len 32768 \
  --max-num-seqs 256 \
  --port 8000
