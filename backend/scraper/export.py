"""
Export the surgsim.db assets table to public/db-assets.json for the frontend.

Called automatically at the end of each scrape run.
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
]

_FT_MAP = {
    "GLB": "GLTF", "GLTF": "GLTF",
    "USD": "USD", "USDA": "USD", "USDC": "USD",
    "OBJ": "OBJ", "STL": "STL", "URDF": "URDF",
    "FBX": "FBX", "PLY": "PLY", "SDF": "SDF",
    "DAE": "DAE", "MJCF": "MJCF",
}


def export_assets(db_path: Path = config.DB_PATH, out_path: Path = _OUT_PATH) -> int:
    """
    Read all assets from the database and write them to `out_path` as JSON.
    Returns the number of asset records written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT a.repo_full_name, a.file_type, a.stars, a.license, a.discovered_at,
               r.url, r.description,
               p.title, p.authors, p.arxiv_id, p.published_at
        FROM assets a
        JOIN repos r ON r.full_name = a.repo_full_name
        LEFT JOIN papers p ON p.paper_id = a.paper_id
        ORDER BY a.repo_full_name, a.id
    """).fetchall()
    conn.close()

    by_repo: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_repo[r["repo_full_name"]].append(dict(r))

    assets = []
    for idx, (repo_full_name, repo_rows) in enumerate(by_repo.items()):
        first = repo_rows[0]

        seen_ft: list[str] = []
        for r in repo_rows:
            ft = _FT_MAP.get(r["file_type"].upper(), r["file_type"].upper())
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
            "id": f"db-{idx + 1}",
            "name": first["title"] or repo_full_name.split("/")[-1],
            "description": first["description"] or "",
            "fileTypes": seen_ft,
            "patientType": "generic",
            "organSystem": "general",
            "surgicalSystem": "generic",
            "rlFrameworks": [],
            "sourceType": "arxiv" if first["arxiv_id"] else "github",
            "arxivId": first["arxiv_id"] or None,
            "arxivTitle": first["title"] if first["arxiv_id"] else None,
            "githubRepo": repo_full_name,
            "githubStars": first["stars"],
            "authors": authors,
            "year": year,
            "tags": [],
            "downloadUrl": first["url"],
            "license": first["license"] or None,
            "addedAt": str(first["discovered_at"])[:10] if first["discovered_at"] else "",
            "thumbnailColor": _COLORS[idx % len(_COLORS)],
        })

    out_path.write_text(json.dumps(assets, indent=2))
    log.info("Exported %d assets → %s", len(assets), out_path)
    return len(assets)
