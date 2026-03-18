#!/usr/bin/env bash
# run_docker.sh — Run A-eye nnU-Net inference via Docker.
#
# The image jaimebarran/fw_gear_aeye_test:latest has the trained Task313_Eye
# model weights baked in; no separate download step is required.
#
# Usage:
#   bash run_docker.sh <input_dir> <output_dir> [gpu_id]
#
#   input_dir   Directory of preprocessed NIfTI files named {ID}_0000.nii.gz
#   output_dir  Directory where segmentation label maps will be written
#   gpu_id      GPU index to use (default: 0)
#
# Example:
#   bash run_docker.sh ./nnunet_input ./nnunet_output 0

set -euo pipefail

INPUT_DIR="${1:?Usage: $0 <input_dir> <output_dir> [gpu_id]}"
OUTPUT_DIR="${2:?Usage: $0 <input_dir> <output_dir> [gpu_id]}"
GPU_ID="${3:-0}"

INPUT_DIR="$(realpath "$INPUT_DIR")"
OUTPUT_DIR="$(realpath "$OUTPUT_DIR")"
mkdir -p "$OUTPUT_DIR"

IMAGE="jaimebarran/fw_gear_aeye_test:latest"

echo "=== A-eye Docker segmentation ==="
echo "  Image:      $IMAGE"
echo "  Input dir:  $INPUT_DIR"
echo "  Output dir: $OUTPUT_DIR"
echo "  GPU:        $GPU_ID"
echo ""

# Pull image if not already present
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    echo "Pulling Docker image (first run — may take several minutes) ..."
    docker pull "$IMAGE"
fi

echo "Running nnU-Net inference ..."
docker run --rm \
    --gpus "device=$GPU_ID" \
    --shm-size=10gb \
    -v "$INPUT_DIR:/tmp/input:ro" \
    -v "$OUTPUT_DIR:/tmp/output" \
    "$IMAGE" \
    nnUNet_predict \
        -i /tmp/input \
        -o /tmp/output \
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
