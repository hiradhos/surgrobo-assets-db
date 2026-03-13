"""
GitHub client for the SurgSim DB scraper.

Responsibilities
────────────────
1. Extract GitHub repository URLs from arXiv paper text (abstract + title).
2. Fetch repo metadata (stars, license, last updated) via the GitHub REST API.
3. Walk the full file tree of a repo and detect simulation asset files
   (.usd, .stl, .urdf, .obj, .ply, .gltf, .sdf, .dae, .mjcf, .fbx, …).
4. For XML files, fetch the first 512 bytes to confirm MuJoCo/Gazebo markers.
5. Respect GitHub rate limits; back off automatically on 429/403 responses.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from . import config
from .models import FileType, GitHubRepo

log = logging.getLogger(__name__)

# ── GitHub REST API helpers ────────────────────────────────────────────────────

_GH_API = "https://api.github.com"
# Capture owner and repo name; allow dots/hyphens/underscores inside names.
# Sanitisation (strip .git, trailing punctuation) is done in extract_github_urls.
_GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
# Trailing characters that are sentence punctuation, not part of a repo name.
_TRAILING_PUNCT = re.compile(r"[.\-_,;:!?)>\]\"']+$")


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SurgSimDB-Scraper/1.0",
    }
    if config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return h


def _get(url: str, params: dict | None = None, *, retries: int = 3) -> dict | list | None:
    """
    GET a GitHub API endpoint.  Handles rate limiting with exponential backoff.
    Returns the parsed JSON or None on permanent failure.
    """
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=20)
        except requests.RequestException as exc:
            log.warning("GitHub GET failed (%s): %s", url, exc)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            _check_rate_limit(resp)
            return resp.json()

        if resp.status_code in (429, 403):
            # rate limited — honour Retry-After or back off exponentially
            retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 2)))
            reset_at = resp.headers.get("X-RateLimit-Reset")
            if reset_at:
                wait = max(0, int(reset_at) - int(time.time())) + 5
                retry_after = min(wait, 120)
            log.warning("GitHub rate limit hit. Sleeping %ds …", retry_after)
            time.sleep(retry_after)
            continue

        if resp.status_code == 404:
            log.debug("GitHub 404: %s", url)
            return None

        log.warning("GitHub %d for %s", resp.status_code, url)
        return None

    log.error("GitHub GET gave up after %d retries: %s", retries, url)
    return None


def _check_rate_limit(resp: requests.Response) -> None:
    remaining = int(resp.headers.get("X-RateLimit-Remaining", 9999))
    limit     = int(resp.headers.get("X-RateLimit-Limit", 9999))
    # Only throttle when below 10% of this endpoint's actual limit.
    # Avoids false positives on the search API (limit=30) vs the core API (limit=5000).
    threshold = max(5, limit // 10)
    if remaining < threshold:
        reset_at = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait = max(0, reset_at - int(time.time())) + 5
        log.warning("GitHub rate limit low (%d/%d remaining). Sleeping %ds …", remaining, limit, wait)
        time.sleep(wait)


# ── URL extraction ─────────────────────────────────────────────────────────────

def extract_github_urls(text: str) -> list[tuple[str, str]]:
    """
    Return a list of (owner, repo_name) tuples found in `text`.
    Deduplicates and filters out obviously wrong entries (e.g. "github.com/topics/…").
    """
    SKIP_OWNERS = {"topics", "explore", "trending", "marketplace", "features", "about", "login", "signup"}
    SKIP_REPOS  = {"issues", "pulls", "releases", "wiki", "tree", "blob", "commit", "compare"}

    seen: set[tuple[str, str]] = set()
    results: list[tuple[str, str]] = []

    for m in _GITHUB_REPO_RE.finditer(text):
        owner = _TRAILING_PUNCT.sub("", m.group(1))
        repo  = _TRAILING_PUNCT.sub("", m.group(2))
        # Strip .git clone suffix
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        if not owner or not repo:
            continue
        if owner.lower() in SKIP_OWNERS or repo.lower() in SKIP_REPOS:
            continue
        key = (owner.lower(), repo.lower())
        if key not in seen:
            seen.add(key)
            results.append((owner, repo))

    return results


# ── Repo metadata ──────────────────────────────────────────────────────────────

def fetch_repo_metadata(owner: str, name: str) -> GitHubRepo | None:
    """
    Fetch repository metadata from the GitHub REST API.
    Returns None if the repo is not found or inaccessible.
    """
    data = _get(f"{_GH_API}/repos/{owner}/{name}")
    if not data or not isinstance(data, dict):
        return None

    # Skip repos below the minimum star threshold
    stars = int(data.get("stargazers_count", 0))
    if stars < config.MIN_STARS:
        log.debug("Skipping %s/%s (stars=%d < threshold)", owner, name, stars)
        return None

    license_name: str | None = None
    if data.get("license") and isinstance(data["license"], dict):
        license_name = data["license"].get("spdx_id") or data["license"].get("name")

    pushed_at_raw = data.get("pushed_at") or data.get("updated_at", "1970-01-01T00:00:00Z")
    last_updated = _parse_gh_datetime(pushed_at_raw)

    return GitHubRepo(
        owner=owner,
        name=name,
        url=data.get("html_url", f"https://github.com/{owner}/{name}"),
        description=data.get("description") or "",
        stars=stars,
        license=license_name,
        last_updated=last_updated,
    )


def _parse_gh_datetime(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw.rstrip("Z")).replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


# ── Asset file detection ───────────────────────────────────────────────────────

def _is_xml_asset(owner: str, name: str, path: str) -> bool:
    """
    Return True if an .xml file looks like a MuJoCo or Gazebo world/robot file.
    Fetches only the first 512 bytes to check for known markers.
    """
    url = f"{_GH_API}/repos/{owner}/{name}/contents/{path}"
    data = _get(url)
    if not data or not isinstance(data, dict):
        return False

    # GitHub contents API returns base64-encoded content
    import base64
    raw_b64: str = data.get("content", "")
    if not raw_b64:
        return False

    try:
        content = base64.b64decode(raw_b64.replace("\n", ""))[:512]
    except Exception:
        return False

    return any(marker in content for marker in config.XML_MUJOCO_MARKERS)


def scan_repo_for_assets(repo: GitHubRepo) -> GitHubRepo:
    """
    Walk the repository's git tree and populate:
      - repo.detected_file_types
      - repo.asset_paths

    Uses the GitHub recursive tree API to get the full file list in one request.
    For XML files, falls back to content inspection.
    Returns the same repo object (mutated in-place) for convenience.
    """
    # Fetch the default branch's latest commit SHA
    repo_data = _get(f"{_GH_API}/repos/{repo.owner}/{repo.name}")
    if not repo_data or not isinstance(repo_data, dict):
        return repo

    default_branch = repo_data.get("default_branch", "main")
    branch_data = _get(f"{_GH_API}/repos/{repo.owner}/{repo.name}/branches/{default_branch}")
    if not branch_data or not isinstance(branch_data, dict):
        return repo

    sha = branch_data.get("commit", {}).get("sha", "")
    if not sha:
        return repo

    # Fetch the full recursive tree (one request covers the whole repo)
    tree_data = _get(
        f"{_GH_API}/repos/{repo.owner}/{repo.name}/git/trees/{sha}",
        params={"recursive": "1"},
    )
    if not tree_data or not isinstance(tree_data, dict):
        return repo

    if tree_data.get("truncated"):
        log.warning("%s: tree truncated (large repo); asset scan may be incomplete", repo.full_name)

    tree: list[dict[str, Any]] = tree_data.get("tree", [])
    found_types: set[FileType] = set()
    found_paths: list[str] = []
    xml_candidates: list[str] = []
    node_count = 0

    for node in tree:
        if node.get("type") != "blob":
            continue
        path: str = node.get("path", "")
        node_count += 1
        if node_count > config.MAX_TREE_NODES:
            log.debug("%s: hit MAX_TREE_NODES=%d, stopping early", repo.full_name, config.MAX_TREE_NODES)
            break

        # Skip paths inside ignored directories
        parts = path.split("/")
        if any(part in config.SKIP_DIRS for part in parts[:-1]):
            continue

        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""

        if ext == ".xml":
            xml_candidates.append(path)
            continue

        ft = FileType.from_extension(ext)
        if ft is not None:
            found_types.add(ft)
            found_paths.append(path)

    # Inspect XML candidates (limit to 10 to avoid excess API calls)
    for xml_path in xml_candidates[:10]:
        if _is_xml_asset(repo.owner, repo.name, xml_path):
            found_types.add(FileType.MJCF)
            found_paths.append(xml_path)

    repo.detected_file_types = sorted(found_types, key=lambda x: x.value)
    repo.asset_paths = found_paths[:200]  # cap stored paths at 200

    log.info(
        "%s: scanned %d nodes, found %d asset files, types=%s",
        repo.full_name,
        node_count,
        len(found_paths),
        [ft.value for ft in repo.detected_file_types],
    )
    return repo


# ── Direct GitHub search (supplement to arXiv extraction) ────────────────────

def search_github_for_surgical_repos(page: int = 1) -> list[GitHubRepo]:
    """
    Use the GitHub Code Search API to find repos that contain simulation
    asset files and relate to surgical robotics.

    This provides a secondary discovery path independent of arXiv links.
    Note: GitHub search API is heavily rate-limited (10 req/min unauth, 30 auth).
    """
    QUERIES = [
        "surgical robot URDF simulation",
        "surgical robot USD Isaac Sim",
        "da Vinci robot MuJoCo",
        "laparoscopic simulation URDF STL",
        "robotic surgery reinforcement learning MJCF",
    ]

    repos: list[GitHubRepo] = []
    seen: set[str] = set()

    for query in QUERIES:
        data = _get(
            f"{_GH_API}/search/repositories",
            params={
                "q": query,
                "sort":     "stars",
                "order":    "desc",
                "per_page": 10,
                "page":     page,
            },
        )
        if not data or not isinstance(data, dict):
            continue

        for item in data.get("items", []):
            full_name: str = item.get("full_name", "")
            if full_name in seen:
                continue
            seen.add(full_name)

            owner, _, name = full_name.partition("/")
            stars = int(item.get("stargazers_count", 0))
            if stars < config.MIN_STARS:
                continue

            license_name = None
            if item.get("license") and isinstance(item["license"], dict):
                license_name = item["license"].get("spdx_id")

            repos.append(GitHubRepo(
                owner=owner,
                name=name,
                url=item.get("html_url", f"https://github.com/{full_name}"),
                description=item.get("description") or "",
                stars=stars,
                license=license_name,
                last_updated=_parse_gh_datetime(item.get("pushed_at", "1970-01-01T00:00:00Z")),
            ))

        # GitHub search rate-limit: be conservative
        time.sleep(3)

    return repos
