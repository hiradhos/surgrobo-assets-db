#!/usr/bin/env python3
"""
preprocess.py — Prepare raw MRI data for A-eye nnU-Net inference.

Steps performed:
  1. DICOM → NIfTI conversion (skipped if input is already .nii/.nii.gz)
  2. N4 bias field correction (SimpleITK)
  3. Nyul intensity normalization
  4. Rename output to nnU-Net convention: {subject}_0000.nii.gz

Usage:
    python preprocess.py \\
        --input  /path/to/dicom_dir_or_nifti_file \\
        --output /path/to/nnunet_input_dir \\
        --subject sub001

    # Multiple subjects from a directory of NIfTI files:
    python preprocess.py \\
        --input  /path/to/nifti_dir \\
        --output /path/to/nnunet_input_dir \\
        --batch

Dependencies:
    pip install nibabel SimpleITK dicom2nifti medpy scipy tqdm
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
from tqdm import tqdm


# ── Bias field correction ──────────────────────────────────────────────────────

def n4_bias_correction(image: sitk.Image, shrink_factor: int = 2) -> sitk.Image:
    """Apply N4ITK bias field correction."""
    image = sitk.Cast(image, sitk.sitkFloat32)

    # Shrink for faster mask computation
    shrunk = sitk.Shrink(image, [shrink_factor] * image.GetDimension())
    mask = sitk.OtsuThreshold(shrunk, 0, 1, 200)

    corrector = sitk.N4BiasFieldCorrectionImageFilter()
    corrector.SetMaximumNumberOfIterations([50] * 4)
    corrected_shrunk = corrector.Execute(shrunk, mask)

    # Apply log bias field at full resolution
    log_bias = corrector.GetLogBiasFieldAsImage(image)
    corrected = image / sitk.Exp(log_bias)
    return sitk.Cast(corrected, sitk.sitkFloat32)


# ── Intensity normalization ────────────────────────────────────────────────────

def nyul_normalize(image: sitk.Image, percentiles: tuple[int, int] = (1, 99)) -> sitk.Image:
    """
    Simple percentile-based intensity normalization (Nyul-style).

    Maps the [p1, p99] range of the input to [0, 1], then clips.
    A full Nyul histogram matching would require a reference template; this
    single-image version is sufficient for nnU-Net which normalizes internally.
    """
    arr = sitk.GetArrayFromImage(image).astype(np.float32)
    p_low  = np.percentile(arr[arr > 0], percentiles[0])
    p_high = np.percentile(arr[arr > 0], percentiles[1])
    arr = np.clip((arr - p_low) / (p_high - p_low + 1e-8), 0.0, 1.0)
    out = sitk.GetImageFromArray(arr)
    out.CopyInformation(image)
    return out


# ── DICOM → NIfTI ─────────────────────────────────────────────────────────────

def dicom_to_nifti(dicom_dir: Path, out_path: Path) -> Path:
    """Convert a DICOM directory to a single NIfTI file."""
    try:
        import dicom2nifti
    except ImportError:
        raise RuntimeError(
            "dicom2nifti is required for DICOM input: pip install dicom2nifti"
        )

    tmp = Path(tempfile.mkdtemp())
    try:
        dicom2nifti.convert_directory(str(dicom_dir), str(tmp), compression=True)
        nifti_files = list(tmp.glob("*.nii.gz"))
        if not nifti_files:
            raise RuntimeError(f"No NIfTI produced from DICOM in {dicom_dir}")
        shutil.copy(nifti_files[0], out_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_path


# ── Main preprocessing pipeline ───────────────────────────────────────────────

def preprocess_subject(
    input_path: Path,
    output_dir: Path,
    subject_id: str,
    skip_bias: bool = False,
    skip_norm: bool = False,
) -> Path:
    """
    Full preprocessing pipeline for one subject.

    Returns the path of the output file ready for nnU-Net inference.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{subject_id}_0000.nii.gz"

    # Step 1: DICOM → NIfTI if needed
    if input_path.is_dir():
        print(f"  [{subject_id}] Converting DICOM → NIfTI ...")
        tmp_nii = output_dir / f"{subject_id}_raw.nii.gz"
        dicom_to_nifti(input_path, tmp_nii)
        working_path = tmp_nii
    elif input_path.suffix in (".gz", ".nii") or input_path.name.endswith(".nii.gz"):
        working_path = input_path
    else:
        raise ValueError(f"Unrecognised input: {input_path}. Expected a NIfTI file or DICOM dir.")

    image = sitk.ReadImage(str(working_path))

    # Step 2: N4 bias field correction
    if not skip_bias:
        print(f"  [{subject_id}] N4 bias field correction ...")
        image = n4_bias_correction(image)

    # Step 3: Intensity normalization
    if not skip_norm:
        print(f"  [{subject_id}] Intensity normalization ...")
        image = nyul_normalize(image)

    # Step 4: Write output with nnU-Net naming convention
    sitk.WriteImage(image, str(out_path))
    print(f"  [{subject_id}] Saved → {out_path}")

    # Clean up intermediate raw file if we created one
    if input_path.is_dir():
        tmp_nii.unlink(missing_ok=True)

    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preprocess MRI for A-eye nnU-Net inference."
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to a NIfTI file, DICOM directory, or (with --batch) a "
             "directory of NIfTI files.",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output directory for preprocessed NIfTI files.",
    )
    parser.add_argument(
        "--subject", default=None,
        help="Subject ID used in output filename. Inferred from input name if omitted.",
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Process all .nii.gz files in --input as separate subjects.",
    )
    parser.add_argument(
        "--skip_bias", action="store_true",
        help="Skip N4 bias field correction.",
    )
    parser.add_argument(
        "--skip_norm", action="store_true",
        help="Skip intensity normalization.",
    )
    args = parser.parse_args()

    input_path  = Path(args.input)
    output_dir  = Path(args.output)

    if args.batch:
        files = sorted(input_path.glob("*.nii.gz"))
        if not files:
            parser.error(f"No .nii.gz files found in {input_path}")
        for f in tqdm(files, desc="Preprocessing"):
            sid = f.name.replace(".nii.gz", "").replace(".nii", "")
            preprocess_subject(f, output_dir, sid, args.skip_bias, args.skip_norm)
    else:
        sid = args.subject or input_path.stem.replace(".nii", "").replace(".gz", "")
        preprocess_subject(input_path, output_dir, sid, args.skip_bias, args.skip_norm)


if __name__ == "__main__":
    main()
