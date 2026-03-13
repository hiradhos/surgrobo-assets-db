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
ARXIV_CATEGORIES: list[str] = [
    "cs.RO",   # robotics
    "cs.AI",   # AI / agents
    "cs.LG",   # machine learning / RL
    "cs.CV",   # computer vision (surgical video, segmentation)
    "cs.GR",   # graphics (3-D assets, rendering)
    "eess.SY", # systems & control
]

# Free-text search terms sent to the arXiv API.
#
# Structure: list of clusters.
#   • Terms within a cluster are OR-combined.
#   • Clusters are AND-combined with each other.
#
# Using a SINGLE cluster (list of one sub-list) means a pure OR search —
# any paper mentioning any of these terms will be fetched.  This is
# intentionally broad: the asset-detection step at the GitHub level does
# the real filtering.  Better to over-fetch papers and find repos than to
# miss them because an abstract never used the word "simulation".
ARXIV_QUERY_CLUSTERS: list[list[str]] = [
    [
        # ── surgical platforms ──────────────────────────────────────────
        "surgical robot",
        "robotic surgery",
        "robot-assisted surgery",
        "autonomous surgery",
        "da Vinci",
        "Versius",
        "RAVEN II",
        "Senhance",
        "Hugo RAS",
        # ── procedure / anatomy terms ───────────────────────────────────
        "laparoscopic",
        "endoscopic",
        "minimally invasive surgery",
        "cholecystectomy",
        "prostatectomy",
        "hysterectomy",
        "anastomosis",
        "suturing",
        "needle driving",
        "tissue manipulation",
        "tissue deformation",
        "soft tissue",
        # ── simulation / environment terms ──────────────────────────────
        "surgical simulation",
        "robot simulation",
        "sim-to-real",
        "Isaac Sim",
        "Isaac Lab",
        "ORBIT simulation",
        "MuJoCo",
        "Gazebo",
        "PyBullet",
        "SAPIEN",
        "robosuite",
        # ── asset / format terms ─────────────────────────────────────────
        "URDF",
        "USD scene",
        "Universal Scene Description",
        "MJCF",
        "robot model",
        "phantom model",
        "3D mesh",
        # ── learning paradigms ───────────────────────────────────────────
        "reinforcement learning",
        "imitation learning",
        "learning from demonstration",
        "surgical skill",
        "surgical training",
        "dexterous manipulation",
        "teleoperation",
    ],
]

# How many days back to search on each incremental weekly run.
# Use --lookback-days on the CLI to override for a one-off back-fill.
ARXIV_LOOKBACK_DAYS: int = int(os.getenv("ARXIV_LOOKBACK_DAYS", "90"))

# Maximum papers to retrieve per run (arXiv API hard cap is 2000).
ARXIV_MAX_RESULTS: int = int(os.getenv("ARXIV_MAX_RESULTS", "500"))

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
