"""
SQLite persistence layer for the Netter-DB scraper.

Schema
──────
papers      — papers from arXiv, PubMed, and Semantic Scholar
repos       — GitHub repositories linked to papers or found directly
paper_repos — many-to-many join
assets      — one row per (repo, file_type) pair — queried by the frontend
scrape_runs — audit log of every scraper execution
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from . import config
from .models import AnatomyRecord, FileType, GitHubRepo, Paper, ScrapeRun

log = logging.getLogger(__name__)

# ── Schema ─────────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS papers (
    paper_id        TEXT PRIMARY KEY,    -- "arxiv:2403.12345" | "pmid:38547123" | "doi:..."
    source_db       TEXT NOT NULL,       -- arxiv | pubmed | semantic_scholar
    title           TEXT NOT NULL,
    authors         TEXT NOT NULL,       -- JSON array
    abstract        TEXT NOT NULL,
    categories      TEXT NOT NULL,       -- JSON array (arXiv cats / MeSH / S2 fields)
    published_at    TEXT NOT NULL,       -- ISO-8601
    updated_at      TEXT NOT NULL,
    pdf_url         TEXT NOT NULL,
    arxiv_id        TEXT,                -- cross-reference
    doi             TEXT,
    pubmed_id       TEXT,
    journal_name    TEXT,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_arxiv_id  ON papers(arxiv_id)  WHERE arxiv_id  IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_pubmed_id ON papers(pubmed_id) WHERE pubmed_id IS NOT NULL;
CREATE INDEX        IF NOT EXISTS idx_papers_source    ON papers(source_db);

CREATE TABLE IF NOT EXISTS repos (
    full_name       TEXT PRIMARY KEY,
    owner           TEXT NOT NULL,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL,
    description     TEXT,
    stars           INTEGER NOT NULL DEFAULT 0,
    license         TEXT,
    last_updated    TEXT NOT NULL,
    asset_paths     TEXT NOT NULL DEFAULT '[]',
    file_types      TEXT NOT NULL DEFAULT '[]',
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_repos (
    paper_id        TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    repo_full_name  TEXT NOT NULL REFERENCES repos(full_name) ON DELETE CASCADE,
    PRIMARY KEY (paper_id, repo_full_name)
);

CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_full_name  TEXT NOT NULL REFERENCES repos(full_name) ON DELETE CASCADE,
    paper_id        TEXT REFERENCES papers(paper_id) ON DELETE SET NULL,
    file_type       TEXT NOT NULL,
    asset_paths     TEXT NOT NULL DEFAULT '[]',
    stars           INTEGER NOT NULL DEFAULT 0,
    license         TEXT,
    last_updated    TEXT NOT NULL,
    discovered_at   TEXT NOT NULL,
    UNIQUE (repo_full_name, file_type)
);

CREATE INDEX IF NOT EXISTS idx_assets_file_type    ON assets(file_type);
CREATE INDEX IF NOT EXISTS idx_assets_repo         ON assets(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_assets_last_updated ON assets(last_updated DESC);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    papers_fetched  INTEGER NOT NULL DEFAULT 0,
    repos_scanned   INTEGER NOT NULL DEFAULT 0,
    assets_added    INTEGER NOT NULL DEFAULT 0,
    assets_updated  INTEGER NOT NULL DEFAULT 0,
    errors          TEXT NOT NULL DEFAULT '[]'
);

-- Anatomy records from dedicated 3D anatomy databases (not GitHub/paper-derived)
CREATE TABLE IF NOT EXISTS anatomy_records (
    record_id        TEXT PRIMARY KEY,   -- "<source>:<unique-id>"
    source_collection TEXT NOT NULL,    -- humanatlas | medshapenet | nih3d | bodyparts3d | anatomytool | sketchfab | other
    name             TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    body_part        TEXT NOT NULL DEFAULT '',   -- liver | heart | femur | brain | etc.
    organ_system     TEXT NOT NULL DEFAULT 'general',
    age_group        TEXT NOT NULL DEFAULT 'adult',      -- adult | pediatric | fetal | generic
    sex              TEXT NOT NULL DEFAULT 'unknown',    -- male | female | unknown
    condition_type   TEXT NOT NULL DEFAULT 'healthy',   -- healthy | tumor | fracture | defect | variant | pathologic | unknown
    creation_method  TEXT NOT NULL DEFAULT 'unknown',   -- ct-scan | mri | photogrammetry | synthetic | anatomist | cadaver | unknown
    file_types       TEXT NOT NULL DEFAULT '[]',        -- JSON array of strings
    download_url     TEXT NOT NULL DEFAULT '',
    preview_url      TEXT NOT NULL DEFAULT '',
    license          TEXT NOT NULL DEFAULT '',
    tags             TEXT NOT NULL DEFAULT '[]',        -- JSON array
    authors          TEXT NOT NULL DEFAULT '[]',        -- JSON array
    year             INTEGER,
    discovered_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_anatomy_source     ON anatomy_records(source_collection);
CREATE INDEX IF NOT EXISTS idx_anatomy_organ      ON anatomy_records(organ_system);
CREATE INDEX IF NOT EXISTS idx_anatomy_condition  ON anatomy_records(condition_type);
CREATE INDEX IF NOT EXISTS idx_anatomy_body_part  ON anatomy_records(body_part);

-- LLM vetting decisions (applies to GitHub repo assets and anatomy records)
CREATE TABLE IF NOT EXISTS asset_vetting (
    source_key              TEXT PRIMARY KEY,  -- "github:<owner/repo>" | "anatomy:<record_id>"
    source_type             TEXT NOT NULL,     -- github | anatomy
    decision                TEXT NOT NULL,     -- keep | reject
    confidence              REAL NOT NULL,
    reason                  TEXT NOT NULL,
    corrected_name          TEXT,
    corrected_body_part     TEXT,
    corrected_organ_system  TEXT,
    corrected_age_group     TEXT,
    corrected_sex           TEXT,
    corrected_condition     TEXT,
    corrected_creation      TEXT,
    corrected_source        TEXT,
    corrected_category      TEXT,
    corrected_tags          TEXT NOT NULL DEFAULT '[]',
    updated_at              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vetting_source_type ON asset_vetting(source_type);

-- Banlist to prevent re-ingest of rejected items
CREATE TABLE IF NOT EXISTS banned_sources (
    source_key   TEXT PRIMARY KEY,  -- "github:<owner/repo>" | "anatomy:<record_id>"
    source_type  TEXT NOT NULL,     -- github | anatomy
    reason       TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_banned_source_type ON banned_sources(source_type);
"""


