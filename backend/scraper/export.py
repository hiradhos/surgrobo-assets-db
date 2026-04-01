"""
Export the netter.db assets + anatomy_records tables to public/db-assets.json
for the frontend.

Called automatically at the end of each scrape run.

Output record shape (both GitHub-sourced and anatomy-database-sourced entries
share the same JSON schema so the frontend handles them uniformly):

  id             — "db-<n>" for GitHub assets, "ana-<n>" for anatomy records
  sourceType     — "arxiv" | "github" | "atlas-database"
  sourceCollection — e.g. "humanatlas" | "medshapenet" | null
  name, description, fileTypes, license, downloadUrl, addedAt, thumbnailColor
  githubRepo, githubStars   — null for anatomy records
  arxivId, arxivTitle       — null for anatomy records
  authors, year, tags
  patientType               — adult | pediatric | neonatal | phantom | generic
  organSystem               — cardiac | hepatobiliary | … | general
  bodyPart                  — specific organ name, e.g. "liver"
  sex                       — male | female | unknown
  conditionType             — healthy | tumor | fracture | defect | variant | pathologic | unknown
  creationMethod            — ct-scan | mri | photogrammetry | synthetic | anatomist | cadaver | unknown
  surgicalSystem            — generic (anatomy records) or inferred
  rlFrameworks              — []
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

# Repo root is three levels up from this file (backend/scraper/export.py)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUT_PATH = _REPO_ROOT / "public" / "db-assets.json"

# Keywords that indicate an atlas-database record is OR infrastructure, not anatomy
_ANATOMY_INSTRUMENT_KEYWORDS: frozenset[str] = frozenset({
    'trocar', 'needle', 'forceps', 'catheter', 'suture', 'stapler',
    'retractor', 'clamp', 'scissors', 'scalpel', 'cannula', 'clipper',
    'clip applier', 'dissector', 'grasper', 'hook', 'electrocautery',
    'cautery', 'electrosurgical', 'probe', 'stent', 'drain', 'port',
    'syringe', 'pill', 'tablet', 'capsule', 'medication', 'drug',
    'surgical tool', 'surgical instrument', 'laparoscopic instrument',
    'surgical equipment', 'hospital bed', 'surgical table', 'drape',
    'phantom', 'manikin', 'mannequin', 'endoscope', 'laparoscope',
    'speculum', 'dilator', 'spreader', 'scope', 'bottle', 'vial',
    'bipolar', 'monopolar', 'electrode', 'burr', 'drill', 'saw',
    'mallet', 'chisel', 'osteotome', 'curette', 'elevator', 'rasp',
    'impactor', 'reamer', 'rod', 'screw', 'plate', 'implant',
    'prosthesis', 'prosthetic',
})


def _classify_anatomy_category(name: str, description: str, tags: list[str]) -> str:
    """Return 'anatomical-model' or 'or-infrastructure' for atlas-database records."""
    text = ' '.join([name or '', description or ''] + (tags or [])).lower()
    if any(kw in text for kw in _ANATOMY_INSTRUMENT_KEYWORDS):
        return 'or-infrastructure'
    return 'anatomical-model'


_COLORS = [
    "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b",
    "#ec4899", "#3b82f6", "#ef4444", "#84cc16",
    "#f97316", "#a855f7", "#14b8a6", "#eab308",
    "#64748b", "#0ea5e9", "#d946ef", "#22c55e",
]

_FT_MAP = {
    "GLB": "GLTF", "GLTF": "GLTF",
    "USD": "USD", "USDA": "USD", "USDC": "USD",
    "OBJ": "OBJ", "STL": "STL", "URDF": "URDF",
    "FBX": "FBX", "PLY": "PLY", "SDF": "SDF",
    "DAE": "DAE", "MJCF": "MJCF",
}


_COLLECTION_CITATIONS: dict[str, str] = {
    # Confirmed by user
    "medshapenet": (
        "Li, J. et al., 2023. MedShapeNet - A Large-Scale Dataset of 3D Medical Shapes "
        "for Computer Vision. arXiv preprint arXiv.2308.16139."
    ),
    # HuBMAP Human Reference Atlas 3D CCF — canonical Sci Data paper
    "humanatlas": (
        "Börner, K. et al., 2023. Anatomical structures, cell types and biomarkers "
        "of the Human Reference Atlas. Scientific Data, 10, 272."
    ),
    # BodyParts3D — DBCLS/Mitsuhiro Hayashi; original RIKEN BodyParts3D project
    "bodyparts3d": (
        "Mitsuhiro, H. et al., 2008. BodyParts3D: 3D structure database for anatomical concepts. "
        "Nucleic Acids Research, 36(suppl_1), D662–D666."
    ),
}

# Maps Sketchfab license label → (short name, CC license URL)
_SKETCHFAB_LICENSE_MAP: dict[str, tuple[str, str]] = {
    "CC Attribution":                          ("CC BY 4.0",        "https://creativecommons.org/licenses/by/4.0/"),
    "CC Attribution-ShareAlike":               ("CC BY-SA 4.0",     "https://creativecommons.org/licenses/by-sa/4.0/"),
    "CC Attribution-NoDerivs":                 ("CC BY-ND 4.0",     "https://creativecommons.org/licenses/by-nd/4.0/"),
    "CC Attribution-NonCommercial":            ("CC BY-NC 4.0",     "https://creativecommons.org/licenses/by-nc/4.0/"),
    "CC Attribution-NonCommercial-ShareAlike": ("CC BY-NC-SA 4.0",  "https://creativecommons.org/licenses/by-nc-sa/4.0/"),
    "CC Attribution-NonCommercial-NoDerivs":   ("CC BY-NC-ND 4.0",  "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
}

# Per-platform citation templates for sources that lack canonical papers.
# These are formatted as: prefix + optional author + " " + model_name + suffix.
_PLATFORM_CITATION_TEMPLATES: dict[str, tuple[str, str]] = {
    # "{author}. {name}. NIH 3D Print Exchange. {url}"
    "nih3d":       ("{author}{name}. NIH 3D Print Exchange. {url}",),
    # "{author}. {name}. AnatomyTool.org. {url}"
    "anatomytool": ("{author}{name}. AnatomyTool.org. {url}",),
    # "{author}. {name}. Embodi3D. {url}"
    "embodi3d":    ("{author}{name}. Embodi3D. {url}",),
    # "{author}. {name}. Thingiverse. {url}"
    "thingiverse": ("{author}{name}. Thingiverse. {url}",),
}


def _make_sketchfab_citation(name: str, authors: list[str], download_url: str, license: str) -> str:
    """
    "Model Title" by Author Name (model_url) is licensed under CC BY 4.0 (license_url).
    Follows Sketchfab attribution requirements.
    """
    license_short, license_url = _SKETCHFAB_LICENSE_MAP.get(
        license, (license or "Unknown License", "https://creativecommons.org/licenses/")
    )
    author = authors[0] if authors else "Unknown Author"
    return (
        f'"{name}" by {author} ({download_url}) '
        f"is licensed under {license_short} ({license_url})."
    )


def _make_platform_citation(
    collection: str, name: str, authors: list[str], download_url: str
) -> str:
    """
    Generate a platform attribution citation for sources that don't have academic papers
    (NIH 3D, AnatomyTool, Embodi3D, Thingiverse). Format: Author. Title. Platform. URL.
    """
    template_tuple = _PLATFORM_CITATION_TEMPLATES.get(collection)
    if not template_tuple:
        return _make_citation(name=name, authors=authors, year=None, arxiv_id=None)
    template = template_tuple[0]
    author_str = f"{authors[0]}. " if authors else ""
    return template.format(author=author_str, name=name, url=download_url)


def _format_author(full_name: str) -> str:
    """Format 'First Last' → 'Last, F.' for citation use."""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        last = parts[-1]
        initials = " ".join(p[0] + "." for p in parts[:-1])
        return f"{last}, {initials}"
    return full_name


def _make_citation(
    name: str,
    authors: list[str],
    year: int | None,
    arxiv_id: str | None,
) -> str:
    """Build an APA-style citation string (no URLs)."""
    if authors:
        first_author = _format_author(authors[0])
        author_str = f"{first_author} et al." if len(authors) > 1 else first_author
    else:
        author_str = "Unknown"

    year_str = str(year) if year else "n.d."

    if arxiv_id:
        return f"{author_str}, {year_str}. {name}. arXiv preprint arXiv.{arxiv_id}."
    else:
        return f"{author_str}, {year_str}. {name}."


def _norm_ft(ft: str) -> str:
    return _FT_MAP.get(ft.upper(), ft.upper())


def export_assets(db_path: Path = config.DB_PATH, out_path: Path = _OUT_PATH) -> int:
    """
    Read all assets + anatomy records from the database and write them to
    `out_path` as a single JSON array.  Returns the number of records written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # ── Vetting decisions ─────────────────────────────────────────────────────
    vet_map: dict[str, dict] = {}
    try:
        vet_rows = conn.execute("SELECT * FROM asset_vetting").fetchall()
        for r in vet_rows:
            vet_map[r["source_key"]] = dict(r)
    except sqlite3.OperationalError:
        vet_map = {}

    # ── GitHub-sourced assets ──────────────────────────────────────────────────
    rows = conn.execute("""
        SELECT a.repo_full_name, a.file_type, a.stars, a.license, a.discovered_at,
               a.body_part, a.condition_type, a.creation_method, a.sex,
               r.url, r.description, r.category, r.category_reason,
               p.title, p.authors, p.arxiv_id, p.published_at
        FROM assets a
        JOIN repos r ON r.full_name = a.repo_full_name
        LEFT JOIN papers p ON p.paper_id = a.paper_id
        ORDER BY a.repo_full_name, a.id
    """).fetchall()

    by_repo: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_repo[r["repo_full_name"]].append(dict(r))

    assets: list[dict] = []
    color_idx = 0

    for repo_full_name, repo_rows in by_repo.items():
        vet = vet_map.get(f"github:{repo_full_name}")
        if vet and vet.get("decision") == "reject":
            continue
        first = repo_rows[0]

        seen_ft: list[str] = []
        for r in repo_rows:
            ft = _norm_ft(r["file_type"])
            if ft not in seen_ft:
                seen_ft.append(ft)

        authors: list[str] = []
        if first["authors"]:
            try:
                authors = json.loads(first["authors"])
            except Exception:
                pass

        year = 2024
        if first["published_at"]:
            try:
                year = int(str(first["published_at"])[:4])
            except Exception:
                pass

        corrected_tags: list[str] = []
        if vet and vet.get("corrected_tags"):
            try:
                corrected_tags = json.loads(vet.get("corrected_tags") or "[]")
            except Exception:
                corrected_tags = []

        name = first["title"] or repo_full_name.split("/")[-1]
        if vet and vet.get("corrected_name"):
            name = vet.get("corrected_name")

        body_part = first["body_part"] or ""
        organ_system = "general"
        sex = first["sex"] or "unknown"
        condition_type = first["condition_type"] or "unknown"
        creation_method = first["creation_method"] or "unknown"
        patient_type = "generic"

        if vet:
            body_part = vet.get("corrected_body_part") or body_part
            organ_system = vet.get("corrected_organ_system") or organ_system
            sex = vet.get("corrected_sex") or sex
            condition_type = vet.get("corrected_condition") or condition_type
            creation_method = vet.get("corrected_creation") or creation_method
            if vet.get("corrected_age_group"):
                patient_type = _map_age_group(vet.get("corrected_age_group"))

        citation = _make_citation(
            name=name,
            authors=authors,
            year=year,
            arxiv_id=first["arxiv_id"],
        )

        assets.append({
            "id": f"db-{len(assets) + 1}",
            "name": name,
            "description": first["description"] or "",
            "fileTypes": seen_ft,
            "previewUrl": None,
            "sourceKey": f"github:{repo_full_name}",
            "citation": citation,
            # Anatomy metadata — populated by LLM classifier where available
            "patientType": patient_type,
            "organSystem": organ_system,
            "bodyPart": body_part,
            "sex": sex,
            "conditionType": condition_type,
            "creationMethod": creation_method,
            "surgicalSystem": "generic",
            "rlFrameworks": [],
            # Source info
            "sourceType": "arxiv" if first["arxiv_id"] else "github",
            "sourceCollection": None,
            "category": (vet.get("corrected_category") if vet else None) or first["category"] or None,
            "arxivId": first["arxiv_id"] or None,
            "arxivTitle": first["title"] if first["arxiv_id"] else None,
            "githubRepo": repo_full_name,
            "githubStars": first["stars"],
            # Provenance
            "authors": authors,
            "year": year,
            "tags": corrected_tags,
            "downloadUrl": first["url"],
            "license": first["license"] or None,
            "addedAt": str(first["discovered_at"])[:10] if first["discovered_at"] else "",
            "thumbnailColor": _COLORS[color_idx % len(_COLORS)],
        })
        color_idx += 1

    # ── Anatomy-database records ───────────────────────────────────────────────
    try:
        ana_rows = conn.execute("SELECT * FROM anatomy_records ORDER BY source_collection, name").fetchall()
    except sqlite3.OperationalError:
        ana_rows = []  # table not yet created in old DB

    conn.close()

    for rec in ana_rows:
        vet = vet_map.get(f"anatomy:{rec['record_id']}")
        if vet and vet.get("decision") == "reject":
            continue
        file_types_raw: list[str] = []
        try:
            file_types_raw = json.loads(rec["file_types"] or "[]")
        except Exception:
            pass
        seen_ft = [_norm_ft(ft) for ft in file_types_raw]
        seen_ft = list(dict.fromkeys(seen_ft))  # deduplicate preserving order

        tags: list[str] = []
        try:
            tags = json.loads(rec["tags"] or "[]")
        except Exception:
            pass

        authors: list[str] = []
        try:
            authors = json.loads(rec["authors"] or "[]")
        except Exception:
            pass

        if vet and vet.get("corrected_tags"):
            try:
                tags = json.loads(vet.get("corrected_tags") or "[]")
            except Exception:
                pass

        name = rec["name"]
        if vet and vet.get("corrected_name"):
            name = vet.get("corrected_name")

        organ_system = vet.get("corrected_organ_system") if vet else None
        body_part = vet.get("corrected_body_part") if vet else None
        sex = vet.get("corrected_sex") if vet else None
        condition = vet.get("corrected_condition") if vet else None
        creation = vet.get("corrected_creation") if vet else None
        age_group = vet.get("corrected_age_group") if vet else None
        source_collection = vet.get("corrected_source") if vet else None

        # Citation: prefer stored value, else generate based on collection type
        collection_key = source_collection or rec["source_collection"]
        stored_citation = rec["citation"] if "citation" in rec.keys() else ""
        citation = stored_citation or _COLLECTION_CITATIONS.get(collection_key, "")
        if not citation:
            if collection_key == "sketchfab":
                citation = _make_sketchfab_citation(
                    name=name,
                    authors=authors,
                    download_url=rec["download_url"] or "",
                    license=rec["license"] or "",
                )
            elif collection_key in _PLATFORM_CITATION_TEMPLATES:
                citation = _make_platform_citation(
                    collection=collection_key,
                    name=name,
                    authors=authors,
                    download_url=rec["download_url"] or "",
                )
            else:
                citation = _make_citation(
                    name=name, authors=authors, year=rec["year"], arxiv_id=None,
                )

        assets.append({
            "id": f"ana-{len(assets) + 1}",
            "name": name,
            "description": rec["description"] or "",
            "fileTypes": seen_ft,
            "previewUrl": (rec["preview_url"] or "").replace(".svg", ".png") or None,
            "sourceKey": f"anatomy:{rec['record_id']}",
            # Anatomy metadata — structured, from the source
            "patientType": _map_age_group(age_group or rec["age_group"]),
            "organSystem": organ_system or rec["organ_system"] or "general",
            "bodyPart": body_part or rec["body_part"] or "",
            "sex": sex or rec["sex"] or "unknown",
            "conditionType": condition or rec["condition_type"] or "healthy",
            "creationMethod": creation or rec["creation_method"] or "unknown",
            "surgicalSystem": "generic",
            "rlFrameworks": [],
            # Source info
            "sourceType": "atlas-database",
            "sourceCollection": source_collection or rec["source_collection"],
            "category": (
                (vet.get("corrected_category") if vet else None)
                or _classify_anatomy_category(name, rec["description"] or "", tags)
            ),
            "arxivId": None,
            "arxivTitle": None,
            "githubRepo": None,
            "githubStars": None,
            # Provenance
            "authors": authors,
            "year": rec["year"],
            "tags": tags,
            "downloadUrl": rec["download_url"] or None,
            "license": rec["license"] or None,
            "citation": citation or None,
            "addedAt": str(rec["discovered_at"])[:10] if rec["discovered_at"] else "",
            "thumbnailColor": _COLORS[color_idx % len(_COLORS)],
        })
        color_idx += 1

    out_path.write_text(json.dumps(assets, indent=2))
    log.info(
        "Exported %d records (%d GitHub, %d anatomy) → %s",
        len(assets),
        len(by_repo),
        len(ana_rows),
        out_path,
    )
    return len(assets)


def _map_age_group(age_group: str | None) -> str:
    """Convert anatomy_records.age_group → frontend PatientType."""
    mapping = {
        "adult": "adult",
        "pediatric": "pediatric",
        "fetal": "neonatal",   # closest frontend equivalent
        "generic": "generic",
    }
    return mapping.get(age_group or "adult", "generic")
