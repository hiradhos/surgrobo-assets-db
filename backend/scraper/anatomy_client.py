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

    Data source: the ccf-3d-reference-library GitHub repo + HRA CDN.
    Models include male/female Visible Human organ meshes in GLTF/OBJ format.
    """
    records: list[AnatomyRecord] = []

    # Try the GitHub releases API first — stable and machine-readable
    releases = _github_get(session, "/repos/hubmapconsortium/ccf-3d-reference-library/releases")
    if not releases or not isinstance(releases, list):
        log.warning("humanatlas: could not fetch GitHub releases")
        return records

    latest = releases[0] if releases else {}
    release_tag = latest.get("tag_name", "unknown")
    release_year = None
    if latest.get("published_at"):
        try:
            release_year = int(latest["published_at"][:4])
        except Exception:
            pass

    assets_api = latest.get("assets", [])
    log.info("humanatlas: release %s has %d downloadable assets", release_tag, len(assets_api))

    for asset in assets_api:
        asset_name = asset.get("name", "")
        download_url = asset.get("browser_download_url", "")
        if not download_url:
            continue

        # Infer file type from extension
        ext = asset_name.rsplit(".", 1)[-1].upper() if "." in asset_name else ""
        if ext not in {"OBJ", "GLB", "GLTF", "STL", "PLY"}:
            continue

        # Strip extension for display name; e.g. "VH_F_Liver.obj" → "VH_F_Liver"
        base = asset_name.rsplit(".", 1)[0]
        record_id = f"humanatlas:{base}"
        if record_id in known_ids:
            continue

        # Visible Human uses naming like VH_F_Liver, VH_M_Heart
        # Also HRA uses <organ>.<ext> directly
        sex = _infer_sex(base)
        body_part = _infer_body_part(base.replace("_", " "))
        organ_system = _infer_organ_system(base.replace("_", " "))
        display_name = (
            base.replace("VH_F_", "")
                .replace("VH_M_", "")
                .replace("_", " ")
                .strip()
        )

        records.append(AnatomyRecord(
            record_id=record_id,
            source_collection="humanatlas",
            name=f"HRA: {display_name}" if display_name else f"HRA: {base}",
            description=(
                f"3D reference organ model from the HuBMAP Human Reference Atlas "
                f"(release {release_tag}). Visible Human Project source data."
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
            year=release_year,
        ))

    # If no packaged release assets, fall back to scanning the repo tree
    if not records:
        log.info("humanatlas: no release assets found, scanning repo tree …")
        tree_data = _github_get(
            session,
            "/repos/hubmapconsortium/ccf-3d-reference-library/git/trees/main?recursive=1",
        )
        if tree_data and isinstance(tree_data, dict):
            for node in tree_data.get("tree", []):
                path = node.get("path", "")
                ext = path.rsplit(".", 1)[-1].upper() if "." in path else ""
                if ext not in {"OBJ", "GLB", "GLTF", "STL"}:
                    continue
                filename = path.split("/")[-1]
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
                download_url = (
                    f"https://raw.githubusercontent.com/hubmapconsortium/"
                    f"ccf-3d-reference-library/main/{path}"
                )
                records.append(AnatomyRecord(
                    record_id=record_id,
                    source_collection="humanatlas",
                    name=f"HRA: {display_name}" if display_name else f"HRA: {base}",
                    description=(
                        "3D reference organ model from the HuBMAP Human Reference Atlas."
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
                ))

    log.info("humanatlas: %d new records", len(records))
    return records


# ── Source: NIH 3D Print Exchange ──────────────────────────────────────────────

def scrape_nih3d(session: requests.Session, known_ids: set[str]) -> list[AnatomyRecord]:
    """
    Scrape the NIH 3D Print Exchange for human anatomy models.

    The NIH 3D Print Exchange (3d.nih.gov) hosts thousands of biomedical 3D models.
    We query their search API filtered by the 'Human Anatomy' and 'HRA' categories.
    """
    records: list[AnatomyRecord] = []

    # NIH 3D has a JSON search endpoint used by their frontend
    search_queries = [
        {"category": "Human Anatomy", "limit": 100},
        {"category": "Human Anatomy", "limit": 100, "offset": 100},
        {"collection": "hra", "limit": 50},
    ]

    seen_ids: set[str] = set()

    for params in search_queries:
        # Try the documented-ish API endpoint pattern
        url = "https://3d.nih.gov/api/entries/?" + urlencode(params)
        r = _get(session, url)
        if r is None:
            # Try alternate endpoint format
            url2 = "https://3d.nih.gov/entries?" + urlencode({**params, "format": "json"})
            r = _get(session, url2)
        if r is None:
            continue

        try:
            data = r.json()
        except Exception:
            continue

        # Handle both {"results": [...]} and plain list responses
        if isinstance(data, dict):
            items = data.get("results", data.get("entries", data.get("models", [])))
        elif isinstance(data, list):
            items = data
        else:
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            uid = item.get("id") or item.get("uid") or item.get("accession_id", "")
            if not uid:
                continue
            if str(uid) in seen_ids:
                continue
            seen_ids.add(str(uid))

            record_id = f"nih3d:{uid}"
            if record_id in known_ids:
                continue

            name = item.get("title") or item.get("name", f"NIH 3D Model {uid}")
            description = item.get("description") or item.get("summary", "")
            download_url = (
                item.get("download_url")
                or item.get("stl_file")
                or f"https://3d.nih.gov/entries/{uid}"
            )
            preview_url = item.get("thumbnail") or item.get("preview_image", "")
            license_str = item.get("license", "")
            tags_raw = item.get("tags") or item.get("keywords", [])
            tags = tags_raw if isinstance(tags_raw, list) else [t.strip() for t in str(tags_raw).split(",") if t.strip()]

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

        time.sleep(1)

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

    # Try to fetch their model listing; they use a WordPress-style pagination
    base_url = "https://anatomytool.org/open3dmodel"
    pages_to_try = [base_url] + [f"{base_url}?page={i}" for i in range(1, 6)]

    seen_urls: set[str] = set()

    for page_url in pages_to_try:
        r = _get(session, page_url)
        if r is None:
            break

        html = r.text

        # Extract model card blocks.  AnatomyTool uses href="/node/<id>" patterns.
        node_links = re.findall(r'href="(/node/\d+)"', html)
        if not node_links and page_url != base_url:
            break  # no more pages

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
            description = ""
            if desc_m:
                description = re.sub(r"<[^>]+>", " ", desc_m.group(1)).strip()[:500]

            # Find download links for 3D files
            dl_links = re.findall(
                r'href="([^"]+\.(?:obj|stl|ply|gltf|glb|fbx|dae))"',
                detail_html,
                re.IGNORECASE,
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

    # Embodi3D uses an IPS Community Suite API
    api_base = "https://www.embodi3d.com/api/core/search"
    params = {
        "type": "core_file",
        "tags": "anatomy",
        "perPage": 25,
        "page": 1,
    }

    for page in range(1, 6):
        params["page"] = page
        r = _get(session, api_base, params=params)
        if r is None:
            break
        try:
            data = r.json()
        except Exception:
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
            description = re.sub(r"<[^>]+>", " ", item.get("content", ""))[:500]
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