# ── Connection management ──────────────────────────────────────────────────────

@contextmanager
def _connect(db_path: Path = config.DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply incremental schema changes that cannot go in _DDL (existing tables)."""
    migrations = [
        # Classifier labels for GitHub-sourced repos
        "ALTER TABLE repos ADD COLUMN category TEXT",
        "ALTER TABLE repos ADD COLUMN category_reason TEXT",
        # Anatomy metadata for GitHub-sourced assets (populated by classifier)
        "ALTER TABLE assets ADD COLUMN body_part TEXT",
        "ALTER TABLE assets ADD COLUMN condition_type TEXT",
        "ALTER TABLE assets ADD COLUMN creation_method TEXT",
        "ALTER TABLE assets ADD COLUMN sex TEXT",
        # Citation string for anatomy records
        "ALTER TABLE anatomy_records ADD COLUMN citation TEXT NOT NULL DEFAULT ''",
        # LLM-corrected category field for vetting (anatomical-model | or-infrastructure | ...)
        "ALTER TABLE asset_vetting ADD COLUMN corrected_category TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists


def init_db(db_path: Path = config.DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_DDL)
        _migrate(conn)
    log.info("Database initialised at %s", db_path)


# ── Upsert helpers ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def upsert_paper(paper: Paper, conn: sqlite3.Connection) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO papers
            (paper_id, source_db, title, authors, abstract, categories,
             published_at, updated_at, pdf_url,
             arxiv_id, doi, pubmed_id, journal_name,
             first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(paper_id) DO UPDATE SET
            title        = excluded.title,
            authors      = excluded.authors,
            abstract     = excluded.abstract,
            categories   = excluded.categories,
            updated_at   = excluded.updated_at,
            doi          = COALESCE(excluded.doi,       papers.doi),
            pubmed_id    = COALESCE(excluded.pubmed_id, papers.pubmed_id),
            journal_name = COALESCE(excluded.journal_name, papers.journal_name),
            last_seen_at = excluded.last_seen_at
        """,
        (
            paper.paper_id,
            paper.source_db.value,
            paper.title,
            json.dumps(paper.authors),
            paper.abstract,
            json.dumps(paper.categories),
            paper.published_at.isoformat(timespec="seconds"),
            paper.updated_at.isoformat(timespec="seconds"),
            paper.pdf_url,
            paper.arxiv_id,
            paper.doi,
            paper.pubmed_id,
            paper.journal_name,
            now,
            now,
        ),
    )


