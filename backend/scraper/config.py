"""
Configuration for the SurgSim DB scraper.

All tuneable parameters live here. Override via environment variables
(loaded from a .env file at the repo root) or edit directly.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


# ── Anthropic ──────────────────────────────────────────────────────────────────

# API key for the Claude classifier (Phase 5). Set in .env or environment.
# If unset, Phase 5 is skipped and repos will have no category labels.
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# Model used for repo classification.
CLASSIFIER_MODEL: str = os.getenv("CLASSIFIER_MODEL", "claude-opus-4-6")


# ── Anatomy database scrapers ──────────────────────────────────────────────────

# Which anatomy sources to scrape.  Remove a key to disable that source.
# All sources are enabled by default; comment out any you want to skip.
_ANATOMY_SOURCES_DEFAULT = ",".join([
    "humanatlas",   # HuBMAP Human Reference Atlas 3D library
    "nih3d",        # NIH 3D Print Exchange (human anatomy collection)
    "medshapenet",  # MedShapeNet 2.0 (CT/MRI-derived medical shapes)
    "bodyparts3d",  # BodyParts3D (Visible Human Project OBJ meshes)
    "anatomytool",  # AnatomyTool.org open 3D model library
    "sketchfab",    # Sketchfab (downloadable anatomy/medical models)
    "embodi3d",     # Embodi3D (CT/MRI-to-STL community platform)
    # "thingiverse", # Thingiverse — requires THINGIVERSE_TOKEN, opt-in
])
ANATOMY_SOURCES: list[str] = [
    s.strip()
    for s in os.getenv("ANATOMY_SOURCES", _ANATOMY_SOURCES_DEFAULT).split(",")
    if s.strip()
]

# Optional Thingiverse API token (https://www.thingiverse.com/apps/create).
# Only needed if "thingiverse" is added to ANATOMY_SOURCES.
THINGIVERSE_TOKEN: str = os.getenv("THINGIVERSE_TOKEN", "")


# ── GitHub ─────────────────────────────────────────────────────────────────────

# Personal access token — requires public_repo scope only.
# Without a token the GitHub API allows 60 req/hr; with one it's 5000 req/hr.
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

# Maximum number of files to inspect per repo tree traversal.
# Repos with > MAX_TREE_NODES files are still scanned but capped here.
MAX_TREE_NODES: int = int(os.getenv("MAX_TREE_NODES", "5000"))

# Minimum GitHub stars for a repo to be included in the database.
# Set to 0 to disable filtering — recommended for academic surgical robotics
# repos which are often newly published and have few stars.
MIN_STARS: int = int(os.getenv("MIN_STARS", "0"))


# ── arXiv ──────────────────────────────────────────────────────────────────────

# arXiv categories to search within.
# Kept tight: cs.RO (robotics) and cs.CV (surgical vision) are the primary homes
# for surgical-robotics simulation papers; eess.IV covers medical image analysis.
ARXIV_CATEGORIES: list[str] = [
    "cs.RO",   # robotics
    "cs.CV",   # computer vision (surgical video, segmentation)
    "eess.IV", # image and video processing (medical imaging / anatomy)
]

# Free-text search terms sent to the arXiv API.
#
# Structure: list of clusters.
#   • Terms within a cluster are OR-combined.
#   • Clusters are AND-combined with each other.
#
# TWO clusters means a paper must match BOTH to be returned:
#   Cluster 1 — surgical / anatomical context  (filters out general robotics)
#   Cluster 2 — simulation / asset context     (filters out pure clinical papers)
#
# This prevents general robot-learning papers (e.g. dexterous-hand manipulation,
# quadruped locomotion) from being included just because they use MuJoCo/URDF.
ARXIV_QUERY_CLUSTERS: list[list[str]] = [
    # ── Cluster 1: surgical / anatomical context (must match at least one) ──
    [
        # surgical platforms
        "surgical robot",
        "robotic surgery",
        "robot-assisted surgery",
        "autonomous surgery",
        "da Vinci",
        "Versius",
        "RAVEN-II",
        "Senhance",
        "Hugo RAS",
        "laparoscopic robot",
        "endoscopic robot",
        # procedures / clinical context
        "laparoscopic surgery",
        "endoscopic surgery",
        "minimally invasive surgery",
        "cholecystectomy",
        "prostatectomy",
        "hysterectomy",
        "anastomosis",
        "surgical suturing",
        "needle driving",
        "surgical dissection",
        "surgical cutting",
        "intraoperative",
        "trocar",
        "instrument tracking",
        # anatomy / tissue
        "anatomical model",
        "organ model",
        "tissue deformation",
        "soft tissue simulation",
        "surgical phantom",
        "deformable organ",
        "abdominal anatomy",
        "surgical training simulation",
    ],
    # ── Cluster 2: simulation / asset context (must match at least one) ────
    [
        "URDF",
        "MJCF",
        "MuJoCo",
        "Isaac Sim",
        "Isaac Lab",
        "Gazebo simulation",
        "PyBullet",
        "SAPIEN simulator",
        "USD scene",
        "Universal Scene Description",
        "simulation environment",
        "robot model",
        "3D mesh",
        "simulation asset",
        "physics simulation",
        "robot description format",
        "sim-to-real transfer",
        "reinforcement learning environment",
        "robot learning simulation",
    ],
]

# How many days back to search on each incremental weekly run.
# Set to 5 years for the initial back-fill; weekly runs override this via CLI.
ARXIV_LOOKBACK_DAYS: int = int(os.getenv("ARXIV_LOOKBACK_DAYS", "1825"))

# Maximum papers to retrieve per run (arXiv API hard cap is 2000).
ARXIV_MAX_RESULTS: int = int(os.getenv("ARXIV_MAX_RESULTS", "2000"))

# Seconds to wait between arXiv API requests (be a good citizen).
ARXIV_REQUEST_DELAY: float = float(os.getenv("ARXIV_REQUEST_DELAY", "3.0"))


# ── Asset detection ────────────────────────────────────────────────────────────

# File extensions that indicate a simulation asset.
ASSET_EXTENSIONS: frozenset[str] = frozenset({
    ".usd", ".usda", ".usdc",   # Universal Scene Description
    ".obj",                     # Wavefront OBJ
    ".stl",                     # STereoLithography
    ".urdf",                    # Unified Robot Description Format
    ".fbx",                     # Autodesk FBX
    ".ply",                     # Polygon File Format
    ".gltf", ".glb",            # GL Transmission Format
    ".sdf",                     # Simulation Description Format (Gazebo)
    ".dae",                     # COLLADA
    ".mjcf",                    # MuJoCo XML (explicit extension)
})

# XML files are only counted if they are likely MuJoCo or Gazebo scene files.
# We check for these markers inside the file content (first 512 bytes).
XML_MUJOCO_MARKERS: tuple[bytes, ...] = (
    b"<mujoco",
    b"<robot",
    b"<sdf",
    b"<world",
)

# Directories that almost certainly do NOT contain simulation assets.
# Repos whose root matches one of these will be skipped during tree traversal.
SKIP_DIRS: frozenset[str] = frozenset({
    "node_modules", ".git", "__pycache__", ".github",
    "docs", "doc", "paper", "papers", "latex",
    "test", "tests", "examples/docs",
})


# ── Database ───────────────────────────────────────────────────────────────────

DB_PATH: Path = Path(os.getenv(
    "DB_PATH",
    str(Path(__file__).resolve().parents[2] / "data" / "surgsim.db"),
))

# Ensure the data directory exists at import time.
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── MedShapeNet local assets ────────────────────────────────────────────────

MEDSHAPENET_ASSETS_DIR: Path = Path(os.getenv(
    "MEDSHAPENET_ASSETS_DIR",
    str(Path(__file__).resolve().parents[2] / "medshapenet_assets"),
))

MEDSHAPENET_MANIFEST_PATH: Path = Path(os.getenv(
    "MEDSHAPENET_MANIFEST_PATH",
    str(MEDSHAPENET_ASSETS_DIR / "manifest.json"),
))

MEDSHAPENET_PREVIEW_DIR: Path = Path(os.getenv(
    "MEDSHAPENET_PREVIEW_DIR",
    str(Path(__file__).resolve().parents[2] / "public" / "medshapenet_previews"),
))

MEDSHAPENET_PREVIEW_BASE_URL: str = os.getenv(
    "MEDSHAPENET_PREVIEW_BASE_URL",
    "/medshapenet_previews",
)


# ── Local LLM vetting ─────────────────────────────────────────────────────────

# Enable/disable local LLM vetting. Set to "0" to disable.
VETTING_ENABLED: bool = os.getenv("VETTING_ENABLED", "1").lower() not in ("0", "false", "no")

# Maximum number of assets to vet per run (to keep runtimes bounded).
VETTING_MAX_ITEMS: int = int(os.getenv("VETTING_MAX_ITEMS", "200"))

# Re-run vetting even if a record already has a decision.
VETTING_FORCE: bool = os.getenv("VETTING_FORCE", "0").lower() in ("1", "true", "yes")

# Delete rejected items from the database after vetting.
VETTING_CLEANUP: bool = os.getenv("VETTING_CLEANUP", "0").lower() in ("1", "true", "yes")

# Local LLM backend: "ollama" (HTTP) or "command".
LOCAL_LLM_BACKEND: str = os.getenv("LOCAL_LLM_BACKEND", "ollama")
LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "llama3")
LOCAL_LLM_URL: str = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/api/generate")

# If using LOCAL_LLM_BACKEND=command, this command will be executed and passed the prompt via stdin.
# Example: "ollama run llama3"
LOCAL_LLM_COMMAND: str = os.getenv("LOCAL_LLM_COMMAND", "ollama run llama3")

# Seconds to wait for a local LLM response.
LOCAL_LLM_TIMEOUT: int = int(os.getenv("LOCAL_LLM_TIMEOUT", "120"))


# ── Admin API ────────────────────────────────────────────────────────────────

ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS: str = os.getenv("ADMIN_PASS", "choggedFunction69")
ADMIN_BIND: str = os.getenv("ADMIN_BIND", "127.0.0.1")
ADMIN_PORT: int = int(os.getenv("ADMIN_PORT", "8123"))


# ── Scheduler ─────────────────────────────────────────────────────────────────

# Day of week for the automatic weekly run ("monday" … "sunday").
SCHEDULE_DAY: str = os.getenv("SCHEDULE_DAY", "sunday")

# Time of day in HH:MM (24-hr, UTC) for the weekly run.
SCHEDULE_TIME: str = os.getenv("SCHEDULE_TIME", "02:00")


# ── Logging ────────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Path | None = (
    Path(os.environ["LOG_FILE"]) if "LOG_FILE" in os.environ else None
)
