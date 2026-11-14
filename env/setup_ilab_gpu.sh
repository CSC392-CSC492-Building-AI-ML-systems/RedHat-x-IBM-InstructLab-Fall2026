#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=3:00:00
#SBATCH --job-name=setup-ilab-gpu
#SBATCH --output=/home/%u/%x-%j.log
# Build a GPU copy of the InstructLab environment in env/ilab_gpu/.venv on Fir,
# so InstructLab's own trainer (ilab model train) can use the H100s.
# It has the same packages as env/ilab, except that PyTorch has GPU support and
# DeepSpeed is added. The regular env/ilab stays as it is.
# Submit from the repo folder:  sbatch env/setup_ilab_gpu.sh
# The log is written to your home folder. When it finishes, the exact versions
# are saved to env/ilab_gpu/requirements.txt.

module load python/3.11.5 cmake
set -e
cd "$SLURM_SUBMIT_DIR"

if [ -d env/ilab_gpu/.venv ]; then
  echo "env/ilab_gpu/.venv already exists. Delete it first if you want to rebuild it."
  exit 1
fi

virtualenv --no-download env/ilab_gpu/.venv
source env/ilab_gpu/.venv/bin/activate

# Same rule override as env/setup_ilab.sh: let pip use the standard Linux packages from PyPI.
mkdir -p "$SLURM_TMPDIR/manylinux"
cat > "$SLURM_TMPDIR/manylinux/_manylinux.py" <<'EOF'
manylinux1_compatible = True
manylinux2010_compatible = True
manylinux2014_compatible = True

def manylinux_compatible(*args):
    return True
EOF
export PYTHONPATH="$SLURM_TMPDIR/manylinux:$PYTHONPATH" PIP_CONFIG_FILE=/dev/null

# The env/ilab package list, minus its CPU-only PyTorch. The regular PyPI PyTorch
# of the same version comes with GPU support.
grep -vE '^(torch|torchvision)==' env/ilab/requirements.txt > "$SLURM_TMPDIR/requirements.txt"
pip install --isolated --no-cache-dir -r "$SLURM_TMPDIR/requirements.txt" torch==2.14.1 torchvision==0.29.1

# InstructLab's trainer needs DeepSpeed. It builds its GPU code with PyTorch, so it
# goes in after PyTorch. ninja lets DeepSpeed compile that code when training starts.
# DeepSpeed's installer looks for the CUDA tools that match PyTorch's CUDA version.
torch_cuda=$(python -c "import torch; print(torch.version.cuda)")
case "$torch_cuda" in
  12.*) module load gcc cuda/12.9 ;;
  13.*) module load gcc cuda/13.2 ;;
  *) echo "ERROR: PyTorch was built for CUDA '$torch_cuda', which this script doesn't handle."; exit 1 ;;
esac
pip install --isolated --no-cache-dir --no-build-isolation deepspeed ninja

python -c "import instructlab.training, deepspeed, torch; print('torch', torch.__version__, 'built for CUDA', torch.version.cuda); print('deepspeed', deepspeed.__version__)"
ilab --version
pip freeze > env/ilab_gpu/requirements.txt
echo "Done. Versions saved to env/ilab_gpu/requirements.txt"
