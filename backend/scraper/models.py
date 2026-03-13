"""
Data models for the SurgSim DB scraper pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ── Enumerations ───────────────────────────────────────────────────────────────

class FileType(str, Enum):
    USD  = "USD"
    USDA = "USDA"
    USDC = "USDC"
    OBJ  = "OBJ"
    STL  = "STL"
    URDF = "URDF"
    FBX  = "FBX"
    PLY  = "PLY"
    GLTF = "GLTF"
    GLB  = "GLB"
    SDF  = "SDF"
    DAE  = "DAE"
    MJCF = "MJCF"
    XML  = "XML"

    @classmethod
    def from_extension(cls, ext: str) -> Optional["FileType"]:
        mapping = {
            ".usd":  cls.USD,
            ".usda": cls.USDA,
            ".usdc": cls.USDC,
            ".obj":  cls.OBJ,
            ".stl":  cls.STL,
            ".urdf": cls.URDF,
            ".fbx":  cls.FBX,
            ".ply":  cls.PLY,
            ".gltf": cls.GLTF,
            ".glb":  cls.GLB,
            ".sdf":  cls.SDF,
            ".dae":  cls.DAE,
            ".mjcf": cls.MJCF,
        }
        return mapping.get(ext.lower() if ext.startswith(".") else f".{ext.lower()}")


class SourceDB(str, Enum):
    ARXIV            = "arxiv"
    PUBMED           = "pubmed"
    SEMANTIC_SCHOLAR = "semantic_scholar"


# ── Core models ────────────────────────────────────────────────────────────────

@dataclass
class GitHubRepo:
    owner: str
    name: str
    url: str
    description: str
    stars: int
    license: Optional[str]
    last_updated: datetime
    detected_file_types: list[FileType] = field(default_factory=list)
    asset_paths: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass
class Paper:
    """
    A paper from any source: arXiv, PubMed, or Semantic Scholar.

    paper_id is the canonical unique key used as the DB primary key:
      - arXiv papers:   "arxiv:2403.12345"
      - PubMed-only:    "pmid:38547123"
      - DOI-only:       "doi:10.1109/LRA.2024.3385652"
    """
    paper_id: str           # canonical key (see above)
    source_db: SourceDB
    title: str
    authors: list[str]
    abstract: str
    published_at: datetime
    updated_at: datetime
    categories: list[str]   # arXiv cats, MeSH terms, or S2 fields-of-study
    pdf_url: str
    # Optional cross-reference IDs
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    pubmed_id: Optional[str] = None
    journal_name: Optional[str] = None
    # Populated after GitHub link extraction
    github_repos: list[GitHubRepo] = field(default_factory=list)
    detected_file_types: list[FileType] = field(default_factory=list)

    @staticmethod
    def make_id(
        arxiv_id: Optional[str] = None,
        pubmed_id: Optional[str] = None,
        doi: Optional[str] = None,
    ) -> str:
        """Return the canonical paper_id from whichever identifier is available."""
        if arxiv_id:
            return f"arxiv:{arxiv_id}"
        if pubmed_id:
            return f"pmid:{pubmed_id}"
        if doi:
            return f"doi:{doi.lower()}"
        raise ValueError("At least one of arxiv_id, pubmed_id, or doi must be provided")


# Keep ArxivPaper as an alias for backwards compatibility with arxiv_client.py
ArxivPaper = Paper


@dataclass
class Asset:
    github_repo_full_name: str
    github_repo_url: str
    paper_id: Optional[str]
    paper_title: Optional[str]
    file_types: list[FileType]
    asset_paths: list[str]
    stars: int
    license: Optional[str]
    last_updated: datetime
    discovered_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScrapeRun:
    started_at: datetime
    finished_at: Optional[datetime] = None
    papers_fetched: int = 0
    repos_scanned: int = 0
    assets_added: int = 0
    assets_updated: int = 0
    errors: list[str] = field(default_factory=list)
