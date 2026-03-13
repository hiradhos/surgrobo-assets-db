"""
SQLite persistence layer for the SurgSim DB scraper.

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
from .models import FileType, GitHubRepo, Paper, ScrapeRun

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


def init_db(db_path: Path = config.DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_DDL)
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
