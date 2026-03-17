"""
anatomy_client.py — Scrapers for dedicated 3D human anatomy databases.

Each scraper function returns a list[AnatomyRecord].  Failures are logged and
return an empty list so one broken source never aborts the whole pipeline.

Implemented sources
───────────────────
  humanatlas   — Human Reference Atlas 3D library (HuBMAP/CCF)
                 https://humanatlas.io/3d-reference-library
  nih3d        — NIH 3D Print Exchange
                 https://3d.nih.gov/collections/hra
  medshapenet  — MedShapeNet 2.0 (GLARKI/MedShapeNet2.0 on GitHub)
                 https://github.com/GLARKI/MedShapeNet2.0
  bodyparts3d  — BodyParts3D (Kevin-Mattheus-Moerman/BodyParts3D on GitHub)
                 https://github.com/Kevin-Mattheus-Moerman/BodyParts3D
  anatomytool  — AnatomyTool.org open 3D model library
                 https://anatomytool.org/open3dmodel
  sketchfab    — Sketchfab public anatomy/medical models (public API)
                 https://sketchfab.com

Adding a new source
───────────────────
  1. Write `scrape_<source>(session, known_ids) -> list[AnatomyRecord]`.
  2. Add it to ANATOMY_SCRAPERS at the bottom of this file.
  3. Optionally add a config toggle in config.py under ANATOMY_SOURCES.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import requests

from . import config
from .models import AnatomyRecord

log = logging.getLogger(__name__)

_UA = "SurgSimDB/1.0 (anatomy scraper; github.com/surgrobo/surgrobo-assets-db)"
_TIMEOUT = 15

# ── Helpers ────────────────────────────────────────────────────────────────────

def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    return s


def _get(session: requests.Session, url: str, **kwargs) -> requests.Response | None:
    """GET with timeout + error logging.  Returns None on any failure."""
    try:
        r = session.get(url, timeout=_TIMEOUT, **kwargs)
        r.raise_for_status()
        return r
    except Exception as exc:
        log.warning("GET %s failed: %s", url, exc)
        return None


def _github_get(session: requests.Session, path: str) -> dict | list | None:
    """GitHub REST API GET (authenticated if GITHUB_TOKEN is set)."""
    headers = {"Accept": "application/vnd.github+json"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    r = _get(session, f"https://api.github.com{path}", headers=headers)
    if r is None:
        return None
    try:
        return r.json()
    except Exception:
        return None


def _get_json(session: requests.Session, url: str, **kwargs) -> dict | list | None:
    r = _get(session, url, **kwargs)
    if r is None:
        return None
    try:
        return r.json()
    except Exception:
        return None


def _clean_html(text: str, max_len: int = 500) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def _extract_download_links(html: str, exts: tuple[str, ...]) -> list[str]:
    pattern = r'href="([^"]+\.(?:' + "|".join(exts) + r'))"'
    return re.findall(pattern, html, re.IGNORECASE)


# Maps common body-part keywords → canonical organ_system values used by the frontend.
_ORGAN_SYSTEM_MAP: dict[str, str] = {
    # cardiac
    "heart": "cardiac", "aorta": "cardiac", "coronary": "cardiac",
    "pericardium": "cardiac", "ventricle": "cardiac", "atrium": "cardiac",
    "myocardium": "cardiac", "cardiac": "cardiac",
    # hepatobiliary
    "liver": "hepatobiliary", "gallbladder": "hepatobiliary",
    "bile duct": "hepatobiliary", "hepatic": "hepatobiliary",
    "pancreas": "hepatobiliary",
    # urologic
    "kidney": "urologic", "ureter": "urologic", "bladder": "urologic",
    "prostate": "urologic", "urethra": "urologic", "renal": "urologic",
    # gynecologic
    "uterus": "gynecologic", "ovary": "gynecologic", "fallopian": "gynecologic",
    "cervix": "gynecologic", "vagina": "gynecologic", "placenta": "gynecologic",
    # colorectal
    "colon": "colorectal", "rectum": "colorectal", "sigmoid": "colorectal",
    "cecum": "colorectal", "appendix": "colorectal", "bowel": "colorectal",
    "intestine": "gastrointestinal", "stomach": "gastrointestinal",
    "esophagus": "gastrointestinal", "duodenum": "gastrointestinal",
    # thoracic
    "lung": "thoracic", "bronchus": "thoracic", "trachea": "thoracic",
    "diaphragm": "thoracic", "pleura": "thoracic", "pulmonary": "thoracic",
    # neurologic
    "brain": "neurologic", "cerebral": "neurologic", "spinal cord": "neurologic",
    "cerebellum": "neurologic", "skull": "neurologic", "dura": "neurologic",
    "meninges": "neurologic", "nerve": "neurologic",
    # orthopedic
    "femur": "orthopedic", "tibia": "orthopedic", "fibula": "orthopedic",
    "humerus": "orthopedic", "radius": "orthopedic", "ulna": "orthopedic",
    "spine": "orthopedic", "vertebra": "orthopedic", "pelvis": "orthopedic",
    "hip": "orthopedic", "knee": "orthopedic", "bone": "orthopedic",
    "cartilage": "orthopedic", "scapula": "orthopedic", "rib": "orthopedic",
    "mandible": "orthopedic", "clavicle": "orthopedic",
    # vascular
    "artery": "vascular", "vein": "vascular", "vessel": "vascular",
    "aneurysm": "vascular", "carotid": "vascular", "femoral artery": "vascular",
    # head / neck
    "thyroid": "general", "larynx": "general", "ear": "general",
    "eye": "general", "orbit": "general",
    # skin / soft tissue
    "muscle": "general", "skin": "general", "fat": "general",
    "adipose": "general", "fascia": "general",
}


def _infer_organ_system(text: str) -> str:
    """Guess organ_system from a free-text description or name."""
    lower = text.lower()
    for keyword, system in _ORGAN_SYSTEM_MAP.items():
        if keyword in lower:
            return system
    return "general"


def _infer_body_part(text: str) -> str:
    """Extract a canonical body part name from text."""
    lower = text.lower()
    # Check longer / more-specific terms first
    sorted_keys = sorted(_ORGAN_SYSTEM_MAP.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in lower:
            return keyword
    return ""


def _infer_creation_method(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("ct scan", "ct-scan", "computed tomography", "dicom", "ct image")):
        return "ct-scan"
    if any(k in lower for k in ("mri", "magnetic resonance", "mr imaging")):
        return "mri"
    if any(k in lower for k in ("photogrammetry", "photoscan", "3d scan", "structured light")):
        return "photogrammetry"
    if any(k in lower for k in ("synthetic", "procedural", "computer-generated", "simulated")):
        return "synthetic"
    if any(k in lower for k in ("cadaver", "cadaveric", "dissection", "plastinated")):
        return "cadaver"
    if any(k in lower for k in ("anatomist", "manual", "illustration", "artist", "sculpt")):
        return "anatomist"
    return "unknown"


def _infer_condition(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("tumor", "cancer", "neoplasm", "malignant", "carcinoma", "sarcoma")):
        return "tumor"
    if any(k in lower for k in ("fracture", "fractured", "break")):
        return "fracture"
    if any(k in lower for k in ("defect", "malformation", "congenital", "abnormal", "anomaly")):
        return "defect"
    if any(k in lower for k in ("patholog", "disease", "disorder", "lesion")):
        return "pathologic"
    if any(k in lower for k in ("variant", "variation", "atypical")):
        return "variant"
    if any(k in lower for k in ("healthy", "normal", "reference", "atlas", "standard")):
        return "healthy"
    return "healthy"  # default for atlas/reference databases


def _infer_age_group(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("fetal", "fetus", "embryo")):
        return "fetal"
    if any(k in lower for k in ("pediatric", "child", "infant", "neonatal", "newborn")):
        return "pediatric"
    return "adult"


def _infer_sex(text: str) -> str:
    lower = text.lower()
    # "VH_F" = Visible Human Female, "VH_M" = Visible Human Male
    if re.search(r"\bvh[_\s-]?f\b|female|woman|women|\bf\b\s+\d", lower):
        return "female"
    if re.search(r"\bvh[_\s-]?m\b|male|man|men|\bm\b\s+\d", lower):
        return "male"
    return "unknown"


# ── Source: HumanAtlas.io (HRA CCF 3D Reference Library) ──────────────────────

def scrape_humanatlas(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Fetch 3D organ reference models from the HuBMAP CCF 3D Reference Library.

    Data source: the ccf-releases GitHub repo (preferred) + fallback to the
    older ccf-3d-reference-library repo if needed.
    Models include male/female Visible Human organ meshes in GLTF/OBJ format.
    """
    records: list[AnatomyRecord] = []

    preferred_repo = "hubmapconsortium/ccf-releases"
    fallback_repo = "hubmapconsortium/ccf-3d-reference-library"
    version_year = {"v1.2": 2022, "v1.1": 2021, "v1.0": 2021}

    def scan_repo(repo: str) -> list[AnatomyRecord]:
        branch = "main"
        tree = _github_get(session, f"/repos/{repo}/git/trees/{branch}?recursive=1")
        if not tree or not isinstance(tree, dict):
            branch = "master"
            tree = _github_get(session, f"/repos/{repo}/git/trees/{branch}?recursive=1")
        if not tree or not isinstance(tree, dict):
            return []

        paths = [n.get("path", "") for n in tree.get("tree", []) if isinstance(n, dict)]
        versions = sorted(
            {p.split("/")[0] for p in paths if p.startswith("v")},
            reverse=True,
        )
        preferred_versions = [v for v in ("v1.2", "v1.1", "v1.0") if v in versions]
        use_versions = preferred_versions or (versions[:1] if versions else [""])

        found: list[AnatomyRecord] = []
        for path in paths:
            if "/models/" not in path:
                continue
            if use_versions[0] and not path.startswith(f"{use_versions[0]}/"):
                continue
            filename = path.split("/")[-1]
            ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else ""
            if ext not in {"OBJ", "GLB", "GLTF", "STL", "PLY", "FBX"}:
                continue
            base = filename.rsplit(".", 1)[0]
            record_id = f"humanatlas:{base}"
            if record_id in known_ids:
                continue

            sex = _infer_sex(base)
            body_part = _infer_body_part(base.replace("_", " "))
            organ_system = _infer_organ_system(base.replace("_", " "))
            display_name = (
                base.replace("VH_F_", "").replace("VH_M_", "").replace("_", " ").strip()
            )
            version = path.split("/")[0] if path.startswith("v") else ""
            download_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"

            found.append(AnatomyRecord(
                record_id=record_id,
                source_collection="humanatlas",
                name=f"HRA: {display_name}" if display_name else f"HRA: {base}",
                description=(
                    "3D reference organ model from the HuBMAP Human Reference Atlas."
                    + (f" Release {version}." if version else "")
                ),
                body_part=body_part,
                organ_system=organ_system,
                age_group="adult",
                sex=sex,
                condition_type="healthy",
                creation_method="ct-scan",
                file_types=[ext if ext != "GLB" else "GLTF"],
                download_url=download_url,
                license="CC BY 4.0",
                tags=["hra", "visible-human", "reference-atlas", "hubmap"],
                year=version_year.get(version),
            ))
        return found

    records = scan_repo(preferred_repo)
    if not records:
        log.warning("humanatlas: could not scan %s — falling back", preferred_repo)
        records = scan_repo(fallback_repo)

    log.info("humanatlas: %d new records", len(records))
    return records


