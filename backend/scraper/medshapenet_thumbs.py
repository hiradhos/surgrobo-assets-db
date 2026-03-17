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


def _render_png(mesh_path: Path, out_path: Path, size: tuple[int, int]) -> None:
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
        # Pink material for visual consistency
        baseColorFactor=(0.94, 0.42, 0.72, 1.0),
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
            _render_png(local_path, out_path, size)
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
