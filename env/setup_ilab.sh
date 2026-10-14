#!/bin/bash
#SBATCH --account=def-engine14
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=3:00:00
#SBATCH --job-name=setup-ilab
#SBATCH --output=/home/%u/%x-%j.log
# Build the InstructLab environment in env/ilab/.venv on Fir.
# Submit from the repo folder:  sbatch env/setup_ilab.sh
# The log is written to your home folder.

module load python/3.11.5 cmake
set -e
cd "$SLURM_SUBMIT_DIR"

if [ -d env/ilab/.venv ]; then
  echo "env/ilab/.venv already exists. Delete it first if you want to rebuild it."
  exit 1
fi

virtualenv --no-download env/ilab/.venv
source env/ilab/.venv/bin/activate

# Fir's Python refuses the standard Linux packages from PyPI ("manylinux wheels").
# This file overrides that rule, only for this install.
mkdir -p "$SLURM_TMPDIR/manylinux"
cat > "$SLURM_TMPDIR/manylinux/_manylinux.py" <<'EOF'
manylinux1_compatible = True
manylinux2010_compatible = True
manylinux2014_compatible = True

def manylinux_compatible(*args):
    return True
EOF

# Install from PyPI only, ignoring Fir's own package collection, which has
# placeholder packages for pyarrow and opencv. PyTorch comes from its CPU-only
# index, since this environment doesn't use the GPU.
PYTHONPATH="$SLURM_TMPDIR/manylinux:$PYTHONPATH" PIP_CONFIG_FILE=/dev/null \
  pip install --isolated -r env/ilab/requirements.txt \
  --extra-index-url https://download.pytorch.org/whl/cpu

python -c "import instructlab.sdg, docling, torch"
ilab --version