# ── Source: NIH 3D Print Exchange ──────────────────────────────────────────────

def scrape_nih3d(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Scrape the NIH 3D Print Exchange for human anatomy models.

    The NIH 3D Print Exchange (3d.nih.gov) hosts thousands of biomedical 3D models.
    The public API has changed several times; this scraper tries a set of known
    endpoints and also parses the discover HTML as a last resort.
    """
    records: list[AnatomyRecord] = []
    seen_ids: set[str] = set()

    def _ingest_items(items: list[dict]) -> None:
        for item in items:
            uid = item.get("id") or item.get("uid") or item.get("accession_id", "") or item.get("uuid", "")
            if not uid:
                continue
            uid = str(uid)
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            record_id = f"nih3d:{uid}"
            if record_id in known_ids:
                continue

            name = item.get("title") or item.get("name", f"NIH 3D Model {uid}")
            description = item.get("description") or item.get("summary", "")
            download_url = (
                item.get("download_url")
                or item.get("stl_file")
                or item.get("url")
                or f"https://3d.nih.gov/entries/{uid}"
            )
            preview_url = item.get("thumbnail") or item.get("preview_image", "")
            license_str = item.get("license", "")
            tags_raw = item.get("tags") or item.get("keywords", []) or []
            tags = tags_raw if isinstance(tags_raw, list) else [
                t.strip() for t in str(tags_raw).split(",") if t.strip()
            ]

            combined = f"{name} {description} {' '.join(tags)}"
            records.append(AnatomyRecord(
                record_id=record_id,
                source_collection="nih3d",
                name=name,
                description=description,
                body_part=_infer_body_part(combined),
                organ_system=_infer_organ_system(combined),
                age_group=_infer_age_group(combined),
                sex=_infer_sex(combined),
                condition_type=_infer_condition(combined),
                creation_method=_infer_creation_method(combined),
                file_types=["STL"],  # NIH 3D Print Exchange is primarily STL
                download_url=download_url,
                preview_url=preview_url,
                license=license_str,
                tags=tags[:10],
            ))

    endpoints = [
        ("https://3d.nih.gov/api/v1/discover", {"collection": "40,42,41", "page": 1}),
        ("https://3d.nih.gov/api/v1/entries", {"collection": "40,42,41", "page": 1}),
        ("https://3d.nih.gov/api/entries", {"collection": "40,42,41", "page": 1}),
        ("https://3d.nih.gov/api/v1/search", {"q": "anatomy", "page": 1}),
        ("https://3d.nih.gov/api/entries", {"category": "Human Anatomy", "limit": 100}),
    ]

    for base_url, params in endpoints:
        for page in range(1, 6):
            params["page"] = page
            data = _get_json(session, base_url, params=params)
            if data is None:
                break
            if isinstance(data, list):
                items = [i for i in data if isinstance(i, dict)]
            elif isinstance(data, dict):
                items = data.get("results") or data.get("entries") or data.get("items") or []
                items = [i for i in items if isinstance(i, dict)]
            else:
                items = []
            if not items:
                break
            _ingest_items(items)
            time.sleep(1)
        if records:
            break

    # HTML fallback: parse discover page if API is blocked
    if not records:
        discover_url = "https://3d.nih.gov/discover?collection=40,42,41"
        r = _get(session, discover_url)
        if r is not None:
            html = r.text
            # Try to extract embedded JSON blobs with entry metadata
            json_candidates = re.findall(r'(\{.*?\})', html, re.DOTALL)
            for blob in json_candidates:
                if '"title"' not in blob or '"id"' not in blob:
                    continue
                try:
                    data = json.loads(blob)
                except Exception:
                    continue
                items = data.get("results") or data.get("entries") or data.get("items") or []
                if isinstance(items, list) and items:
                    _ingest_items([i for i in items if isinstance(i, dict)])
                    break

    log.info("nih3d: %d new records", len(records))
    return records


# ── Source: MedShapeNet 2.0 ────────────────────────────────────────────────────

def scrape_medshapenet(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Scrape MedShapeNet 2.0 — a large-scale medical shape dataset hosted on GitHub.

    The repo contains thousands of medical 3D shapes (OBJ/STL) organized by anatomy,
    with accompanying metadata CSVs.
    """
    records: list[AnatomyRecord] = []
    manifest_path = config.MEDSHAPENET_MANIFEST_PATH
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("medshapenet: failed to read manifest %s", manifest_path)
            payload = []

        if isinstance(payload, dict):
            items = payload.get("records") or payload.get("items") or []
        else:
            items = payload if isinstance(payload, list) else []

        for item in items:
            if not isinstance(item, dict):
                continue
            record_id = item.get("record_id") or item.get("id")
            if not record_id or record_id in known_ids:
                continue
            records.append(AnatomyRecord(
                record_id=record_id,
                source_collection=item.get("source_collection", "medshapenet"),
                name=item.get("name", "MedShapeNet 2.0 Asset"),
                description=item.get("description", ""),
                body_part=item.get("body_part", ""),
                organ_system=item.get("organ_system", "general"),
                age_group=item.get("age_group", "adult"),
                sex=item.get("sex", "unknown"),
                condition_type=item.get("condition_type", "healthy"),
                creation_method=item.get("creation_method", "ct-scan"),
                file_types=item.get("file_types", []) or [],
                download_url=item.get("download_url", ""),
                preview_url=item.get("preview_url", ""),
                license=item.get("license", "CC BY 4.0"),
                tags=item.get("tags", []) or [],
                authors=item.get("authors", []) or [],
                year=item.get("year"),
            ))

        log.info("medshapenet: %d new records (manifest)", len(records))
        return records
    OWNER, REPO = "GLARKI", "MedShapeNet2.0"

    # Read the repo tree to discover anatomy categories
    tree = _github_get(session, f"/repos/{OWNER}/{REPO}/git/trees/main?recursive=1")
    if not tree or not isinstance(tree, dict):
        # Try 'master' branch
        tree = _github_get(session, f"/repos/{OWNER}/{REPO}/git/trees/master?recursive=1")
    if not tree or not isinstance(tree, dict):
        log.warning("medshapenet: could not fetch repo tree")
        return records

    # Look for a metadata CSV
    csv_path: str | None = None
    obj_paths: list[str] = []
    for node in tree.get("tree", []):
        path: str = node.get("path", "")
        if path.endswith(".csv") and ("metadata" in path.lower() or "label" in path.lower()):
            csv_path = path
        if path.lower().endswith(".obj") or path.lower().endswith(".stl"):
            obj_paths.append(path)

    # Try to parse metadata CSV for structured info
    category_records: dict[str, list[str]] = {}  # category → list of file paths
    if csv_path:
        raw_url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{csv_path}"
        r = _get(session, raw_url)
        if r:
            for line in r.text.splitlines()[1:]:  # skip header
                parts = line.split(",")
                if len(parts) >= 2:
                    category = parts[0].strip().strip('"')
                    if category:
                        category_records.setdefault(category, [])

    # If no CSV, infer categories from directory structure
    if not category_records:
        for path in obj_paths:
            parts = path.split("/")
            if len(parts) >= 2:
                category = parts[0]  # top-level directory = anatomy category
                category_records.setdefault(category, []).append(path)

    # Create one record per anatomy category (not per file — too many files)
    repo_url = f"https://github.com/{OWNER}/{REPO}"
    for category, paths in sorted(category_records.items()):
        record_id = f"medshapenet:{category.lower().replace(' ', '_')}"
        if record_id in known_ids:
            continue

        combined = category
        records.append(AnatomyRecord(
            record_id=record_id,
            source_collection="medshapenet",
            name=f"MedShapeNet 2.0: {category}",
            description=(
                f"Medical 3D shape collection for '{category}' from MedShapeNet 2.0 — "
                f"a large-scale benchmark dataset of medical shapes derived from CT/MRI segmentations. "
                f"Contains {len(paths)} models."
            ),
            body_part=_infer_body_part(combined),
            organ_system=_infer_organ_system(combined),
            age_group="adult",
            sex="unknown",
            condition_type=_infer_condition(combined),
            creation_method="ct-scan",  # MedShapeNet is primarily from CT segmentations
            file_types=["OBJ", "STL"],
            download_url=repo_url,
            license="CC BY 4.0",
            tags=["medshapenet", "medical-shapes", "segmentation", "ct"],
        ))

    log.info("medshapenet: %d new records (categories)", len(records))
    return records


# ── Source: BodyParts3D ────────────────────────────────────────────────────────

def scrape_bodyparts3d(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Scrape the BodyParts3D GitHub repository.

    BodyParts3D provides OBJ meshes of 3D human body part models derived from the
    Visible Human Project male dataset.  Each file is a discrete anatomical structure.
    """
    records: list[AnatomyRecord] = []
    OWNER, REPO = "Kevin-Mattheus-Moerman", "BodyParts3D"

    # Get repo metadata for license/description
    meta = _github_get(session, f"/repos/{OWNER}/{REPO}")
    repo_license = ""
    if meta and isinstance(meta, dict):
        lic = meta.get("license") or {}
        repo_license = lic.get("spdx_id", "") if isinstance(lic, dict) else ""

    # Scan the tree for OBJ files
    for branch in ("main", "master"):
        tree = _github_get(session, f"/repos/{OWNER}/{REPO}/git/trees/{branch}?recursive=1")
        if tree and isinstance(tree, dict):
            break
    else:
        log.warning("bodyparts3d: could not fetch repo tree")
        return records

    for node in tree.get("tree", []):
        path: str = node.get("path", "")
        if not path.lower().endswith(".obj"):
            continue

        filename = path.split("/")[-1]
        base = filename.rsplit(".", 1)[0]
        record_id = f"bodyparts3d:{base}"
        if record_id in known_ids:
            continue

        # BodyParts3D filenames encode anatomy: e.g. "Liver.obj", "FemurLeft.obj"
        display = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)  # CamelCase → words
        combined = display
        download_url = (
            f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{branch}/{path}"
        )
        records.append(AnatomyRecord(
            record_id=record_id,
            source_collection="bodyparts3d",
            name=f"BodyParts3D: {display}",
            description=(
                f"3D mesh of human '{display}' from the BodyParts3D dataset, "
                f"derived from the Visible Human Project male dataset."
            ),
            body_part=_infer_body_part(combined),
            organ_system=_infer_organ_system(combined),
            age_group="adult",
            sex="male",  # Visible Human Male source
            condition_type="healthy",
            creation_method="ct-scan",
            file_types=["OBJ"],
            download_url=download_url,
            license=repo_license or "CC BY 4.0",
            tags=["bodyparts3d", "visible-human", "anatomy", "mesh"],
        ))

    log.info("bodyparts3d: %d new records", len(records))
    return records


# ── Source: AnatomyTool.org ────────────────────────────────────────────────────

def scrape_anatomytool(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Scrape the open 3D model library at anatomytool.org/open3dmodel.

    AnatomyTool hosts curated anatomical 3D models from various contributors.
    We parse their listing pages to extract model metadata.
    """
    records: list[AnatomyRecord] = []

    # Primary model listings live under the "learn" and "create" sections.
    base_urls = [
        "https://anatomytool.org/open3dmodel",
        "https://anatomytool.org/open3dmodel-learn",
        "https://anatomytool.org/open3dmodel-create",
    ]
    pages_to_try = []
    for base_url in base_urls:
        pages_to_try.extend([base_url] + [f"{base_url}?page={i}" for i in range(1, 6)])

    seen_urls: set[str] = set()

    for page_url in pages_to_try:
        r = _get(session, page_url)
        if r is None:
            break

        html = r.text

        # Extract model card blocks.  AnatomyTool uses href="/node/<id>" patterns.
        node_links = re.findall(r'href="(/node/\d+)"', html)
        if not node_links:
            # Also capture direct asset links on the create/learn pages
            dl_links = _extract_download_links(
                html,
                ("zip", "glb", "gltf", "obj", "stl", "fbx", "dae"),
            )
            for link in dl_links:
                full = urljoin("https://anatomytool.org", link)
                base = full.split("/")[-1].rsplit(".", 1)[0]
                record_id = f"anatomytool:{base}"
                if record_id in known_ids:
                    continue
                name = base.replace("-", " ").replace("_", " ").strip()
                combined = name
                ext = link.rsplit(".", 1)[-1].upper()
                records.append(AnatomyRecord(
                    record_id=record_id,
                    source_collection="anatomytool",
                    name=name or f"AnatomyTool model {base}",
                    description="AnatomyTool open 3D model download.",
                    body_part=_infer_body_part(combined),
                    organ_system=_infer_organ_system(combined),
                    age_group=_infer_age_group(combined),
                    sex=_infer_sex(combined),
                    condition_type=_infer_condition(combined),
                    creation_method=_infer_creation_method(combined),
                    file_types=[ext],
                    download_url=full,
                    tags=["anatomytool", "anatomy"],
                ))
            continue

        for rel_link in set(node_links):
            full_url = f"https://anatomytool.org{rel_link}"
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            node_id = rel_link.strip("/").split("/")[-1]
            record_id = f"anatomytool:{node_id}"
            if record_id in known_ids:
                continue

            # Fetch the model page to get details
            time.sleep(0.5)
            detail = _get(session, full_url)
            if detail is None:
                continue

            detail_html = detail.text

            # Extract title
            title_m = re.search(
                r'<h1[^>]*class="[^"]*page-header[^"]*"[^>]*>([^<]+)</h1>', detail_html
            ) or re.search(r"<title>([^<|]+)", detail_html)
            name = title_m.group(1).strip() if title_m else f"AnatomyTool model {node_id}"

            # Extract description  (first paragraph after the header)
            desc_m = re.search(r'<div[^>]*class="[^"]*field-body[^"]*"[^>]*>(.*?)</div>', detail_html, re.DOTALL)
            description = _clean_html(desc_m.group(1) if desc_m else "")

            # Find download links for 3D files
            dl_links = _extract_download_links(
                detail_html,
                ("obj", "stl", "ply", "gltf", "glb", "fbx", "dae", "zip"),
            )
            download_url = urljoin("https://anatomytool.org", dl_links[0]) if dl_links else full_url
            file_exts = list({l.rsplit(".", 1)[-1].upper() for l in dl_links}) if dl_links else ["OBJ"]

            combined = f"{name} {description}"
            records.append(AnatomyRecord(
                record_id=record_id,
                source_collection="anatomytool",
                name=name,
                description=description,
                body_part=_infer_body_part(combined),
                organ_system=_infer_organ_system(combined),
                age_group=_infer_age_group(combined),
                sex=_infer_sex(combined),
                condition_type=_infer_condition(combined),
                creation_method=_infer_creation_method(combined),
                file_types=file_exts[:4],
                download_url=download_url,
                tags=["anatomytool", "anatomy"],
            ))

        time.sleep(1)

    log.info("anatomytool: %d new records", len(records))
    return records


# ── Source: Sketchfab (public anatomy search) ──────────────────────────────────

def scrape_sketchfab(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Search Sketchfab's public API for downloadable anatomical 3D models.

    Uses the public unauthenticated endpoint to search models tagged with
    anatomy/medical keywords.  Only downloadable models are included.
    """
    records: list[AnatomyRecord] = []

    # Sketchfab public search endpoint — no API key needed for read access
    search_tags = [
        "anatomy", "human-anatomy", "medical", "organ",
        "surgical-anatomy", "anatomical-model",
    ]

    seen_uids: set[str] = set()

    for tag in search_tags:
        url = "https://api.sketchfab.com/v3/models?" + urlencode({
            "type": "models",
            "tags": tag,
            "sort_by": "-likeCount",
            "count": 24,
            "downloadable": True,
        })

        while url:
            r = _get(session, url)
            if r is None:
                break
            try:
                data = r.json()
            except Exception:
                break

            for model in data.get("results", []):
                uid = model.get("uid", "")
                if not uid or uid in seen_uids:
                    continue
                seen_uids.add(uid)

                record_id = f"sketchfab:{uid}"
                if record_id in known_ids:
                    continue

                name = model.get("name", f"Sketchfab model {uid}")
                description = model.get("description", "")
                published = model.get("publishedAt", "")
                year = None
                if published:
                    try:
                        year = int(published[:4])
                    except Exception:
                        pass

                # License
                license_data = model.get("license") or {}
                license_str = license_data.get("label", "") if isinstance(license_data, dict) else ""

                # Tags
                raw_tags = [t.get("name", "") for t in model.get("tags", []) if isinstance(t, dict)]

                # Thumbnails
                thumbs = model.get("thumbnails") or {}
                images = thumbs.get("images", [])
                preview_url = images[0].get("url", "") if images else ""

                model_url = f"https://sketchfab.com/3d-models/{uid}"
                combined = f"{name} {description} {' '.join(raw_tags)}"

                records.append(AnatomyRecord(
                    record_id=record_id,
                    source_collection="sketchfab",
                    name=name,
                    description=description[:500],
                    body_part=_infer_body_part(combined),
                    organ_system=_infer_organ_system(combined),
                    age_group=_infer_age_group(combined),
                    sex=_infer_sex(combined),
                    condition_type=_infer_condition(combined),
                    creation_method=_infer_creation_method(combined),
                    file_types=["GLTF"],  # Sketchfab exports GLTF/GLB by default
                    download_url=model_url,
                    preview_url=preview_url,
                    license=license_str,
                    tags=raw_tags[:8],
                    year=year,
                ))

            # Follow pagination cursor
            url = data.get("next", "")  # type: ignore[assignment]
            if url:
                time.sleep(1)
            else:
                break

        time.sleep(2)

    log.info("sketchfab: %d new records", len(records))
    return records


# ── Source: Embodi3D ───────────────────────────────────────────────────────────

def scrape_embodi3d(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Scrape Embodi3D — a community platform for medical 3D models derived from
    anonymized medical imaging (CT/MRI → STL).
    https://www.embodi3d.com/files/category/0-all-free-medical-3d-printing-files/
    """
    records: list[AnatomyRecord] = []

    # Embodi3D uses an IPS Community Suite API, but it may be blocked (403).
    api_base = "https://www.embodi3d.com/api/core/search"
    params = {
        "type": "core_file",
        "tags": "anatomy",
        "perPage": 25,
        "page": 1,
    }

    for page in range(1, 4):
        params["page"] = page
        data = _get_json(session, api_base, params=params)
        if not isinstance(data, dict):
            break

        results = data.get("results", [])
        if not results:
            break

        for item in results:
            uid = str(item.get("id", ""))
            if not uid:
                continue
            record_id = f"embodi3d:{uid}"
            if record_id in known_ids:
                continue

            name = item.get("title", f"Embodi3D model {uid}")
            description = _clean_html(item.get("content", ""))
            url = item.get("url", f"https://www.embodi3d.com/files/file/{uid}")
            tags_raw = [t.get("name", "") for t in item.get("tags", []) if isinstance(t, dict)]
            combined = f"{name} {description} {' '.join(tags_raw)}"

            records.append(AnatomyRecord(
                record_id=record_id,
                source_collection="embodi3d",
                name=name,
                description=description,
                body_part=_infer_body_part(combined),
                organ_system=_infer_organ_system(combined),
                age_group=_infer_age_group(combined),
                sex=_infer_sex(combined),
                condition_type=_infer_condition(combined),
                creation_method="ct-scan",  # Embodi3D is primarily CT-derived
                file_types=["STL"],
                download_url=url,
                tags=tags_raw[:8],
            ))

        time.sleep(1.5)

    # HTML fallback if API is blocked
    if not records:
        list_pages = [
            "https://www.embodi3d.com/files/",
            "https://www.embodi3d.com/files/category/0-all-free-medical-3d-printing-files/",
        ]
        file_links: list[str] = []
        for page_url in list_pages:
            r = _get(session, page_url)
            if r is None:
                continue
            html = r.text
            links = re.findall(r'href="(/files/file/\d+[^"]*)"', html)
            for rel in links:
                full = urljoin("https://www.embodi3d.com", rel)
                if full not in file_links:
                    file_links.append(full)
            time.sleep(1)

        for full_url in file_links[:60]:
            r = _get(session, full_url)
            if r is None:
                continue
            html = r.text

            uid_match = re.search(r"/files/file/(\d+)", full_url)
            uid = uid_match.group(1) if uid_match else ""
            if not uid:
                continue
            record_id = f"embodi3d:{uid}"
            if record_id in known_ids:
                continue

            title_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html) or re.search(r"<title>([^<|]+)", html)
            name = title_m.group(1).strip() if title_m else f"Embodi3D model {uid}"

            desc_m = re.search(r'class="[^"]*ipsType_richText[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            description = _clean_html(desc_m.group(1) if desc_m else "")

            dl_links = _extract_download_links(html, ("stl", "obj", "zip", "gltf", "glb", "ply"))
            download_url = urljoin("https://www.embodi3d.com", dl_links[0]) if dl_links else full_url
            file_exts = list({l.rsplit(".", 1)[-1].upper() for l in dl_links}) if dl_links else ["STL"]

            tags = re.findall(r'href="[^"]*/tags/([^"/]+)"', html, re.IGNORECASE)
            tags = [t.replace("-", " ") for t in tags][:8]

            combined = f"{name} {description} {' '.join(tags)}"
            records.append(AnatomyRecord(
                record_id=record_id,
                source_collection="embodi3d",
                name=name,
                description=description,
                body_part=_infer_body_part(combined),
                organ_system=_infer_organ_system(combined),
                age_group=_infer_age_group(combined),
                sex=_infer_sex(combined),
                condition_type=_infer_condition(combined),
                creation_method="ct-scan",
                file_types=file_exts[:4],
                download_url=download_url,
                tags=tags,
            ))
            time.sleep(0.8)

    log.info("embodi3d: %d new records", len(records))
    return records


# ── Source: Thingiverse medical/anatomy search ─────────────────────────────────

def scrape_thingiverse(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Search Thingiverse for human anatomy 3D models via their public API.
    Focused on the 'medical' category with anatomy-specific search terms.
    """
    records: list[AnatomyRecord] = []

    tv_token = config.THINGIVERSE_TOKEN
    if not tv_token:
        log.info("thingiverse: no THINGIVERSE_TOKEN set — skipping")
        return records

    headers = {"Authorization": f"Bearer {tv_token}"}
    search_terms = ["human anatomy", "organ model", "bone anatomy", "surgical anatomy"]

    seen_ids: set[str] = set()
    for term in search_terms:
        url = "https://api.thingiverse.com/search/" + term + "?type=things&per_page=20&page=1"
        r = _get(session, url, headers=headers)
        if r is None:
            continue
        try:
            items = r.json()
        except Exception:
            continue
        if not isinstance(items, list):
            items = items.get("hits", []) if isinstance(items, dict) else []

        for item in items:
            tid = str(item.get("id", ""))
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)
            record_id = f"thingiverse:{tid}"
            if record_id in known_ids:
                continue

            name = item.get("name", f"Thingiverse {tid}")
            description = item.get("description", "")[:500]
            url_thing = item.get("public_url", f"https://www.thingiverse.com/thing:{tid}")
            tags = [t.get("name", "") for t in item.get("tags", []) if isinstance(t, dict)]
            combined = f"{name} {description} {' '.join(tags)}"

            records.append(AnatomyRecord(
                record_id=record_id,
                source_collection="thingiverse",
                name=name,
                description=description,
                body_part=_infer_body_part(combined),
                organ_system=_infer_organ_system(combined),
                age_group=_infer_age_group(combined),
                sex=_infer_sex(combined),
                condition_type=_infer_condition(combined),
                creation_method=_infer_creation_method(combined),
                file_types=["STL"],
                download_url=url_thing,
                tags=tags[:8],
            ))
        time.sleep(1)

    log.info("thingiverse: %d new records", len(records))
    return records


# ── Registry ───────────────────────────────────────────────────────────────────

# Map source_collection key → scraper function.
# Add new sources here to register them.
ANATOMY_SCRAPERS: dict[str, Any] = {
    "humanatlas":  scrape_humanatlas,
    "nih3d":       scrape_nih3d,
    "medshapenet": scrape_medshapenet,
    "bodyparts3d": scrape_bodyparts3d,
    "anatomytool": scrape_anatomytool,
    "sketchfab":   scrape_sketchfab,
    "embodi3d":    scrape_embodi3d,
    "thingiverse": scrape_thingiverse,
}


def scrape_all_anatomy_sources(known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Run all enabled anatomy scrapers and return the combined list of new records.

    Scrapers are enabled/disabled via config.ANATOMY_SOURCES.
    Each scraper failure is logged and skipped — one bad source never aborts the rest.
    """
    session = _session()
    all_records: list[AnatomyRecord] = []

    enabled = set(config.ANATOMY_SOURCES)  # e.g. {"humanatlas", "medshapenet", ...}
    if not enabled:
        log.info("anatomy: no sources enabled — skipping")
        return all_records

    for source_key, scraper_fn in ANATOMY_SCRAPERS.items():
        if source_key not in enabled:
            log.debug("anatomy: %s disabled — skipping", source_key)
            continue

        log.info("anatomy: scraping %s …", source_key)
        try:
            records = scraper_fn(session, known_ids)
            all_records.extend(records)
            # Update known_ids so later scrapers don't re-create duplicates
            for rec in records:
                known_ids.add(rec.record_id)
        except Exception as exc:
            log.error("anatomy: %s scraper failed: %s", source_key, exc, exc_info=True)

    log.info("anatomy: %d total new records from %d sources", len(all_records), len(enabled))
    return all_records
