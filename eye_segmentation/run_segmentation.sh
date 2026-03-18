#!/usr/bin/env bash
# run_segmentation.sh — Run A-eye nnU-Net v1 inference locally.
#
# Prerequisites:
#   - nnU-Net v1 installed (bash setup.sh)
#   - Trained model extracted to $nnUNet_results (see README.md)
#   - Three env vars set:
#       export nnUNet_raw="/path/to/nnUNet_raw"
#       export nnUNet_preprocessed="/path/to/nnUNet_preprocessed"
#       export nnUNet_results="/path/to/nnUNet_trained_models"
#
# Usage:
#   bash run_segmentation.sh <input_dir> <output_dir>
#
#   input_dir   Directory of preprocessed NIfTI files named {ID}_0000.nii.gz
#   output_dir  Directory where segmentation label maps will be written
#
# Example:
#   bash run_segmentation.sh ./nnunet_input ./nnunet_output

set -euo pipefail

INPUT_DIR="${1:?Usage: $0 <input_dir> <output_dir>}"
OUTPUT_DIR="${2:?Usage: $0 <input_dir> <output_dir>}"

# Validate nnU-Net env vars
for var in nnUNet_raw nnUNet_preprocessed nnUNet_results; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: $var is not set."
        echo "  export $var=\"/path/to/...\""
        exit 1
    fi
done

mkdir -p "$OUTPUT_DIR"

echo "=== A-eye local nnU-Net segmentation ==="
echo "  Input dir:  $INPUT_DIR"
echo "  Output dir: $OUTPUT_DIR"
echo "  nnUNet_results: $nnUNet_results"
echo ""

nnUNet_predict \
    -i  "$INPUT_DIR" \
    -o  "$OUTPUT_DIR" \
    -tr  nnUNetTrainerV2 \
    -ctr nnUNetTrainerV2CascadeFullRes \
    -m   3d_fullres \
    -p   nnUNetPlansv2.1 \
    -t   Task313_Eye

echo ""
echo "Segmentation complete. Label maps written to:"
echo "  $OUTPUT_DIR"
echo ""
echo "Next: convert label maps to STL meshes:"
echo "  python convert_to_mesh.py --seg_dir $OUTPUT_DIR --out_dir ../eye_mri_assets"
