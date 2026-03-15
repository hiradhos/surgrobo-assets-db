"""
Export the surgsim.db assets + anatomy_records tables to public/db-assets.json
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

        assets.append({
            "id": f"db-{len(assets) + 1}",
            "name": first["title"] or repo_full_name.split("/")[-1],
            "description": first["description"] or "",
            "fileTypes": seen_ft,
            # Anatomy metadata — populated by LLM classifier where available
            "patientType": "generic",
            "organSystem": "general",
            "bodyPart": first["body_part"] or "",
            "sex": first["sex"] or "unknown",
            "conditionType": first["condition_type"] or "unknown",
            "creationMethod": first["creation_method"] or "unknown",
            "surgicalSystem": "generic",
            "rlFrameworks": [],
            # Source info
            "sourceType": "arxiv" if first["arxiv_id"] else "github",
            "sourceCollection": None,
            "category": first["category"] or None,
            "arxivId": first["arxiv_id"] or None,
            "arxivTitle": first["title"] if first["arxiv_id"] else None,
            "githubRepo": repo_full_name,
            "githubStars": first["stars"],
            # Provenance
            "authors": authors,
            "year": year,
            "tags": [],
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

        assets.append({
            "id": f"ana-{len(assets) + 1}",
            "name": rec["name"],
            "description": rec["description"] or "",
            "fileTypes": seen_ft,
            # Anatomy metadata — structured, from the source
            "patientType": _map_age_group(rec["age_group"]),
            "organSystem": rec["organ_system"] or "general",
            "bodyPart": rec["body_part"] or "",
            "sex": rec["sex"] or "unknown",
            "conditionType": rec["condition_type"] or "healthy",
            "creationMethod": rec["creation_method"] or "unknown",
            "surgicalSystem": "generic",
            "rlFrameworks": [],
            # Source info
            "sourceType": "atlas-database",
            "sourceCollection": rec["source_collection"],
            "category": "anatomical-model",
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
