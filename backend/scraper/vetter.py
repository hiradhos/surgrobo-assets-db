"""
Local LLM vetting for assets.

Runs after scraping to reject non-anatomical or low-fidelity assets and to
correct metadata (organ system, body part, age group, etc.).
"""
from __future__ import annotations

import json
import logging
import subprocess
import os
from typing import Any

import requests

from . import config, db

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert curator of surgical robotics simulation assets. "
    "Your job is to vet assets for high-fidelity anatomical and surgical training. "
    "KEEP high-quality surgical robotics simulation tools or environments when they "
    "clearly include or are built around realistic surgical/anatomical assets (e.g., "
    "surgical simulation toolkits, surgical RL environments, tissue/organ simulators). "
    "Reject anything that is artistic, stylized, cartoonish, illustrative, toy-like, "
    "game-like, decorative, or otherwise not a faithful anatomical or surgical asset. "
    "For anatomy-database assets (e.g., Sketchfab, NIH 3D, HumanAtlas, AnatomyTool), "
    "keep entries that are clearly human anatomy (organs, bones, vessels, musculoskeletal "
    "structures), even if not a surgical simulator. "
    "If the entry is a full-body human model or whole anatomy set, set "
    "organ_system=\"whole body\" and body_part=\"whole body\". "
    "Only keep assets that are clearly accurate anatomical structures or surgical "
    "robotics simulation assets suitable for reinforcement learning. "
    "If uncertain, reject.\n\n"
    "You must also correct metadata when the provided fields are wrong or vague: "
    "organ system, body part, age group (adult|pediatric|fetal|generic), sex "
    "(male|female|unknown), condition type (healthy|tumor|fracture|defect|variant|"
    "pathologic|unknown), creation method (ct-scan|mri|photogrammetry|synthetic|"
    "anatomist|cadaver|unknown), and source collection if it is wrong. "
    "If the title is indirect or unclear, provide a better name. "
    "Be conservative about edits; only change when clearly justified.\n\n"
    "Do NOT use Markdown or code fences. Output JSON only with this schema:\n"
    "{\n"
    "  \"keep\": true|false,\n"
    "  \"confidence\": 0.0-1.0,\n"
    "  \"reason\": \"short rationale\",\n"
    "  \"corrected\": {\n"
    "    \"name\": string|null,\n"
    "    \"organ_system\": string|null,\n"
    "    \"body_part\": string|null,\n"
    "    \"age_group\": string|null,\n"
    "    \"sex\": string|null,\n"
    "    \"condition_type\": string|null,\n"
    "    \"creation_method\": string|null,\n"
    "    \"source_collection\": string|null,\n"
    "    \"tags\": [string] | null\n"
    "  }\n"
    "}\n"
    "If you are unsure, set keep=false and provide your best corrections.\n"
)


def _call_local_llm(prompt: str) -> str | None:
    if config.LOCAL_LLM_BACKEND == "command":
        try:
            proc = subprocess.run(
                config.LOCAL_LLM_COMMAND.split(),
                input=f"{_SYSTEM_PROMPT}\n{prompt}".encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=config.LOCAL_LLM_TIMEOUT,
                check=False,
            )
        except Exception as exc:
            log.warning("local LLM command failed: %s", exc)
            return None
        if proc.returncode != 0:
            log.warning("local LLM command error: %s", proc.stderr.decode("utf-8", "ignore"))
            return None
        return proc.stdout.decode("utf-8", "ignore")

    # Default: Ollama-compatible HTTP API
    base_url = config.LOCAL_LLM_URL.rstrip("/")
    generate_url = base_url if base_url.endswith("/api/generate") else f"{base_url}/api/generate"
    chat_url = base_url if base_url.endswith("/api/chat") else f"{base_url}/api/chat"

    def _post_generate() -> dict | None:
        try:
            r = requests.post(
                generate_url,
                json={
                    "model": config.LOCAL_LLM_MODEL,
                    "prompt": prompt,
                    "system": _SYSTEM_PROMPT,
                    "stream": False,
                    "format": "json",
                },
                timeout=config.LOCAL_LLM_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("local LLM HTTP failed: %s", exc)
            return None

    def _post_chat() -> dict | None:
        try:
            r = requests.post(
                chat_url,
                json={
                    "model": config.LOCAL_LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                },
                timeout=config.LOCAL_LLM_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("local LLM HTTP failed: %s", exc)
            return None

    data = _post_generate()
    if data is None:
        data = _post_chat()
    if not isinstance(data, dict):
        return None

    # Ollama generate returns {"response": "..."}
    if "response" in data:
        return str(data["response"])

    # Ollama chat returns {"message": {"content": "..."}}
    msg = data.get("message")
    if isinstance(msg, dict) and "content" in msg:
        return str(msg["content"])

    return None


def _parse_response(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text.strip()).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, str):
            return json.loads(parsed)
        return parsed
    except Exception:
        # try to extract JSON object from a larger string
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, str):
                    return json.loads(parsed)
                return parsed
            except Exception:
                return None
    return None


