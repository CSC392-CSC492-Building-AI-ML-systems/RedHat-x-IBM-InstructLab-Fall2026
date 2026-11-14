#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --gpus=h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=200G
#SBATCH --time=2:00:00
#SBATCH --job-name=test-ilab-train
#SBATCH --output=/home/%u/%x-%j.log
# A short test run of InstructLab's own trainer (ilab model train) on Qwen3.8-27B,
# to see whether it can train our model at all. It uses the same LoRA settings as
# training/lora.yaml, on the first 64 examples of a stage 2 training file, for 1 epoch
# (about 8 training steps). It saves nothing, because each InstructLab save is a full
# 54 GB copy of the model. Everything it writes goes to ~/scratch/ilab-train-test/.
#
# Needs env/ilab_gpu first (sbatch env/setup_ilab_gpu.sh).
# Submit from the repo folder:  sbatch jobs/test_ilab_train.sh
# To use another training file, give it first:  sbatch jobs/test_ilab_train.sh data/generated/<folder>/train.jsonl
#
# Why these settings:
# - DeepSpeed, because InstructLab's default (FSDP) crashes on this model before training starts.
# - Flash attention off, so examples are padded rather than packed together, which is safer
#   for Qwen3.8's linear attention layers.
# - LoRA on every language layer. InstructLab's default would only train the 16 full
#   attention layers and skip the other 48.
# - A small settings file turns off 4 bit loading, which InstructLab turns on by default.

module load python/3.11.5 gcc
set -e
cd "$SLURM_SUBMIT_DIR"
source env/ilab_gpu/.venv/bin/activate

# DeepSpeed compiles some GPU code when training starts, with the CUDA version PyTorch was built for.
torch_cuda=$(python -c "import torch; print(torch.version.cuda)")
case "$torch_cuda" in
  12.*) module load cuda/12.9 ;;
  13.*) module load cuda/13.2 ;;
  *) echo "ERROR: PyTorch was built for CUDA '$torch_cuda', which this script doesn't handle."; exit 1 ;;
esac
echo "PyTorch built for CUDA $torch_cuda, using $(nvcc --version | tail -1)"

data=${1:-data/generated/stage2_new_2026-11-13/train.jsonl}
out=$HOME/scratch/ilab-train-test/$SLURM_JOB_ID
mkdir -p "$out"
head -n 64 "$data" > "$out/test_data.jsonl"

cat > "$out/config.yaml" <<'EOF'
train:
  lora_quantize_dtype: null
EOF

args=(
  --pipeline accelerated --device cuda --gpus 1 --distributed-backend deepspeed
  --model-path models/Qwen3.8-27B
  --data-path "$out/test_data.jsonl"
  --data-output-dir "$out/data" --ckpt-output-dir "$out/ckpt"
  --num-epochs 1 --effective-batch-size 8
  --max-seq-len 4096 --max-batch-len 4096
  --learning-rate 2e-4 --warmup-steps 1
  --save-samples 1000000
  --lora-rank 16 --lora-alpha 16 --lora-dropout 0
  --disable-flash-attn --disable-accelerate-full-state-at-epoch
)
for m in q_proj k_proj v_proj o_proj in_proj_qkv in_proj_z in_proj_a in_proj_b out_proj gate_proj up_proj down_proj; do
  args+=(--lora-target-modules "$m")
done

echo "== Settings InstructLab will use (check lora_quantize_dtype is None) =="
ilab --config "$out/config.yaml" model train "${args[@]}" --debug-params || true

echo "== Training, started $(date) =="
ilab --config "$out/config.yaml" model train "${args[@]}"

echo "== Loss per step =="
find "$out" -name 'training_params_and_metrics*' -exec tail -n 20 {} \;
echo "TEST RUN FINISHED at $(date). Files are in $out"
