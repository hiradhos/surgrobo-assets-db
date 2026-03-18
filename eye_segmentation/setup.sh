#!/usr/bin/env bash
# setup.sh — Install nnU-Net v1 and all dependencies for the A-eye pipeline.
# Tested on Python 3.8–3.10 with CUDA 11.x.
#
# Usage:
#   bash setup.sh
#
# After running, activate the venv and set the three nnUNet env vars shown at
# the end of this script before calling run_segmentation.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== A-eye setup ==="
echo "Creating virtual environment at $VENV_DIR ..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "Upgrading pip ..."
pip install --quiet --upgrade pip

echo "Installing nnU-Net v1 ..."
pip install --quiet nnunet==1.7.1

echo "Installing image processing dependencies ..."
pip install --quiet \
    nibabel>=4.0 \
    SimpleITK>=2.1 \
    scikit-image>=0.19 \
    numpy-stl>=2.17 \
    tqdm \
    dicom2nifti \
    medpy \
    scipy

echo ""
echo "=== Setup complete ==="
echo ""
echo "Activate the environment before running segmentation:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Set nnU-Net data directories (edit these paths):"
echo "  export nnUNet_raw=\"/path/to/nnUNet_raw\""
echo "  export nnUNet_preprocessed=\"/path/to/nnUNet_preprocessed\""
echo "  export nnUNet_results=\"/path/to/nnUNet_trained_models\""
echo ""
echo "Verify nnU-Net is installed:"
echo "  nnUNet_predict -h"
