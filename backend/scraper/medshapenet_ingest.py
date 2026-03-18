"""
Ingest local MedShapeNet assets into the SQLite DB and export to frontend JSON.

Usage:
  python -m backend.scraper.medshapenet_ingest
  python -m backend.scraper.medshapenet_ingest --skip-sync
  python -m backend.scraper.medshapenet_ingest --sync-download
"""
from __future__ import annotations

import argparse
import logging
import runpy
import sys
from contextlib import contextmanager

from . import config, db
from .anatomy_client import _session, scrape_medshapenet
from .export import export_assets

log = logging.getLogger(__name__)


@contextmanager
def _patched_argv(args: list[str]):
    old = sys.argv[:]
    sys.argv = args
    try:
        yield
    finally:
        sys.argv = old


def _run_medshapenet_sync(skip_download: bool) -> None:
    log.info("Running medshapenet_sync (skip_download=%s)", skip_download)
    argv = ["medshapenet_sync"]
    if skip_download:
        argv.append("--skip-download")
    with _patched_argv(argv):
        runpy.run_module("backend.scraper.medshapenet_sync", run_name="__main__")


def _run_medshapenet_thumbs(force: bool) -> None:
    log.info("Running medshapenet_thumbs (force=%s)", force)
    argv = ["medshapenet_thumbs"]
    if force:
        argv.append("--force")
    with _patched_argv(argv):
        runpy.run_module("backend.scraper.medshapenet_thumbs", run_name="__main__")


def ingest_medshapenet(
    skip_sync: bool,
    skip_download: bool,
    skip_thumbnails: bool,
    force_thumbnails: bool,
    skip_export: bool,
) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if not skip_sync:
        _run_medshapenet_sync(skip_download=skip_download)

    if not skip_thumbnails:
        _run_medshapenet_thumbs(force=force_thumbnails)

    # Force only MedShapeNet regardless of environment at import time.
    config.ANATOMY_SOURCES = ["medshapenet"]

    db.init_db()
    with db._connect() as conn:
        banned = db.get_banned_anatomy_ids(conn)

    # Force a full refresh from the MedShapeNet manifest so preview_url updates.
    session = _session()
    records = [r for r in scrape_medshapenet(session, set()) if r.record_id not in banned]

    added = updated = 0
    with db._connect() as conn:
        for rec in records:
            if db.upsert_anatomy_record(rec, conn):
                added += 1
            else:
                updated += 1

    log.info("medshapenet ingest: +%d new, ~%d updated", added, updated)

    if not skip_export:
        export_assets()
        log.info("exported public/db-assets.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest local MedShapeNet assets into SQLite and export db-assets.json",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip medshapenet_sync (manifest + previews).",
    )
    parser.add_argument(
        "--sync-download",
        action="store_true",
        help="Allow medshapenet_sync to download missing files (default: skip downloads).",
    )
    parser.add_argument(
        "--skip-thumbnails",
        action="store_true",
        help="Skip PNG thumbnail generation.",
    )
    parser.add_argument(
        "--force-thumbnails",
        action="store_true",
        help="Re-render thumbnails even if PNGs exist.",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip exporting public/db-assets.json.",
    )
    args = parser.parse_args()

    ingest_medshapenet(
        skip_sync=args.skip_sync,
        skip_download=not args.sync_download,
        skip_thumbnails=args.skip_thumbnails,
        force_thumbnails=args.force_thumbnails,
        skip_export=args.skip_export,
    )


if __name__ == "__main__":
    main()
