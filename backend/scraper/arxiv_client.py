"""
arXiv API client for the SurgSim DB scraper.

Uses the arXiv Atom feed API (no authentication required).
Docs: https://arxiv.org/help/api/user-manual

Strategy
────────
1. Build a compound query combining surgical-context terms with
   simulation/RL terms (see config.ARXIV_QUERY_CLUSTERS).
2. Filter to papers published/updated within the lookback window.
3. Parse each Atom entry into an ArxivPaper dataclass.
4. Deduplicate against already-known IDs from the database.
"""
from __future__ import annotations

import logging
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Generator

import feedparser
import requests

from . import config
from .models import Paper, SourceDB

log = logging.getLogger(__name__)

_ARXIV_API_BASE = "https://export.arxiv.org/api/query"

# arXiv IDs look like: 2403.12345 or 2403.12345v2
_ARXIV_ID_RE = re.compile(r"\d{4}\.\d{4,5}(v\d+)?")


# ── Query building ─────────────────────────────────────────────────────────────

def _build_query(lookback_days: int = config.ARXIV_LOOKBACK_DAYS) -> str:
    """
    Build an arXiv API search query string.

    Logic:
      • Within each cluster, terms are OR-combined.
      • The two clusters are AND-combined.
      • Results are restricted to the configured arXiv categories.
      • A date filter is applied using submittedDate.
    """
    # Date range: from (today - lookback_days) to today
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    date_from = since.strftime("%Y%m%d%H%M")
    date_to   = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    date_filter = f"submittedDate:[{date_from} TO {date_to}]"

    # Category filter
    cat_filter = " OR ".join(f"cat:{c}" for c in config.ARXIV_CATEGORIES)
    cat_clause = f"({cat_filter})"

    # Content clusters
    cluster_clauses: list[str] = []
    for cluster in config.ARXIV_QUERY_CLUSTERS:
        terms = " OR ".join(
            f'ti:"{t}" OR abs:"{t}"' for t in cluster
        )
        cluster_clauses.append(f"({terms})")

    content_clause = " AND ".join(cluster_clauses)

    return f"({content_clause}) AND {cat_clause} AND {date_filter}"


# ── Parsing ────────────────────────────────────────────────────────────────────

def _parse_datetime(raw: str) -> datetime:
    """Parse arXiv's ISO-8601 date strings (they include timezone)."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    # fallback: strip trailing Z manually
    return datetime.fromisoformat(raw.rstrip("Z")).replace(tzinfo=timezone.utc)


def _entry_to_paper(entry: feedparser.FeedParserDict) -> Paper | None:
    """Convert a single feedparser entry to a Paper, or None on failure."""
    try:
        raw_id: str = entry.get("id", "")
        m = _ARXIV_ID_RE.search(raw_id)
        if not m:
            return None
        arxiv_id = m.group(0).split("v")[0]

        authors = [a["name"] for a in entry.get("authors", [])]
        categories = [t["term"] for t in entry.get("tags", [])]
        published_at = _parse_datetime(entry.get("published", "1970-01-01T00:00:00Z"))
        updated_at   = _parse_datetime(entry.get("updated",   "1970-01-01T00:00:00Z"))

        pdf_url = next(
            (l["href"] for l in entry.get("links", []) if l.get("type") == "application/pdf"),
            f"https://arxiv.org/pdf/{arxiv_id}",
        )

        return Paper(
            paper_id=Paper.make_id(arxiv_id=arxiv_id),
            source_db=SourceDB.ARXIV,
            arxiv_id=arxiv_id,
            title=entry.get("title", "").replace("\n", " ").strip(),
            authors=authors,
            abstract=entry.get("summary", "").replace("\n", " ").strip(),
            published_at=published_at,
            updated_at=updated_at,
            categories=categories,
            pdf_url=pdf_url,
        )
    except Exception as exc:
        log.warning("Failed to parse arXiv entry %s: %s", entry.get("id", "?"), exc)
        return None


# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_papers(
    known_ids: set[str] | None = None,
    lookback_days: int = config.ARXIV_LOOKBACK_DAYS,
    max_results: int = config.ARXIV_MAX_RESULTS,
) -> Generator[Paper, None, None]:
    """
    Yield Paper objects for recent surgical-robotics arXiv papers.

    Skips papers whose arxiv_id is already in `known_ids` (incremental mode).
    Paginates automatically up to `max_results` total entries.
    """
    known_ids = known_ids or set()
    query     = _build_query(lookback_days)
    start     = 0
    page_size = min(100, max_results)
    total_yielded = 0

    log.info("arXiv query: %s", query[:120] + ("…" if len(query) > 120 else ""))

    while total_yielded < max_results:
        params = {
            "search_query": query,
            "start":        start,
            "max_results":  page_size,
            "sortBy":       "submittedDate",
            "sortOrder":    "descending",
        }
        url = f"{_ARXIV_API_BASE}?{urllib.parse.urlencode(params)}"

        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "SurgSimDB-Scraper/1.0"})
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.error("arXiv request failed (start=%d): %s", start, exc)
            break

        feed = feedparser.parse(resp.text)
        entries = feed.get("entries", [])

        if not entries:
            log.debug("arXiv returned 0 entries at start=%d — stopping pagination", start)
            break

        for entry in entries:
            paper = _entry_to_paper(entry)
            if paper is None:
                continue
            if paper.arxiv_id in known_ids:
                log.debug("  skip (known): %s", paper.arxiv_id)
                continue
            log.debug("  new paper: %s — %s", paper.arxiv_id, paper.title[:60])
            yield paper
            total_yielded += 1
            if total_yielded >= max_results:
                break

        start += len(entries)
        if len(entries) < page_size:
            break  # no more pages

        log.debug("arXiv page done. start=%d, yielded so far=%d", start, total_yielded)
        time.sleep(config.ARXIV_REQUEST_DELAY)

    log.info("arXiv fetch complete: %d new papers", total_yielded)