def _normalize_decision(payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None
    keep = payload.get("keep")
    confidence = payload.get("confidence")
    reason = payload.get("reason")
    corrected = payload.get("corrected") or {}

    if not isinstance(keep, bool):
        return None
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.0

    if not isinstance(reason, str):
        reason = ""

    if not isinstance(corrected, dict):
        corrected = {}

    return {
        "keep": keep,
        "confidence": max(0.0, min(1.0, confidence)),
        "reason": reason[:400],
        "corrected": corrected,
    }


def _debug_response(raw: str | None, source_key: str) -> None:
    if not raw:
        return
    if not os.getenv("VETTING_DEBUG"):
        return
    snippet = raw.strip().replace("\n", " ")[:300]
    log.warning("vetting raw response for %s: %s", source_key, snippet)


def _build_prompt(kind: str, details: dict[str, Any]) -> str:
    return (
        f"Asset type: {kind}\n"
        "Asset details (JSON):\n"
        f"{json.dumps(details, ensure_ascii=True)}\n"
        "Return JSON only."
    )


def vet_assets() -> None:
    if not config.VETTING_ENABLED:
        log.info("vetting: disabled")
        return

    # Ensure schema exists (asset_vetting table may be missing in existing DBs).
    db.init_db()

    with db._connect() as conn:
        vet_map = db.get_vetting_map(conn)

    vetted = 0
    max_items = config.VETTING_MAX_ITEMS
    if max_items <= 0:
        max_items = 1_000_000_000

    # ── GitHub repo-level assets ─────────────────────────────────────────────
    with db._connect() as conn:
        repos = conn.execute(
            """
            SELECT r.full_name, r.url, r.description, r.stars, r.license,
                   r.asset_paths, r.file_types, r.last_updated
            FROM repos r
            ORDER BY r.last_seen_at DESC
            """
        ).fetchall()

        paper_rows = conn.execute(
            """
            SELECT pr.repo_full_name, p.title, p.abstract, p.published_at
            FROM paper_repos pr
            JOIN papers p ON p.paper_id = pr.paper_id
            """
        ).fetchall()

    papers_by_repo: dict[str, list[dict[str, Any]]] = {}
    for row in paper_rows:
        papers_by_repo.setdefault(row["repo_full_name"], []).append(dict(row))

    total_repos = len(repos)
    log.info("vetting: %d repo candidates (limit=%d)", total_repos, max_items)

    for idx, repo in enumerate(repos, start=1):
        source_key = f"github:{repo['full_name']}"
        if not config.VETTING_FORCE and source_key in vet_map:
            continue
        if vetted >= max_items:
            break

        log.info("vetting: [%d/%d] github %s", idx, total_repos, repo["full_name"])

        details = {
            "name": repo["full_name"],
            "description": repo["description"] or "",
            "url": repo["url"],
            "stars": repo["stars"],
            "license": repo["license"] or "",
            "file_types": json.loads(repo["file_types"] or "[]"),
            "asset_paths": json.loads(repo["asset_paths"] or "[]"),
            "papers": papers_by_repo.get(repo["full_name"], [])[:3],
        }

        prompt = _build_prompt("github_repo", details)
        raw = _call_local_llm(prompt)
        _debug_response(raw, source_key)
        payload = _parse_response(raw or "")
        decision = _normalize_decision(payload or {})
        if decision is None:
            log.warning("vetting: invalid response for %s", source_key)
            continue

        with db._connect() as conn:
            db.upsert_vetting(
                source_key=source_key,
                source_type="github",
                decision="keep" if decision["keep"] else "reject",
                confidence=decision["confidence"],
                reason=decision["reason"],
                corrected=decision["corrected"],
                conn=conn,
            )
        vetted += 1

    # ── Anatomy records ──────────────────────────────────────────────────────
    with db._connect() as conn:
        records = conn.execute(
            "SELECT * FROM anatomy_records ORDER BY discovered_at DESC"
        ).fetchall()

    total_records = len(records)
    log.info("vetting: %d anatomy candidates (limit=%d)", total_records, max_items)

    for idx, rec in enumerate(records, start=1):
        source_key = f"anatomy:{rec['record_id']}"
        if not config.VETTING_FORCE and source_key in vet_map:
            continue
        if vetted >= max_items:
            break

        log.info("vetting: [%d/%d] anatomy %s", idx, total_records, rec["record_id"])

        details = {
            "record_id": rec["record_id"],
            "name": rec["name"],
            "description": rec["description"],
            "source_collection": rec["source_collection"],
            "body_part": rec["body_part"],
            "organ_system": rec["organ_system"],
            "age_group": rec["age_group"],
            "sex": rec["sex"],
            "condition_type": rec["condition_type"],
            "creation_method": rec["creation_method"],
            "file_types": json.loads(rec["file_types"] or "[]"),
            "download_url": rec["download_url"],
            "tags": json.loads(rec["tags"] or "[]"),
            "authors": json.loads(rec["authors"] or "[]"),
            "year": rec["year"],
        }

        prompt = _build_prompt("anatomy_record", details)
        raw = _call_local_llm(prompt)
        _debug_response(raw, source_key)
        payload = _parse_response(raw or "")
        decision = _normalize_decision(payload or {})
        if decision is None:
            log.warning("vetting: invalid response for %s", source_key)
            continue

        with db._connect() as conn:
            db.upsert_vetting(
                source_key=source_key,
                source_type="anatomy",
                decision="keep" if decision["keep"] else "reject",
                confidence=decision["confidence"],
                reason=decision["reason"],
                corrected=decision["corrected"],
                conn=conn,
            )
        vetted += 1

    log.info("vetting: completed %d item(s)", vetted)

    if config.VETTING_CLEANUP:
        _cleanup_rejected()


def _cleanup_rejected() -> None:
    log.info("vetting: cleanup rejected items …")
    with db._connect() as conn:
        rows = conn.execute(
            "SELECT source_key, source_type, reason FROM asset_vetting WHERE decision = 'reject'"
        ).fetchall()

        github_repos: list[str] = []
        anatomy_ids: list[str] = []
        for r in rows:
            key = r["source_key"]
            if r["source_type"] == "github" and key.startswith("github:"):
                github_repos.append(key.split("github:", 1)[1])
            elif r["source_type"] == "anatomy" and key.startswith("anatomy:"):
                anatomy_ids.append(key.split("anatomy:", 1)[1])
            db.ban_source(key, r["source_type"], r["reason"], conn)

        def _chunk(items: list[str], size: int = 200) -> list[list[str]]:
            return [items[i : i + size] for i in range(0, len(items), size)]

        deleted_repos = 0
        for batch in _chunk(github_repos):
            placeholders = ",".join(["?"] * len(batch))
            cur = conn.execute(
                f"DELETE FROM repos WHERE full_name IN ({placeholders})",
                batch,
            )
            deleted_repos += cur.rowcount if cur.rowcount is not None else 0

        deleted_anatomy = 0
        for batch in _chunk(anatomy_ids):
            placeholders = ",".join(["?"] * len(batch))
            cur = conn.execute(
                f"DELETE FROM anatomy_records WHERE record_id IN ({placeholders})",
                batch,
            )
            deleted_anatomy += cur.rowcount if cur.rowcount is not None else 0

    log.info(
        "vetting: cleanup complete (deleted repos=%d, anatomy_records=%d)",
        deleted_repos,
        deleted_anatomy,
    )


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    vet_assets()


if __name__ == "__main__":
    main()
