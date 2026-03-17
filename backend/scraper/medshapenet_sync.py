"""
medshapenet_sync.py — Download MedShapeNet Core datasets and build a manifest.

Uses the MedShapeNet Python API (from MedShapeNet package) to download datasets
into MEDSHAPENET_ASSETS_DIR, then scans local files to build a manifest for the
scraper and generates preview images for the frontend.

Usage:
  python -m backend.scraper.medshapenet_sync
  python -m backend.scraper.medshapenet_sync --datasets "medshapenetcore/ASOCA,medshapenetcore/AVT"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from . import config
from .anatomy_client import (
    _infer_body_part,
    _infer_condition,
    _infer_creation_method,
    _infer_organ_system,
)

log = logging.getLogger(__name__)

_ASSET_EXTS = {".stl", ".obj", ".ply", ".glb", ".gltf"}
_COLOR_PALETTE = [
    "#06b6d4", "#10b981", "#f59e0b", "#ec4899",
    "#3b82f6", "#ef4444", "#84cc16", "#a855f7",
]

_DEFAULT_DATASETS = [
    "medshapenetcore/3DTeethSeg",
    "medshapenetcore/ASOCA",
    "medshapenetcore/AVT",
    "medshapenetcore/AutoImplantCraniotomy",
    "medshapenetcore/CoronaryArteries",
    "medshapenetcore/FLARE",
    "medshapenetcore/FaceVR",
    "medshapenetcore/KITS",
    "medshapenetcore/PULMONARY",
    "medshapenetcore/SurgicalInstruments",
    "medshapenetcore/ThoracicAorta_Saitta",
    "medshapenetcore/ToothFairy",
]


@dataclass
class ManifestRecord:
    record_id: str
    source_collection: str
    name: str
    description: str
    body_part: str
    organ_system: str
    age_group: str
    sex: str
    condition_type: str
    creation_method: str
    file_types: list[str]
    download_url: str
    preview_url: str
    license: str
    tags: list[str]
    authors: list[str]
    year: int | None
    local_path: str


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug or "item"


def _hash_color(seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    idx = int(digest[:4], 16) % len(_COLOR_PALETTE)
    return _COLOR_PALETTE[idx]


def _preview_svg(title: str, subtitle: str, color: str) -> str:
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_sub = subtitle.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"640\" height=\"360\" viewBox=\"0 0 640 360\">"
        "<defs>"
        "<linearGradient id=\"g\" x1=\"0\" x2=\"1\" y1=\"0\" y2=\"1\">"
        f"<stop offset=\"0%\" stop-color=\"{color}\" stop-opacity=\"0.35\" />"
        "<stop offset=\"100%\" stop-color=\"#0b1324\" stop-opacity=\"0.95\" />"
        "</linearGradient>"
        "</defs>"
        "<rect width=\"640\" height=\"360\" fill=\"url(#g)\" />"
        "<rect x=\"24\" y=\"24\" width=\"592\" height=\"312\" rx=\"16\" fill=\"#0b1324\" opacity=\"0.75\" />"
        f"<text x=\"48\" y=\"120\" fill=\"#e5e7eb\" font-family=\"Arial, sans-serif\" font-size=\"28\" font-weight=\"700\">{safe_title}</text>"
        f"<text x=\"48\" y=\"160\" fill=\"#94a3b8\" font-family=\"Arial, sans-serif\" font-size=\"16\">{safe_sub}</text>"
        "<text x=\"48\" y=\"305\" fill=\"#22d3ee\" font-family=\"Arial, sans-serif\" font-size=\"12\" letter-spacing=\"2\">MEDSHAPENET 2.0</text>"
        "</svg>"
    )


def _load_medshapenet():
    try:
        from MedShapeNet import MedShapeNet  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Failed to import MedShapeNet. Ensure the MedShapeNet package is installed."
        ) from exc
    return MedShapeNet


def _init_client(base_dir: Path):
    MedShapeNet = _load_medshapenet()

    for kwargs in (
        {"download_dir": str(base_dir)},
        {"download_path": str(base_dir)},
        {"root": str(base_dir)},
        {"base_dir": str(base_dir)},
        {"storage_dir": str(base_dir)},
        {},
    ):
        try:
            return MedShapeNet(**kwargs)
        except TypeError:
            continue
    return MedShapeNet()


def _call_download_dataset(client, dataset_name: str, base_dir: Path) -> None:
    try:
        import inspect

        sig = inspect.signature(client.download_dataset)
        params = sig.parameters
        kwargs = {}
        if "file_path" in params:
            kwargs["file_path"] = str(base_dir)
        if "download_path" in params:
            kwargs["download_path"] = str(base_dir)
        if "download_dir" in params:
            kwargs["download_dir"] = str(base_dir)
        if "output_dir" in params:
            kwargs["output_dir"] = str(base_dir)
        if "dataset_name" in params:
            kwargs["dataset_name"] = dataset_name
            client.download_dataset(**kwargs)
        else:
            client.download_dataset(dataset_name, **kwargs)
    except Exception as exc:
        raise RuntimeError(f"MedShapeNet download_dataset failed for {dataset_name}: {exc}") from exc


def _call_dataset_files(client, dataset_name: str) -> list[str]:
    try:
        items = client.dataset_files(dataset_name)
    except Exception as exc:
        log.warning("medshapenet: dataset_files failed for %s: %s", dataset_name, exc)
        return []
    if isinstance(items, list):
        out: list[str] = []
        for item in items:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for key in ("object_name", "name", "key", "path", "file"):
                    if item.get(key):
                        out.append(str(item[key]))
                        break
        return out
    return []


def _call_download_file(client, dataset_name: str, object_name: str, dest_dir: Path) -> None:
    try:
        import inspect

        sig = inspect.signature(client.download_file)
        params = sig.parameters
        kwargs = {}
        if "file_path" in params:
            kwargs["file_path"] = str(dest_dir)
        if "download_path" in params:
            kwargs["download_path"] = str(dest_dir)
        if "download_dir" in params:
            kwargs["download_dir"] = str(dest_dir)
        if "output_dir" in params:
            kwargs["output_dir"] = str(dest_dir)
        if "dataset_name" in params:
            kwargs["dataset_name"] = dataset_name
            kwargs["object_name"] = object_name
            client.download_file(**kwargs)
        else:
            client.download_file(dataset_name, object_name, **kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"MedShapeNet download_file failed for {dataset_name}/{object_name}: {exc}"
        ) from exc


def _iter_asset_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in _ASSET_EXTS:
            files.append(path)
    return files


def _build_record(rel_path: Path, local_path: Path, preview_base_url: str) -> ManifestRecord:
    stem = rel_path.stem
    ext = rel_path.suffix.lower()
    parts = [p for p in rel_path.parts if p not in ("", ".")]
    label = stem.replace("_", " ").replace("-", " ")
    folder_hint = " / ".join(parts[-4:-1]) if len(parts) >= 2 else "MedShapeNet"
    combined = f"{label} {folder_hint} {stem}"

    record_slug = _slugify(str(rel_path.with_suffix("")))
    record_id = f"medshapenet:{record_slug}"

    tags = ["medshapenet", "medical-shapes", "segmentation", "ct"]
    for part in parts[-4:-1]:
        tag = _slugify(part)
        if tag and tag not in tags:
            tags.append(tag)

    preview_name = record_id.replace(":", "_") + ".svg"
    preview_url = f"{preview_base_url.rstrip('/')}/{preview_name}"
    download_url = f"/medshapenet_assets/{rel_path.as_posix()}"

    creation = _infer_creation_method(combined)
    if creation == "unknown":
        creation = "ct-scan"

    return ManifestRecord(
        record_id=record_id,
        source_collection="medshapenet",
        name=label,
        description=(
            f"MedShapeNet 2.0 structure '{label}' ({folder_hint}). "
            "Large-scale medical shape dataset derived from CT/MRI segmentations."
        ),
        body_part=_infer_body_part(combined),
        organ_system=_infer_organ_system(combined),
        age_group="adult",
        sex="unknown",
        condition_type=_infer_condition(combined),
        creation_method=creation,
        file_types=[ext.replace(".", "").upper()],
        download_url=download_url,
        preview_url=preview_url,
        license="CC BY 4.0",
        tags=tags[:10],
        authors=[],
        year=None,
        local_path=str(local_path),
    )


def _write_preview(preview_dir: Path, record: ManifestRecord) -> None:
    preview_name = record.record_id.replace(":", "_") + ".svg"
    out_path = preview_dir / preview_name
    if out_path.exists():
        return
    preview_dir.mkdir(parents=True, exist_ok=True)
    color = _hash_color(record.record_id)
    subtitle = record.body_part or record.organ_system or "MedShapeNet"
    out_path.write_text(_preview_svg(record.name, subtitle, color), encoding="utf-8")


def _records_from_files(files: Iterable[Path], root: Path) -> list[ManifestRecord]:
    records: list[ManifestRecord] = []
    seen: set[str] = set()
    for path in files:
        rel_path = path.relative_to(root)
        record = _build_record(rel_path, path, config.MEDSHAPENET_PREVIEW_BASE_URL)
        if record.record_id in seen:
            continue
        seen.add(record.record_id)
        _write_preview(config.MEDSHAPENET_PREVIEW_DIR, record)
        records.append(record)
    return records


def _parse_dataset_list(raw: str | None) -> list[str]:
    if not raw:
        return _DEFAULT_DATASETS
    items = [i.strip() for i in raw.split(",") if i.strip()]
    return items or _DEFAULT_DATASETS


def _dataset_slug(dataset_name: str) -> str:
    slug = dataset_name.split("/")[-1]
    return _slugify(slug)


def _flat_name(dataset_name: str, rel_path: Path) -> str:
    return rel_path.name


def _flatten_dataset(base_dir: Path, dataset_name: str) -> None:
    candidates = [
        base_dir / dataset_name,
        base_dir / dataset_name.split("/")[-1],
    ]
    for root in candidates:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _ASSET_EXTS:
                continue
            rel = path.relative_to(root)
            flat_path = base_dir / _flat_name(dataset_name, rel)
            flat_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(flat_path))
        # Best-effort cleanup of empty dirs.
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            if not dirnames and not filenames:
                try:
                    Path(dirpath).rmdir()
                except OSError:
                    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Download MedShapeNet datasets and build manifest")
    parser.add_argument("--datasets", default="", help="Comma-separated dataset names to download")
    parser.add_argument("--skip-download", action="store_true", help="Skip download, rebuild manifest only")
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resume by downloading only missing files when possible",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    base_dir = config.MEDSHAPENET_ASSETS_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    datasets = _parse_dataset_list(args.datasets)

    if not args.skip_download:
        client = _init_client(base_dir)
        for name in datasets:
            log.info("Syncing MedShapeNet dataset: %s", name)
            if args.resume:
                files = _call_dataset_files(client, name)
                if files:
                    missing = 0
                    for obj in files:
                        rel = Path(obj)
                        flat_path = base_dir / _flat_name(name, rel)
                        nested_path = base_dir / rel
                        if flat_path.exists() and flat_path.stat().st_size > 0:
                            continue
                        if nested_path.exists() and nested_path.stat().st_size > 0:
                            # Move nested file into flat layout for consistency.
                            flat_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(nested_path), str(flat_path))
                            try:
                                nested_path.parent.rmdir()
                            except OSError:
                                pass
                            continue
                        missing += 1
                        _call_download_file(client, name, obj, base_dir)
                        # After download, normalize to flat layout if needed.
                        if nested_path.exists() and nested_path.stat().st_size > 0:
                            flat_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(nested_path), str(flat_path))
                            try:
                                nested_path.parent.rmdir()
                            except OSError:
                                pass
                    if missing == 0:
                        log.info("medshapenet: dataset already complete: %s", name)
                        _flatten_dataset(base_dir, name)
                        continue
                    _flatten_dataset(base_dir, name)
                else:
                    log.info("medshapenet: no file listing for %s; falling back", name)
            log.info("Downloading MedShapeNet dataset: %s", name)
            _call_download_dataset(client, name, base_dir)
            _flatten_dataset(base_dir, name)

    files = _iter_asset_files(base_dir)
    log.info("Discovered %d MedShapeNet files in %s", len(files), base_dir)
    records = _records_from_files(files, base_dir)

    manifest_out = config.MEDSHAPENET_MANIFEST_PATH
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(
        json.dumps([asdict(r) for r in records], indent=2),
        encoding="utf-8",
    )
    log.info("Wrote manifest with %d records → %s", len(records), manifest_out)


if __name__ == "__main__":
    main()
