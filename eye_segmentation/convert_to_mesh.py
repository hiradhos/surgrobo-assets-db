#!/usr/bin/env python3
"""
convert_to_mesh.py — Convert A-eye nnU-Net segmentation label maps to STL meshes.

For each segmentation NIfTI produced by nnU-Net (one file per subject, containing
labels 1–9), this script:

  1. Loads the label map with nibabel
  2. Runs marching cubes (scikit-image) on each label to extract an isosurface
  3. Applies Laplacian smoothing to reduce staircase artefacts
  4. Writes one STL per structure into eye_mri_assets/<subject>/
  5. Writes a per-subject meta.json with provenance metadata
  6. Updates eye_mri_assets/manifest.json

Label definitions (A-eye / Task313_Eye):
  1 lens          2 globe          3 optic_nerve
  4 intraconal_fat  5 extraconal_fat
  6 lateral_rectus  7 medial_rectus
  8 inferior_rectus 9 superior_rectus

Usage:
    # Single subject (auto-detects subject ID from filename):
    python convert_to_mesh.py \\
        --seg_dir /path/to/nnunet_output \\
        --out_dir ../eye_mri_assets

    # Explicit subject ID + optional metadata:
    python convert_to_mesh.py \\
        --seg_dir /path/to/nnunet_output \\
        --out_dir ../eye_mri_assets \\
        --subject sub001 \\
        --sex male \\
        --age 42 \\
        --scanner "Siemens Magnetom Avanto 1.5T"

    # Batch: process all .nii.gz in seg_dir:
    python convert_to_mesh.py \\
        --seg_dir /path/to/nnunet_output \\
        --out_dir ../eye_mri_assets \\
        --batch

Dependencies:
    pip install nibabel scikit-image numpy-stl tqdm
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from skimage import measure
from stl import mesh as stl_mesh
from tqdm import tqdm


# ── Label map ─────────────────────────────────────────────────────────────────

LABELS: dict[int, str] = {
    1: "lens",
    2: "globe",
    3: "optic_nerve",
    4: "intraconal_fat",
    5: "extraconal_fat",
    6: "lateral_rectus",
    7: "medial_rectus",
    8: "inferior_rectus",
    9: "superior_rectus",
}

LABEL_DISPLAY: dict[int, str] = {
    1: "Lens",
    2: "Globe (Eyeball)",
    3: "Optic Nerve",
    4: "Intraconal Fat",
    5: "Extraconal Fat",
    6: "Lateral Rectus Muscle",
    7: "Medial Rectus Muscle",
    8: "Inferior Rectus Muscle",
    9: "Superior Rectus Muscle",
}


# ── Mesh utilities ─────────────────────────────────────────────────────────────

def smooth_mesh(
    verts: np.ndarray,
    faces: np.ndarray,
    iterations: int = 20,
    lam: float = 0.5,
) -> np.ndarray:
    """
    Laplacian smoothing — iteratively moves each vertex toward the average
    position of its neighbours.

    Returns smoothed vertices (faces are unchanged).
    """
    # Build adjacency: vertex → set of neighbour vertex indices
    adjacency: dict[int, set[int]] = {i: set() for i in range(len(verts))}
    for tri in faces:
        for i, j in [(0, 1), (1, 2), (2, 0)]:
            adjacency[tri[i]].add(tri[j])
            adjacency[tri[j]].add(tri[i])

    smoothed = verts.copy().astype(np.float64)
    for _ in range(iterations):
        new_verts = smoothed.copy()
        for idx, neighbours in adjacency.items():
            if neighbours:
                avg = smoothed[list(neighbours)].mean(axis=0)
                new_verts[idx] = smoothed[idx] + lam * (avg - smoothed[idx])
        smoothed = new_verts
    return smoothed.astype(np.float32)


def label_to_stl(
    label_vol: np.ndarray,
    label_id: int,
    voxel_spacing: tuple[float, float, float],
    smooth_iterations: int = 20,
    upsample: int = 1,
) -> stl_mesh.Mesh | None:
    """
    Extract an isosurface for a single label and return a numpy-stl Mesh.

    Returns None if the label is absent in the volume.
    """
    binary = (label_vol == label_id).astype(np.uint8)
    if binary.sum() == 0:
        return None

    if upsample > 1:
        from scipy.ndimage import zoom
        binary = zoom(binary, zoom=upsample, order=1)
        spacing = tuple(s / upsample for s in voxel_spacing)
    else:
        spacing = voxel_spacing

    # Marching cubes: level=0.5 for binary mask
    verts, faces, normals, _ = measure.marching_cubes(
        binary,
        level=0.5,
        spacing=spacing,
        allow_degenerate=False,
    )

    if len(faces) == 0:
        return None

    # Laplacian smoothing
    if smooth_iterations > 0:
        verts = smooth_mesh(verts, faces, iterations=smooth_iterations)

    # Pack into numpy-stl Mesh
    m = stl_mesh.Mesh(np.zeros(faces.shape[0], dtype=stl_mesh.Mesh.dtype))
    for i, tri in enumerate(faces):
        for j in range(3):
            m.vectors[i][j] = verts[tri[j]]
    return m


# ── Per-subject processing ────────────────────────────────────────────────────

def process_subject(
    seg_path: Path,
    out_dir: Path,
    subject_id: str,
    smooth_iterations: int = 20,
    upsample: int = 1,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convert all labels in one segmentation NIfTI to STL files.

    Returns a manifest entry dict for this subject.
    """
    subject_out = out_dir / subject_id
    subject_out.mkdir(parents=True, exist_ok=True)

    img   = nib.load(str(seg_path))
    data  = np.asarray(img.dataobj, dtype=np.int16)
    zooms = img.header.get_zooms()[:3]  # voxel spacing in mm

    structures_written: list[dict[str, str]] = []
    print(f"  [{subject_id}] Processing {len(LABELS)} structures ...")

    for label_id, struct_name in tqdm(LABELS.items(), desc=f"  {subject_id}", leave=False):
        stl_path = subject_out / f"{struct_name}.stl"
        m = label_to_stl(
            label_vol=data,
            label_id=label_id,
            voxel_spacing=tuple(float(z) for z in zooms),
            smooth_iterations=smooth_iterations,
            upsample=upsample,
        )
        if m is None:
            print(f"    WARNING: label {label_id} ({struct_name}) not found in {seg_path.name}")
            continue
        m.save(str(stl_path))
        structures_written.append({
            "label_id": label_id,
            "structure": struct_name,
            "display_name": LABEL_DISPLAY[label_id],
            "file": f"{subject_id}/{struct_name}.stl",
        })

    # Write per-subject meta.json
    meta: dict[str, Any] = {
        "subject_id": subject_id,
        "source": "a-eye nnU-Net (Task313_Eye)",
        "paper_doi": "10.1101/2024.08.15.608051",
        "segmentation_model": "nnUNetTrainerV2 / 3d_fullres / nnUNetPlansv2.1",
        "modality": "T1w MRI",
        "voxel_spacing_mm": [float(z) for z in zooms],
        "structures": structures_written,
        "converted_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_meta:
        meta.update(extra_meta)

    with open(subject_out / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  [{subject_id}] {len(structures_written)}/{len(LABELS)} structures → {subject_out}")
    return meta


# ── Manifest helpers ──────────────────────────────────────────────────────────

MANIFEST_PATH_DEFAULT = Path(__file__).resolve().parents[1] / "eye_mri_assets" / "manifest.json"


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return {"source": "a-eye", "subjects": {}}


def save_manifest(manifest: dict[str, Any], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert A-eye nnU-Net segmentations to per-structure STL meshes."
    )
    parser.add_argument(
        "--seg_dir", required=True,
        help="Directory containing nnU-Net output .nii.gz segmentation files.",
    )
    parser.add_argument(
        "--out_dir", default=str(MANIFEST_PATH_DEFAULT.parent),
        help="Root output directory (default: ../eye_mri_assets).",
    )
    parser.add_argument(
        "--subject", default=None,
        help="Subject ID. Inferred from filename if omitted. Ignored with --batch.",
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Process all .nii.gz files in --seg_dir.",
    )
    parser.add_argument(
        "--smooth_iterations", type=int, default=20,
        help="Laplacian smoothing iterations (default 20; 0 to disable).",
    )
    parser.add_argument(
        "--upsample", type=int, default=1,
        help="Integer upsample factor before marching cubes (default 1 = no upsampling).",
    )
    # Optional provenance metadata written into meta.json
    parser.add_argument("--sex",     default=None, help="Subject sex: male | female | unknown")
    parser.add_argument("--age",     type=int, default=None, help="Subject age in years")
    parser.add_argument("--scanner", default=None, help="MRI scanner description")
    args = parser.parse_args()

    seg_dir  = Path(args.seg_dir)
    out_dir  = Path(args.out_dir)
    manifest_path = out_dir / "manifest.json"

    extra_meta: dict[str, Any] = {}
    if args.sex:     extra_meta["sex"]     = args.sex
    if args.age:     extra_meta["age"]     = args.age
    if args.scanner: extra_meta["scanner"] = args.scanner

    manifest = load_manifest(manifest_path)

    if args.batch:
        seg_files = sorted(seg_dir.glob("*.nii.gz"))
        if not seg_files:
            parser.error(f"No .nii.gz files found in {seg_dir}")
        for seg_file in seg_files:
            # nnU-Net output names can be:
            #   sub001.nii.gz
            #   sub001_0000.nii.gz (input copy — skip these)
            name = seg_file.stem.replace(".nii", "")
            if name.endswith("_0000"):
                continue  # skip input copies that might be in same dir
            subject_id = name
            entry = process_subject(
                seg_path=seg_file,
                out_dir=out_dir,
                subject_id=subject_id,
                smooth_iterations=args.smooth_iterations,
                upsample=args.upsample,
                extra_meta=extra_meta or None,
            )
            manifest["subjects"][subject_id] = entry
    else:
        seg_files = sorted(seg_dir.glob("*.nii.gz"))
        # Filter out input files (_0000.nii.gz)
        seg_files = [f for f in seg_files if not f.stem.replace(".nii", "").endswith("_0000")]
        if not seg_files:
            parser.error(f"No segmentation .nii.gz files found in {seg_dir}")

        if args.subject:
            # Find a specific file
            matches = [f for f in seg_files if args.subject in f.name]
            if not matches:
                parser.error(f"No file matching subject '{args.subject}' in {seg_dir}")
            seg_file = matches[0]
            subject_id = args.subject
        else:
            seg_file   = seg_files[0]
            subject_id = seg_file.stem.replace(".nii", "")

        entry = process_subject(
            seg_path=seg_file,
            out_dir=out_dir,
            subject_id=subject_id,
            smooth_iterations=args.smooth_iterations,
            upsample=args.upsample,
            extra_meta=extra_meta or None,
        )
        manifest["subjects"][subject_id] = entry

    save_manifest(manifest, manifest_path)
    print(f"\nManifest updated: {manifest_path}")
    print(f"Total subjects in manifest: {len(manifest['subjects'])}")


if __name__ == "__main__":
    main()