def upsert_repo(repo: GitHubRepo, conn: sqlite3.Connection) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO repos
            (full_name, owner, name, url, description, stars, license,
             last_updated, asset_paths, file_types, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(full_name) DO UPDATE SET
            description  = excluded.description,
            stars        = excluded.stars,
            license      = excluded.license,
            last_updated = excluded.last_updated,
            asset_paths  = excluded.asset_paths,
            file_types   = excluded.file_types,
            last_seen_at = excluded.last_seen_at
        """,
        (
            repo.full_name,
            repo.owner,
            repo.name,
            repo.url,
            repo.description,
            repo.stars,
            repo.license,
            repo.last_updated.isoformat(timespec="seconds"),
            json.dumps(repo.asset_paths),
            json.dumps([ft.value for ft in repo.detected_file_types]),
            now,
            now,
        ),
    )


def link_paper_repo(paper_id: str, repo_full_name: str, conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO paper_repos (paper_id, repo_full_name) VALUES (?, ?)",
        (paper_id, repo_full_name),
    )


def upsert_assets(
    repo: GitHubRepo,
    paper_id: str | None,
    conn: sqlite3.Connection,
) -> tuple[int, int]:
    added = updated = 0
    now = _now()

    for ft in repo.detected_file_types:
        paths_for_type = [p for p in repo.asset_paths if p.lower().endswith(f".{ft.value.lower()}")]
        if not paths_for_type:
            paths_for_type = repo.asset_paths[:10]

        cur = conn.execute(
            "SELECT id FROM assets WHERE repo_full_name = ? AND file_type = ?",
            (repo.full_name, ft.value),
        )
        row = cur.fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO assets
                    (repo_full_name, paper_id, file_type, asset_paths,
                     stars, license, last_updated, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo.full_name, paper_id, ft.value,
                    json.dumps(paths_for_type[:20]),
                    repo.stars, repo.license,
                    repo.last_updated.isoformat(timespec="seconds"), now,
                ),
            )
            added += 1
        else:
            conn.execute(
                """
                UPDATE assets
                SET asset_paths = ?, stars = ?, license = ?, last_updated = ?
                WHERE id = ?
                """,
                (
                    json.dumps(paths_for_type[:20]),
                    repo.stars, repo.license,
                    repo.last_updated.isoformat(timespec="seconds"),
                    row["id"],
                ),
            )
            updated += 1

    return added, updated


# ── Scrape-run log ─────────────────────────────────────────────────────────────

def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO scrape_runs (started_at) VALUES (?)", (_now(),))
    return cur.lastrowid  # type: ignore[return-value]


def finish_run(run_id: int, run: ScrapeRun, conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE scrape_runs
        SET finished_at=?, papers_fetched=?, repos_scanned=?,
            assets_added=?, assets_updated=?, errors=?
        WHERE id=?
        """,
        (
            run.finished_at.isoformat(timespec="seconds") if run.finished_at else None,
            run.papers_fetched, run.repos_scanned,
            run.assets_added, run.assets_updated,
            json.dumps(run.errors), run_id,
        ),
    )


# ── Read helpers ───────────────────────────────────────────────────────────────

def get_known_paper_ids(conn: sqlite3.Connection) -> set[str]:
    return {r["paper_id"] for r in conn.execute("SELECT paper_id FROM papers").fetchall()}


def get_known_arxiv_ids(conn: sqlite3.Connection) -> set[str]:
    """Convenience helper — returns bare arXiv IDs (without 'arxiv:' prefix)."""
    rows = conn.execute("SELECT arxiv_id FROM papers WHERE arxiv_id IS NOT NULL").fetchall()
    return {r["arxiv_id"] for r in rows}


def get_known_pubmed_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT pubmed_id FROM papers WHERE pubmed_id IS NOT NULL").fetchall()
    return {r["pubmed_id"] for r in rows}


def get_known_repo_names(conn: sqlite3.Connection) -> set[str]:
    return {r["full_name"] for r in conn.execute("SELECT full_name FROM repos").fetchall()}


