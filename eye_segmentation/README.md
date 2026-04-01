# Eye Segmentation Pipeline (A-eye / nnU-Net)

Automated 3D segmentation of the human eye and orbit from T1-weighted MRI,
followed by mesh export into `eye_mri_assets/` for ingestion into Netter-DB.

Based on the **A-eye** project:
- GitHub: https://github.com/jaimebarran/a-eye
- Paper: https://doi.org/10.1101/2024.08.15.608051
- Atlas dataset: https://zenodo.org/records/13325371

## Segmented structures (9 labels)

| Label | Structure |
|-------|-----------|
| 1 | Lens |
| 2 | Globe (eyeball) |
| 3 | Optic nerve |
| 4 | Intraconal fat |
| 5 | Extraconal fat |
| 6 | Lateral rectus muscle |
| 7 | Medial rectus muscle |
| 8 | Inferior rectus muscle |
| 9 | Superior rectus muscle |

## Input requirements

- **Modality:** T1-weighted MRI (1.5T or 3T)
- **Format:** NIfTI (`.nii.gz`) — convert DICOM first (see step 1)
- **Coverage:** Head/orbit — full head scans work; cropped orbit volumes also accepted
- **Resolution:** Any; nnU-Net handles resampling internally

---

## Recommended path: Docker (GPU)

The Docker image `jaimebarran/fw_gear_aeye_test:latest` has the trained nnU-Net
weights baked in. This is the simplest way to run inference.

### Prerequisites

- Docker with NVIDIA GPU support (`nvidia-container-toolkit`)
- At least one CUDA-compatible GPU

### Quick start

```bash
# 1. Pull the image (first run only; ~several GB)
docker pull jaimebarran/fw_gear_aeye_test:latest

# 2. Prepare input directory — one file per subject, named {ID}_0000.nii.gz
mkdir -p /path/to/input /path/to/output
cp my_subject_T1.nii.gz /path/to/input/sub001_0000.nii.gz

# 3. Run segmentation
bash run_docker.sh /path/to/input /path/to/output

# 4. Convert label maps to per-structure STL meshes
python convert_to_mesh.py \
    --seg_dir /path/to/output \
    --out_dir ../eye_mri_assets \
    --subject sub001
```

Output meshes land in `eye_mri_assets/<subject>/` as one STL per structure.

---

## Alternative path: Local nnU-Net v1 install (CPU or GPU)

Use this if Docker is unavailable or you want to run on an HPC cluster with
Singularity (see the HPC section below).

### 1. Install nnU-Net v1

```bash
# Requires Python 3.8+
bash setup.sh
```

Or manually:

```bash
pip install nnunet==1.7.1
pip install nibabel SimpleITK scikit-image numpy-stl tqdm

# Set required environment variables (add to your .bashrc / .env)
export nnUNet_raw="/absolute/path/to/nnUNet_raw"
export nnUNet_preprocessed="/absolute/path/to/nnUNet_preprocessed"
export nnUNet_results="/absolute/path/to/nnUNet_trained_models"
```

### 2. Download trained model weights

The trained nnU-Net model for `Task313_Eye` is embedded in the Docker image.
To extract it for local use:

```bash
# Extract the trained model from the Docker image to a local directory
docker create --name aeye_tmp jaimebarran/fw_gear_aeye_test:latest
docker cp aeye_tmp:/opt/nnunet_resources/nnUNet_trained_models/. $nnUNet_results/
docker rm aeye_tmp
```

### 3. Preprocess input MRI

If your input is DICOM, convert to NIfTI first:

```bash
python preprocess.py \
    --input /path/to/dicom_or_nifti \
    --output /path/to/nnunet_input \
    --subject sub001
```

This script handles:
- DICOM → NIfTI conversion (via `dicom2nifti`)
- N4 bias field correction (via `SimpleITK`)
- Nyul intensity normalization
- Renaming to nnU-Net convention (`{ID}_0000.nii.gz`)

If your input is already a NIfTI, the script skips DICOM conversion and only
runs bias correction + normalization.

### 4. Run segmentation (local nnU-Net v1)

```bash
bash run_segmentation.sh /path/to/nnunet_input /path/to/output
```

Equivalent manual command:

```bash
nnUNet_predict \
    -i /path/to/nnunet_input \
    -o /path/to/output \
    -tr  nnUNetTrainerV2 \
    -ctr nnUNetTrainerV2CascadeFullRes \
    -m   3d_fullres \
    -p   nnUNetPlansv2.1 \
    -t   Task313_Eye
```

### 5. Convert segmentations to 3D meshes

```bash
python convert_to_mesh.py \
    --seg_dir /path/to/output \
    --out_dir ../eye_mri_assets \
    --subject sub001
```

---

## HPC / Singularity

For SLURM clusters that use Singularity instead of Docker:

```bash
singularity run \
    --bind /data/nnUNet:/opt/nnunet_resources \
    --nv \
    docker://petermcgor/nnunet:0.0.1 \
    nnUNet_predict \
        -i /opt/nnunet_resources/input \
        -o /opt/nnunet_resources/output \
        -tr  nnUNetTrainerV2 \
        -ctr nnUNetTrainerV2CascadeFullRes \
        -m   3d_fullres \
        -p   nnUNetPlansv2.1 \
        -t   Task313_Eye
```

Example SLURM batch script (`slurm_segment.sh`):

```bash
#!/bin/bash
#SBATCH --job-name=aeye_seg
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=64gb
#SBATCH --gres=gpu:1
#SBATCH --time=4:00:00

singularity run \
    --bind /data/nnUNet:/opt/nnunet_resources \
    --nv \
    docker://petermcgor/nnunet:0.0.1 \
    nnUNet_predict \
        -i /opt/nnunet_resources/input \
        -o /opt/nnunet_resources/output \
        -tr nnUNetTrainerV2 -ctr nnUNetTrainerV2CascadeFullRes \
        -m 3d_fullres -p nnUNetPlansv2.1 -t Task313_Eye
```

---

## Output structure

After running `convert_to_mesh.py`, assets land in `eye_mri_assets/`:

```
eye_mri_assets/
└── sub001/
    ├── lens.stl
    ├── globe.stl
    ├── optic_nerve.stl
    ├── intraconal_fat.stl
    ├── extraconal_fat.stl
    ├── lateral_rectus.stl
    ├── medial_rectus.stl
    ├── inferior_rectus.stl
    ├── superior_rectus.stl
    └── meta.json           ← per-subject metadata (sex, age, scanner, etc.)
```

The `manifest.json` in `eye_mri_assets/` is updated automatically with each run.

---

## Troubleshooting

**`nnUNet_predict: command not found`**
→ Run `bash setup.sh` or activate the correct conda/venv environment.

**CUDA out of memory**
→ nnU-Net v1 3d_fullres requires ~8–12 GB VRAM. On smaller GPUs, add
  `--num_threads_preprocessing 2 --num_threads_nifti_save 2` and reduce
  batch size, or use the CPU fallback (slow): remove `--gpus` from the
  Docker command.

**Segmentation all zeros / empty output**
→ Check that input files are named `{ID}_0000.nii.gz` (underscore + four
  zeros before the extension). nnU-Net v1 requires this convention.

**Mesh has holes or looks wrong**
→ Increase `--smooth_iterations` in `convert_to_mesh.py` (default 20).
  For small structures (lens, optic nerve), marching cubes at native voxel
  resolution can be noisy — try `--upsample 2` to interpolate first.
