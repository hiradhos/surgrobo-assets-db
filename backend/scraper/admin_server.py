"""Minimal admin API for deleting assets from the SQLite DB.

Run:
  python -m backend.scraper.admin_server
"""
from __future__ import annotations

import base64
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from . import config, db, export

log = logging.getLogger(__name__)


def _basic_auth_ok(header: str | None) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except Exception:
        return False
    user, _, pwd = raw.partition(":")
    return user == config.ADMIN_USER and pwd == config.ADMIN_PASS


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "NetterAdmin/0.1"

    def _set_headers(self, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._set_headers(200)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._set_headers(200)
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "not found"}).encode("utf-8"))

    def do_POST(self) -> None:  # noqa: N802
        if not _basic_auth_ok(self.headers.get("Authorization")):
            self._set_headers(401)
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode("utf-8"))
            return

        if self.path != "/delete":
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "not found"}).encode("utf-8"))
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "invalid json"}).encode("utf-8"))
            return

        source_keys = payload.get("sourceKeys") or []
        if not isinstance(source_keys, list) or not source_keys:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "sourceKeys required"}).encode("utf-8"))
            return

        db.init_db()

        deleted_repos = 0
        deleted_anatomy = 0

        with db._connect() as conn:
            for key in source_keys:
                if not isinstance(key, str):
                    continue
                if key.startswith("github:"):
                    full_name = key.split("github:", 1)[1]
                    cur = conn.execute(
                        "DELETE FROM repos WHERE full_name = ?",
                        (full_name,),
                    )
                    deleted_repos += cur.rowcount if cur.rowcount is not None else 0
                    db.ban_source(key, "github", "admin delete", conn)
                elif key.startswith("anatomy:"):
                    rec_id = key.split("anatomy:", 1)[1]
                    cur = conn.execute(
                        "DELETE FROM anatomy_records WHERE record_id = ?",
                        (rec_id,),
                    )
                    deleted_anatomy += cur.rowcount if cur.rowcount is not None else 0
                    db.ban_source(key, "anatomy", "admin delete", conn)

        try:
            export.export_assets()
        except Exception:
            log.exception("Failed to export db-assets.json after admin delete")

        self._set_headers(200)
        self.wfile.write(
            json.dumps({
                "deletedRepos": deleted_repos,
                "deletedAnatomy": deleted_anatomy,
            }).encode("utf-8")
        )


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    addr = (config.ADMIN_BIND, config.ADMIN_PORT)
    server = HTTPServer(addr, AdminHandler)
    log.info("Admin API listening on http://%s:%d", *addr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