def connect_ro(db_path: Path = config.DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


# ── Anatomy record CRUD ────────────────────────────────────────────────────────

def upsert_anatomy_record(rec: AnatomyRecord, conn: sqlite3.Connection) -> bool:
    """Insert or update an anatomy record. Returns True if it was newly inserted."""
    cur = conn.execute(
        "SELECT record_id FROM anatomy_records WHERE record_id = ?", (rec.record_id,)
    )
    exists = cur.fetchone() is not None

    conn.execute(
        """
        INSERT INTO anatomy_records
            (record_id, source_collection, name, description, body_part,
             organ_system, age_group, sex, condition_type, creation_method,
             file_types, download_url, preview_url, license, tags, authors, year)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(record_id) DO UPDATE SET
            name             = excluded.name,
            description      = excluded.description,
            body_part        = excluded.body_part,
            organ_system     = excluded.organ_system,
            age_group        = excluded.age_group,
            sex              = excluded.sex,
            condition_type   = excluded.condition_type,
            creation_method  = excluded.creation_method,
            file_types       = excluded.file_types,
            download_url     = excluded.download_url,
            preview_url      = excluded.preview_url,
            license          = excluded.license,
            tags             = excluded.tags,
            authors          = excluded.authors,
            year             = excluded.year
        """,
        (
            rec.record_id,
            rec.source_collection,
            rec.name,
            rec.description,
            rec.body_part,
            rec.organ_system,
            rec.age_group,
            rec.sex,
            rec.condition_type,
            rec.creation_method,
            json.dumps(rec.file_types),
            rec.download_url,
            rec.preview_url,
            rec.license,
            json.dumps(rec.tags),
            json.dumps(rec.authors),
            rec.year,
        ),
    )
    return not exists


def get_known_anatomy_ids(conn: sqlite3.Connection) -> set[str]:
    return {r["record_id"] for r in conn.execute("SELECT record_id FROM anatomy_records").fetchall()}


def get_anatomy_records(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM anatomy_records ORDER BY source_collection, name").fetchall()


# ── Vetting CRUD ───────────────────────────────────────────────────────────────

def upsert_vetting(
    source_key: str,
    source_type: str,
    decision: str,
    confidence: float,
    reason: str,
    corrected: dict,
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        """
        INSERT INTO asset_vetting
            (source_key, source_type, decision, confidence, reason,
             corrected_name, corrected_body_part, corrected_organ_system,
             corrected_age_group, corrected_sex, corrected_condition,
             corrected_creation, corrected_source, corrected_category,
             corrected_tags, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
            decision               = excluded.decision,
            confidence             = excluded.confidence,
            reason                 = excluded.reason,
            corrected_name         = excluded.corrected_name,
            corrected_body_part    = excluded.corrected_body_part,
            corrected_organ_system = excluded.corrected_organ_system,
            corrected_age_group    = excluded.corrected_age_group,
            corrected_sex          = excluded.corrected_sex,
            corrected_condition    = excluded.corrected_condition,
            corrected_creation     = excluded.corrected_creation,
            corrected_source       = excluded.corrected_source,
            corrected_category     = excluded.corrected_category,
            corrected_tags         = excluded.corrected_tags,
            updated_at             = excluded.updated_at
        """,
        (
            source_key,
            source_type,
            decision,
            confidence,
            reason,
            corrected.get("name"),
            corrected.get("body_part"),
            corrected.get("organ_system"),
            corrected.get("age_group"),
            corrected.get("sex"),
            corrected.get("condition_type"),
            corrected.get("creation_method"),
            corrected.get("source_collection"),
            corrected.get("category"),
            json.dumps(corrected.get("tags") or []),
            _now(),
        ),
    )


def get_vetting_map(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute("SELECT * FROM asset_vetting").fetchall()
    return {r["source_key"]: r for r in rows}


def ban_source(source_key: str, source_type: str, reason: str, conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO banned_sources (source_key, source_type, reason, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
            reason = excluded.reason,
            updated_at = excluded.updated_at
        """,
        (source_key, source_type, reason[:400], _now()),
    )


def get_banned_sources(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute("SELECT * FROM banned_sources").fetchall()
    return {r["source_key"]: r for r in rows}


def get_banned_anatomy_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT source_key FROM banned_sources WHERE source_type = 'anatomy'"
    ).fetchall()
    ids: set[str] = set()
    for r in rows:
        key = r["source_key"]
        if key.startswith("anatomy:"):
            ids.add(key.split("anatomy:", 1)[1])
    return ids


def get_banned_repo_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT source_key FROM banned_sources WHERE source_type = 'github'"
    ).fetchall()
    names: set[str] = set()
    for r in rows:
        key = r["source_key"]
        if key.startswith("github:"):
            names.add(key.split("github:", 1)[1].lower())
    return names
