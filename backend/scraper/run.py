"""
Netter-DB — Weekly Scraper Orchestrator

Usage
─────
Run once immediately:
    python -m backend.scraper.run --once

Run as a persistent process (fires every Sunday at 02:00 UTC by default):
    python -m backend.scraper.run

Override schedule via environment:
    SCHEDULE_DAY=monday SCHEDULE_TIME=03:30 python -m backend.scraper.run

Override lookback for a back-fill / initial load:
    python -m backend.scraper.run --once --lookback-days 90

Pipeline (per run)
──────────────────
Phase 1a — arXiv: fetch surgical-robotics preprints matching keyword clusters.
Phase 1b — PubMed: fetch papers from targeted medical/surgical robotics journals.
Phase 1c — Semantic Scholar: fetch papers from ICRA, IROS, MICCAI, Hamlyn, etc.
Phase 2  — GitHub link extraction: parse all paper abstracts/titles for repo URLs.
Phase 3  — Direct GitHub search: secondary discovery pass.
Phase 4  — Repo scanning: fetch metadata + walk git tree for simulation assets.
Phase 4  — Anatomy databases: scrape HumanAtlas, NIH 3D, MedShapeNet, etc.
Phase 5  — Persist: upsert papers, repos, assets, anatomy records, and audit log.
Phase 6  — Local LLM vetting: filter non-anatomical assets and correct metadata.
Phase 7  — Export: write public/db-assets.json for the frontend.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import schedule

from . import config, db
from .export import export_assets
from .arxiv_client import fetch_papers as fetch_arxiv_papers
from .pubmed_client import fetch_papers as fetch_pubmed_papers
from .semantic_scholar_client import fetch_papers as fetch_s2_papers
from .github_client import (
    extract_github_urls,
    fetch_repo_metadata,
    scan_repo_for_assets,
    search_github_for_surgical_repos,
)
from .anatomy_client import scrape_all_anatomy_sources
from .models import Paper, ScrapeRun
from .vetter import vet_assets

# ── Logging setup ──────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if config.LOG_FILE:
        config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(config.LOG_FILE))

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
    )


log = logging.getLogger(__name__)


# ── Core pipeline ──────────────────────────────────────────────────────────────

def _collect_papers_from_source(
    source_name: str,
    generator,
    papers_this_run: list[Paper],
    queued_repos: dict[str, tuple[str, str]],
    repo_source_paper: dict[str, str],
    banned_repos: set[str],
    run: ScrapeRun,
) -> None:
    """
    Drain a paper generator, extract GitHub URLs, and queue repos for scanning.
    Mutates papers_this_run, queued_repos, repo_source_paper, and run in place.
    """
    count = 0
    for paper in generator:
        run.papers_fetched += 1
        count += 1
        papers_this_run.append(paper)

        search_text = f"{paper.title} {paper.abstract}"
        found_pairs = extract_github_urls(search_text)

        if found_pairs:
            log.info(
                "  [%s] '%s…' → %d GitHub URL(s)",
                paper.paper_id,
                paper.title[:50],
                len(found_pairs),
            )

        for owner, name in found_pairs:
            full_name = f"{owner}/{name}".lower()
            if full_name in banned_repos:
                continue
            if full_name not in queued_repos:
                queued_repos[full_name] = (owner, name)
                repo_source_paper[full_name] = paper.paper_id

    log.info("  %s: %d new papers collected", source_name, count)


def run_scrape(lookback_days: int = config.ARXIV_LOOKBACK_DAYS) -> ScrapeRun:
    """
    Execute one complete scrape cycle.  Returns a filled-in ScrapeRun summary.
    """
    started_at = datetime.now(timezone.utc)
    run = ScrapeRun(started_at=started_at)

    log.info("=" * 60)
    log.info("Netter-DB scraper starting  (lookback=%d days)", lookback_days)
    log.info("=" * 60)

    db.init_db()

    with db._connect() as conn:
        run_id          = db.start_run(conn)
        known_paper_ids = db.get_known_paper_ids(conn)
        known_arxiv_ids = db.get_known_arxiv_ids(conn)
        known_pubmed_ids = db.get_known_pubmed_ids(conn)
        known_repos     = db.get_known_repo_names(conn)
        banned_repos    = db.get_banned_repo_names(conn)

    log.info(
        "Known papers: %d (arXiv: %d, PubMed: %d)  |  Known repos: %d",
        len(known_paper_ids),
        len(known_arxiv_ids),
        len(known_pubmed_ids),
        len(known_repos),
    )
    if banned_repos:
        log.info("Banned repos: %d", len(banned_repos))

    # Track repos queued for scanning to avoid duplicate work within this run.
    # full_name (lower) -> (owner, name)
    queued_repos: dict[str, tuple[str, str]] = {}
    # Maps repo full_name (lower) -> paper_id that first introduced it
    repo_source_paper: dict[str, str] = {}

    # Accumulates all papers seen this run (for bulk upsert at the end)
    papers_this_run: list[Paper] = []

    # ── Phase 1a: arXiv ───────────────────────────────────────────────────────

    log.info("Phase 1a: arXiv …")
    _collect_papers_from_source(
        "arXiv",
        fetch_arxiv_papers(
            known_ids=known_arxiv_ids,
            lookback_days=lookback_days,
        ),
        papers_this_run,
        queued_repos,
        repo_source_paper,
        banned_repos,
        run,
    )

    # ── Phase 1b: PubMed ──────────────────────────────────────────────────────

    log.info("Phase 1b: PubMed …")
    _collect_papers_from_source(
        "PubMed",
        fetch_pubmed_papers(
            known_pubmed_ids=known_pubmed_ids,
            lookback_days=lookback_days,
        ),
        papers_this_run,
        queued_repos,
        repo_source_paper,
        banned_repos,
        run,
    )

    # ── Phase 1c: Semantic Scholar ────────────────────────────────────────────

    log.info("Phase 1c: Semantic Scholar …")
    _collect_papers_from_source(
        "Semantic Scholar",
        fetch_s2_papers(
            known_paper_ids=known_paper_ids,
            known_arxiv_ids=known_arxiv_ids,
            lookback_days=lookback_days,
        ),
        papers_this_run,
        queued_repos,
        repo_source_paper,
        banned_repos,
        run,
    )

    log.info(
        "Phases 1a-1c complete: %d new papers total, %d candidate repos",
        run.papers_fetched,
        len(queued_repos),
    )

    # ── Phase 2: Direct GitHub search (secondary discovery) ───────────────────

    log.info("Phase 2: GitHub repo search …")
    direct_repos = search_github_for_surgical_repos()
    added_direct = 0
    for repo in direct_repos:
        fn = repo.full_name.lower()
        if fn in banned_repos:
            continue
        if fn not in queued_repos:
            queued_repos[fn] = (repo.owner, repo.name)
            added_direct += 1

    log.info("Phase 2 complete: %d additional repos from direct search", added_direct)

    # ── Phase 3: Fetch metadata + scan each repo ───────────────────────────────

    log.info("Phase 3: scanning %d repos …", len(queued_repos))

    for full_name_lower, (owner, name) in queued_repos.items():
        if full_name_lower in banned_repos:
            continue
        log.info("  Scanning %s/%s …", owner, name)

        repo = fetch_repo_metadata(owner, name)
        if repo is None:
            run.errors.append(f"metadata fetch failed: {owner}/{name}")
            continue

        repo = scan_repo_for_assets(repo)
        run.repos_scanned += 1

        if not repo.detected_file_types:
            log.debug("  No simulation assets in %s — skipping DB write", repo.full_name)
            continue

        source_paper_id = repo_source_paper.get(full_name_lower)

        with db._connect() as conn:
            # Persist all papers collected this run
            for paper in papers_this_run:
                try:
                    db.upsert_paper(paper, conn)
                except Exception as exc:
                    log.warning("Could not persist paper %s: %s", paper.paper_id, exc)

            db.upsert_repo(repo, conn)

            if source_paper_id:
                db.link_paper_repo(source_paper_id, repo.full_name, conn)

            added, updated = db.upsert_assets(repo, source_paper_id, conn)
            run.assets_added   += added
            run.assets_updated += updated

        log.info(
            "  %s: +%d new asset types, ~%d updated",
            repo.full_name,
            added,
            updated,
        )

    # ── Persist any remaining papers (those with no GitHub links) ─────────────

    with db._connect() as conn:
        for paper in papers_this_run:
            try:
                db.upsert_paper(paper, conn)
            except Exception as exc:
                log.warning("Could not persist paper %s: %s", paper.paper_id, exc)

    # ── Phase 4: Anatomy database scraping ────────────────────────────────────

    log.info("Phase 4: scraping anatomy databases …")
    with db._connect() as conn:
        known_anatomy_ids = db.get_known_anatomy_ids(conn)
        banned_anatomy_ids = db.get_banned_anatomy_ids(conn)

    anatomy_records = scrape_all_anatomy_sources(known_anatomy_ids | banned_anatomy_ids)

    anatomy_added = anatomy_updated = 0
    with db._connect() as conn:
        for rec in anatomy_records:
            try:
                is_new = db.upsert_anatomy_record(rec, conn)
                if is_new:
                    anatomy_added += 1
                else:
                    anatomy_updated += 1
            except Exception as exc:
                log.warning("Could not persist anatomy record %s: %s", rec.record_id, exc)

    log.info(
        "Phase 4 complete: +%d new anatomy records, ~%d updated",
        anatomy_added,
        anatomy_updated,
    )

    # ── Finalise audit record ──────────────────────────────────────────────────

    run.finished_at = datetime.now(timezone.utc)
    elapsed = (run.finished_at - started_at).total_seconds()

    with db._connect() as conn:
        db.finish_run(run_id, run, conn)

    # ── Phase 5: Local LLM vetting ────────────────────────────────────────────

    log.info("Phase 5: local LLM vetting …")
    try:
        vet_assets()
    except Exception as exc:
        log.warning("Vetting failed: %s", exc)

    # ── Phase 5: Export to frontend JSON ──────────────────────────────────────

    log.info("Phase 6: exporting assets to public/db-assets.json …")
    export_assets()

    log.info("=" * 60)
    log.info(
        "Scrape complete in %.1fs  |  papers=%d  repos=%d  +assets=%d  ~assets=%d  errors=%d",
        elapsed,
        run.papers_fetched,
        run.repos_scanned,
        run.assets_added,
        run.assets_updated,
        len(run.errors),
    )
    if run.errors:
        for err in run.errors[:10]:
            log.warning("  error: %s", err)
    log.info("=" * 60)

    return run


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _schedule_and_run() -> None:
    log.info(
        "Scheduling weekly scrape: every %s at %s UTC",
        config.SCHEDULE_DAY,
        config.SCHEDULE_TIME,
    )
    getattr(schedule.every(), config.SCHEDULE_DAY).at(config.SCHEDULE_TIME).do(run_scrape)

    # Run immediately on startup too (so you get data on first deploy)
    run_scrape()

    while True:
        schedule.run_pending()
        time.sleep(60)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    _configure_logging()

    parser = argparse.ArgumentParser(
        description="Netter-DB — arXiv / PubMed / Semantic Scholar / GitHub scraper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scrape cycle and exit (good for cron)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=config.ARXIV_LOOKBACK_DAYS,
        metavar="N",
        help="How many days back to search all sources",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Re-export public/db-assets.json from the existing DB without re-scraping",
    )
    args = parser.parse_args()

    if args.export_only:
        from .export import export_assets
        n = export_assets()
        log.info("export-only: wrote %d records", n)
    elif args.once:
        run_scrape(lookback_days=args.lookback_days)
    else:
        _schedule_and_run()


if __name__ == "__main__":
    main()
