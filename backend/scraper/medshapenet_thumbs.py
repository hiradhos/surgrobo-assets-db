"""
Generate real PNG thumbnails for MedShapeNet mesh assets.

Reads medshapenet_assets/manifest.json and writes PNGs to public/medshapenet_previews/.
Also updates manifest preview_url entries to point to the PNGs.

Usage:
  python -m backend.scraper.medshapenet_thumbs
  python -m backend.scraper.medshapenet_thumbs --force
  python -m backend.scraper.medshapenet_thumbs --limit 200
  PYOPENGL_PLATFORM=egl python -m backend.scraper.medshapenet_thumbs
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import config

log = logging.getLogger(__name__)

_ASSET_EXTS = {".stl", ".obj", ".ply", ".glb", ".gltf"}
_COLOR_PINK = (0.94, 0.42, 0.72, 1.0)
_COLOR_GRAY = (0.55, 0.57, 0.60, 1.0)
_COLOR_RED = (0.86, 0.20, 0.20, 1.0)
_COLOR_BLUE = (0.15, 0.45, 0.82, 1.0)
_SUFFIX_COLOR = {
    "teeth": _COLOR_PINK,
    "coronaryartery": _COLOR_RED,
    "thoracicaortawithbranches": _COLOR_RED,
    "artery": _COLOR_RED,
    "aorta": _COLOR_RED,
    "aorticvesseltree": _COLOR_RED,
    "vein": _COLOR_BLUE,
    "cava": _COLOR_BLUE,
    "surgicalinstrument": _COLOR_GRAY,
    "craniotomy": _COLOR_GRAY,
    "airway": _COLOR_PINK,
    "inferioralveolarnerve": _COLOR_PINK,
    "kidney": _COLOR_PINK,
    "cyst": _COLOR_PINK,
    "esophagus": _COLOR_PINK,
    "stomach": _COLOR_PINK,
    "duodenum": _COLOR_PINK,
    "pancreas": _COLOR_PINK,
    "liver": _COLOR_PINK,
    "spleen": _COLOR_PINK,
    "gallbladder": _COLOR_PINK,
    "gland": _COLOR_PINK,
    "facevr": _COLOR_PINK,
}


@dataclass
class _ThumbStats:
    total: int = 0
    rendered: int = 0
    skipped: int = 0
    failed: int = 0


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("records") or payload.get("items") or []
    else:
        items = payload if isinstance(payload, list) else []
    return [i for i in items if isinstance(i, dict)]


def _write_manifest(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def _normalize_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(v) for v in value if v is not None)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _extract_suffix(record: dict[str, Any]) -> str:
    for key in ("local_path", "download_url"):
        value = record.get(key)
        if not value:
            continue
        name = Path(str(value)).name
        stem = Path(name).stem
        if "_" in stem:
            return stem.rsplit("_", 1)[1].lower()
        return stem.lower()
    record_id = record.get("record_id") or ""
    if "_" in record_id:
        return record_id.rsplit("_", 1)[1].lower()
    return record_id.lower()


def _pick_thumbnail_color(record: dict[str, Any]) -> tuple[float, float, float, float]:
    suffix = _extract_suffix(record)
    if suffix in _SUFFIX_COLOR:
        return _SUFFIX_COLOR[suffix]

    text = _normalize_text(
        record.get("name"),
        record.get("record_id"),
        record.get("body_part"),
        record.get("organ_system"),
        record.get("tags"),
    )

    if "vein" in text:
        return _COLOR_BLUE
    if "surgicalinstrument" in text or "surgical instrument" in text or "instrument" in text:
        return _COLOR_GRAY
    if "tooth" in text or "teeth" in text:
        return _COLOR_PINK
    if "kidney" in text or "renal" in text or "esophagus" in text or "brain" in text:
        return _COLOR_PINK
    if "heart" in text or "cardiac" in text or "aorta" in text or "artery" in text or "vessel" in text:
        return _COLOR_RED
    return _COLOR_PINK


def _look_at(eye, target, up):
    import numpy as np

    forward = target - eye
    forward = forward / (np.linalg.norm(forward) + 1e-9)
    right = np.cross(forward, up)
    right = right / (np.linalg.norm(right) + 1e-9)
    true_up = np.cross(right, forward)

    mat = np.eye(4, dtype=float)
    mat[:3, 0] = right
    mat[:3, 1] = true_up
    mat[:3, 2] = -forward
    mat[:3, 3] = eye
    return mat


def _render_png(
    mesh_path: Path,
    out_path: Path,
    size: tuple[int, int],
    base_color: tuple[float, float, float, float],
) -> None:
    import numpy as np
    import pyrender
    import trimesh
    from PIL import Image

    mesh = trimesh.load(mesh_path, force="mesh", skip_materials=True)
    if isinstance(mesh, trimesh.Scene):
        if not mesh.geometry:
            raise ValueError("empty scene")
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    if mesh.is_empty:
        raise ValueError("empty mesh")

    # Some cleanup helpers are version-dependent in trimesh.
    for fn_name in (
        "remove_degenerate_faces",
        "remove_unreferenced_vertices",
        "remove_infinite_values",
        "remove_duplicate_faces",
        "remove_duplicate_vertices",
    ):
        fn = getattr(mesh, fn_name, None)
        if callable(fn):
            fn()

    mesh.apply_translation(-mesh.centroid)
    scale = float(max(mesh.extents))
    if scale > 0:
        mesh.apply_scale(1.0 / scale)

    material = pyrender.MetallicRoughnessMaterial(
        baseColorFactor=base_color,
        metallicFactor=0.15,
        roughnessFactor=0.65,
    )
    pm = pyrender.Mesh.from_trimesh(mesh, material=material, smooth=True)

    # White background for clean thumbnails
    scene = pyrender.Scene(bg_color=[255, 255, 255, 255], ambient_light=[0.22, 0.22, 0.25, 1.0])
    scene.add(pm)

    # Camera placement
    radius = float(np.linalg.norm(mesh.extents)) * 0.5
    dist = max(2.4 * radius, 1.6)
    eye = np.array([dist, dist * 0.9, dist * 0.8], dtype=float)
    target = np.array([0.0, 0.0, 0.0], dtype=float)
    up = np.array([0.0, 0.0, 1.0], dtype=float)

    cam = pyrender.PerspectiveCamera(yfov=np.pi / 4.0)
    scene.add(cam, pose=_look_at(eye, target, up))

    # Lighting
    light = pyrender.DirectionalLight(color=np.ones(3), intensity=2.2)
    scene.add(light, pose=_look_at(eye, target, up))
    scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=1.2),
              pose=_look_at(np.array([-dist, dist, dist * 0.6]), target, up))
    scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=0.8),
              pose=_look_at(np.array([dist, -dist, dist * 0.4]), target, up))

    renderer = pyrender.OffscreenRenderer(viewport_width=size[0], viewport_height=size[1])
    color, _ = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)
    renderer.delete()

    img = Image.fromarray(color, mode="RGBA")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def generate_thumbnails(
    manifest_path: Path,
    preview_dir: Path,
    preview_base_url: str,
    size: tuple[int, int] = (640, 360),
    force: bool = False,
    limit: int | None = None,
) -> _ThumbStats:
    records = _load_manifest(manifest_path)
    stats = _ThumbStats(total=len(records))
    started = time.time()
    last_log = started

    for item in records:
        if limit is not None and stats.rendered >= limit:
            break
        local_path = Path(item.get("local_path", ""))
        if not local_path.is_file():
            stats.skipped += 1
            continue
        if local_path.suffix.lower() not in _ASSET_EXTS:
            stats.skipped += 1
            continue

        record_id = item.get("record_id") or item.get("id")
        if not record_id:
            stats.skipped += 1
            continue

        preview_name = record_id.replace(":", "_") + ".png"
        out_path = preview_dir / preview_name
        if out_path.exists() and not force:
            item["preview_url"] = f"{preview_base_url.rstrip('/')}/{preview_name}"
            stats.skipped += 1
            continue

        try:
            base_color = _pick_thumbnail_color(item)
            _render_png(local_path, out_path, size, base_color)
            item["preview_url"] = f"{preview_base_url.rstrip('/')}/{preview_name}"
            stats.rendered += 1
        except Exception as exc:
            stats.failed += 1
            log.warning("thumb failed: %s (%s)", local_path, exc)
        finally:
            processed = stats.rendered + stats.skipped + stats.failed
            now = time.time()
            if processed % 100 == 0 or (now - last_log) > 15:
                rate = processed / max(now - started, 1e-6)
                log.info(
                    "thumbs progress: %d/%d (rendered=%d skipped=%d failed=%d) rate=%.1f/s",
                    processed,
                    stats.total,
                    stats.rendered,
                    stats.skipped,
                    stats.failed,
                    rate,
                )
                last_log = now

    _write_manifest(manifest_path, records)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MedShapeNet PNG thumbnails")
    parser.add_argument("--force", action="store_true", help="Re-render existing PNGs")
    parser.add_argument("--limit", type=int, default=None, help="Render only N thumbnails")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument(
        "--pyopengl-platform",
        default="",
        help="Set PYOPENGL_PLATFORM (egl/osmesa/glx).",
    )
    args = parser.parse_args()

    if args.pyopengl_platform:
        os.environ["PYOPENGL_PLATFORM"] = args.pyopengl_platform

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    manifest_path = config.MEDSHAPENET_MANIFEST_PATH
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    stats = generate_thumbnails(
        manifest_path=manifest_path,
        preview_dir=config.MEDSHAPENET_PREVIEW_DIR,
        preview_base_url=config.MEDSHAPENET_PREVIEW_BASE_URL,
        size=(args.width, args.height),
        force=args.force,
        limit=args.limit,
    )

    log.info(
        "thumbs: total=%d rendered=%d skipped=%d failed=%d",
        stats.total,
        stats.rendered,
        stats.skipped,
        stats.failed,
    )


if __name__ == "__main__":
    main()
