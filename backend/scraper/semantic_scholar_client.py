"""
Semantic Scholar API client for the SurgSim DB scraper.

Semantic Scholar (S2) indexes papers from arXiv, IEEE, PubMed, ACM, and many
other sources under a single API. It is particularly useful because:
  • It covers conference proceedings (ICRA, IROS, MICCAI, HAMLYN) that are
    not well-indexed in PubMed.
  • Its externalIds field exposes arXiv ID, DOI, and PubMed ID — enabling
    cross-source deduplication.
  • Unauthenticated rate limit: 1 req/s (sufficient for weekly batch runs).

Docs: https://api.semanticscholar.org/api-docs/
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Generator

import requests

from . import config
from .models import Paper, SourceDB

log = logging.getLogger(__name__)

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"

# Fields returned by the S2 search endpoint.
_FIELDS = ",".join([
    "paperId",
    "externalIds",       # arXivId, DOI, PubMedId, etc.
    "title",
    "abstract",
    "authors",
    "year",
    "publicationDate",
    "publicationTypes",
    "journal",
    "openAccessPdf",
    "fieldsOfStudy",
])

# Top surgical-robotics conferences/journals that S2 indexes but PubMed/arXiv miss.
# These are used as venue filters in addition to keyword search.
TARGET_VENUES: list[str] = [
    "International Conference on Robotics and Automation",  # ICRA
    "IEEE/RSJ International Conference on Intelligent Robots and Systems",  # IROS
    "Medical Image Computing and Computer Assisted Intervention",  # MICCAI
    "Hamlyn Symposium on Medical Robotics",
    "International Symposium on Medical Robotics",  # ISMR
    "IEEE International Conference on Robotics and Biomimetics",  # ROBIO
    "Conference on Robot Learning",  # CoRL
    "International Journal of Computer Assisted Radiology and Surgery",  # IJCARS
    "Frontiers in Robotics and AI",
]

# Search queries — each is a separate API call to maximise coverage.
SEARCH_QUERIES: list[str] = [
    "surgical robot simulation reinforcement learning",
    "robotic surgery URDF MuJoCo simulation",
    "da Vinci robot simulation learning",
    "laparoscopic robot simulation environment",
    "surgical tissue deformation simulation",
    "autonomous surgical robot learning",
    "robot-assisted surgery Isaac Sim",
    "surgical skill learning simulation",
    "suturing robot reinforcement learning",
    "minimally invasive surgery simulation asset",
]

_REQUEST_DELAY = 1.1  # seconds (safe for 1 req/s unauthenticated)


def _headers() -> dict[str, str]:
    return {"User-Agent": "SurgSimDB-Scraper/1.0"}


def _get(params: dict, *, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            resp = requests.get(
                _S2_SEARCH, params=params, headers=_headers(), timeout=20,
            )
        except requests.RequestException as exc:
            log.warning("S2 request failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 10))
            log.warning("S2 rate limit hit, sleeping %ds …", wait)
            time.sleep(wait)
            continue
        if resp.status_code == 404:
            return None
        log.warning("S2 HTTP %d for query", resp.status_code)
        return None

    return None


def _parse_date(paper: dict) -> datetime:
    raw = paper.get("publicationDate") or ""
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    year = paper.get("year")
    if year:
        return datetime(int(year), 1, 1, tzinfo=timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _to_paper(item: dict) -> Paper | None:
    """Convert a Semantic Scholar search result dict to a Paper, or None."""
    try:
        title = (item.get("title") or "").strip()
        if not title:
            return None

        abstract = (item.get("abstract") or "").strip()
        ext_ids: dict = item.get("externalIds") or {}
        arxiv_id  = ext_ids.get("ArXiv")
        doi       = (ext_ids.get("DOI") or "").lower() or None
        pubmed_id = ext_ids.get("PubMed") or ext_ids.get("PMID")

        # Build canonical ID — prefer arXiv so we can deduplicate with arXiv client
        try:
            paper_id = Paper.make_id(arxiv_id=arxiv_id, pubmed_id=pubmed_id, doi=doi)
        except ValueError:
            # S2 paperId as last resort
            s2_id = item.get("paperId", "")
            if not s2_id:
                return None
            paper_id = f"s2:{s2_id}"

        authors = [
            a.get("name", "") for a in (item.get("authors") or []) if a.get("name")
        ]

        pub_date = _parse_date(item)
        categories = item.get("fieldsOfStudy") or []

        journal_name = ""
        journal = item.get("journal") or {}
        if isinstance(journal, dict):
            journal_name = journal.get("name") or ""

        pdf_url = ""
        oa = item.get("openAccessPdf") or {}
        if isinstance(oa, dict):
            pdf_url = oa.get("url") or ""
        if not pdf_url:
            if arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
            elif doi:
                pdf_url = f"https://doi.org/{doi}"
            elif pubmed_id:
                pdf_url = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"

        return Paper(
            paper_id=paper_id,
            source_db=SourceDB.SEMANTIC_SCHOLAR,
            title=title,
            authors=authors,
            abstract=abstract,
            published_at=pub_date,
            updated_at=pub_date,
            categories=[str(c) for c in categories],
            pdf_url=pdf_url,
            arxiv_id=arxiv_id,
            doi=doi,
            pubmed_id=str(pubmed_id) if pubmed_id else None,
            journal_name=journal_name,
        )
    except Exception as exc:
        log.debug("S2 paper parse error: %s", exc)
        return None


def fetch_papers(
    known_paper_ids: set[str] | None = None,
    known_arxiv_ids: set[str] | None = None,
    lookback_days: int = config.ARXIV_LOOKBACK_DAYS,
    max_per_query: int = 50,
) -> Generator[Paper, None, None]:
    """
    Yield Paper objects from Semantic Scholar for surgical-robotics papers.

    Runs each query in SEARCH_QUERIES and deduplicates by paper_id and arXiv ID
    so papers already found by the arXiv client are not re-emitted.
    """
    known_paper_ids  = known_paper_ids  or set()
    known_arxiv_ids  = known_arxiv_ids  or set()
    since_year = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).year

    seen_this_run: set[str] = set()
    total_yielded = 0

    for query in SEARCH_QUERIES:
        log.debug("S2 query: %s", query)
        data = _get({
            "query":  query,
            "fields": _FIELDS,
            "limit":  max_per_query,
        })
        if data is None:
            time.sleep(_REQUEST_DELAY)
            continue

        for item in data.get("data", []):
            paper = _to_paper(item)
            if paper is None:
                continue

            # Date filter
            if paper.published_at.year < since_year:
                continue

            # Dedup: skip if already in DB or already yielded this run
            if paper.paper_id in known_paper_ids or paper.paper_id in seen_this_run:
                continue
            # Also skip if its arXiv ID is already known (arXiv client will/did cover it)
            if paper.arxiv_id and paper.arxiv_id in known_arxiv_ids:
                continue

            seen_this_run.add(paper.paper_id)
            log.debug("  S2: %s — %s", paper.paper_id, paper.title[:60])
            yield paper
            total_yielded += 1

        time.sleep(_REQUEST_DELAY)

    log.info("Semantic Scholar fetch complete: %d new papers", total_yielded)
