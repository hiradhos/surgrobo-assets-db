"""
PubMed E-utilities client for the Netter-DB scraper.

Covers journals that rarely appear on arXiv:
  • IEEE Transactions on Medical Robotics and Bionics (T-MRB)
  • IEEE Robotics and Automation Letters (RA-L)
  • International Journal of Medical Robotics and Computer Assisted Surgery
  • Surgical Endoscopy
  • Journal of Robotic Surgery
  • Medical Image Analysis
  • IEEE Transactions on Biomedical Engineering
  • Annals of Biomedical Engineering
  • Computerized Medical Imaging and Graphics
  • Computer Methods and Programs in Biomedicine

No API key required. Rate limit: 3 req/s without key, 10 req/s with NCBI key.
Docs: https://www.ncbi.nlm.nih.gov/books/NBK25499/
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Generator

import requests

from . import config
from .models import Paper, SourceDB

log = logging.getLogger(__name__)

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Prestigious surgical robotics / medical robotics journals indexed in PubMed.
# The [TA] tag searches Journal Title Abbreviation; [JT] searches full title.
TARGET_JOURNALS: list[str] = [
    "IEEE Trans Med Robot Bionics",
    "IEEE Robot Autom Lett",
    "Int J Med Robot",           # IJMRCAS
    "Surg Endosc",               # Surgical Endoscopy
    "J Robot Surg",              # Journal of Robotic Surgery
    "Med Image Anal",            # Medical Image Analysis
    "IEEE Trans Biomed Eng",
    "Ann Biomed Eng",
    "Comput Med Imaging Graph",
    "Comput Methods Programs Biomed",
    "J Neuroeng Rehabil",        # covers surgical neurorobotics
    "IEEE Trans Neural Syst Rehabil Eng",
    "Biomed Eng Online",
    "Int J Comput Assist Radiol Surg",   # IJCARS
    "Surg Innov",                # Surgical Innovation
]

# Two sets of terms — a paper must match at least one from EACH set:
#   SURGICAL_TERMS  — establishes the surgical/anatomical context
#   ASSET_TERMS     — establishes that simulation assets or environments are involved
#
# The _build_query function ANDs the two clauses together, so a paper must
# be about surgery AND mention simulation/assets to qualify.

PUBMED_SURGICAL_TERMS: list[str] = [
    "surgical robot",
    "robotic surgery",
    "robot-assisted surgery",
    "laparoscopic surgery",
    "minimally invasive surgery",
    "endoscopic surgery",
    "autonomous surgery",
    "surgical suturing",
    "needle driving",
    "tissue manipulation",
    "tissue deformation",
    "soft tissue simulation",
    "surgical dissection",
    "surgical phantom",
    "anatomical model",
    "organ model",
    "deformable tissue",
    "intraoperative",
    "cholecystectomy",
    "prostatectomy",
    "hysterectomy",
    "anastomosis",
    "surgical training simulator",
]

PUBMED_ASSET_TERMS: list[str] = [
    "URDF",
    "MJCF",
    "MuJoCo",
    "Isaac Sim",
    "Gazebo",
    "PyBullet",
    "simulation environment",
    "simulation asset",
    "robot model",
    "3D model",
    "physics simulation",
    "reinforcement learning",
    "sim-to-real",
    "robot learning",
    "simulation platform",
    "virtual environment",
]

_REQUEST_DELAY = 0.4  # seconds between requests (safe for 3 req/s limit)


def _get(url: str, params: dict, *, retries: int = 3) -> requests.Response | None:
    for attempt in range(retries):
        try:
            resp = requests.get(
                url, params=params, timeout=20,
                headers={"User-Agent": "NetterDB-Scraper/1.0"},
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            log.warning("PubMed request failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 ** attempt)
    return None


def _parse_pubmed_xml(xml_text: str) -> list[Paper]:
    """Parse PubMed efetch XML (PubmedArticleSet format) into Paper objects."""
    papers: list[Paper] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.error("PubMed XML parse error: %s", exc)
        return papers

    for article in root.findall(".//PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            if medline is None:
                continue

            pmid_el = medline.find("PMID")
            pubmed_id = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else None
            if not pubmed_id:
                continue

            art = medline.find("Article")
            if art is None:
                continue

            # Title
            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()).strip() if title_el is not None else ""
            if not title:
                continue

            # Abstract
            abstract_parts: list[str] = []
            for ab in art.findall(".//AbstractText"):
                label = ab.get("Label", "")
                text  = "".join(ab.itertext()).strip()
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)

            # Authors
            authors: list[str] = []
            for author in art.findall(".//Author"):
                last  = (author.findtext("LastName")  or "").strip()
                first = (author.findtext("ForeName")  or "").strip()
                if last:
                    authors.append(f"{last}, {first[0]}." if first else last)

            # Journal
            journal_el = art.find("Journal")
            journal_name = ""
            if journal_el is not None:
                jt = journal_el.findtext("Title") or journal_el.findtext("ISOAbbreviation") or ""
                journal_name = jt.strip()

            # Publication date
            pub_date = _parse_pubmed_date(art)

            # DOI
            doi: str | None = None
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi" and id_el.text:
                    doi = id_el.text.strip().lower()
                    break

            # arXiv cross-reference (some papers deposit to both)
            arxiv_id: str | None = None
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "pii" and id_el.text and "arxiv" in id_el.text.lower():
                    arxiv_id = id_el.text.strip()
                    break

            # MeSH headings as categories
            categories: list[str] = [
                mh.findtext("DescriptorName") or ""
                for mh in medline.findall(".//MeshHeading")
                if mh.findtext("DescriptorName")
            ]

            pdf_url = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
            if doi:
                pdf_url = f"https://doi.org/{doi}"

            paper_id = Paper.make_id(arxiv_id=arxiv_id, pubmed_id=pubmed_id, doi=doi)

            papers.append(Paper(
                paper_id=paper_id,
                source_db=SourceDB.PUBMED,
                title=title,
                authors=authors,
                abstract=abstract,
                published_at=pub_date,
                updated_at=pub_date,
                categories=categories,
                pdf_url=pdf_url,
                arxiv_id=arxiv_id,
                doi=doi,
                pubmed_id=pubmed_id,
                journal_name=journal_name,
            ))

        except Exception as exc:
            log.debug("Skipping PubMed article: %s", exc)
            continue

    return papers


def _parse_pubmed_date(art_el: ET.Element) -> datetime:
    """Extract the best available publication date from an Article element."""
    # Try ArticleDate (electronic pub date — most precise)
    for ad in art_el.findall("ArticleDate"):
        try:
            y = int(ad.findtext("Year") or 0)
            m = int(ad.findtext("Month") or 1)
            d = int(ad.findtext("Day") or 1)
            if y:
                return datetime(y, m, d, tzinfo=timezone.utc)
        except ValueError:
            pass

    # Fall back to Journal/JournalIssue/PubDate
    pub_date = art_el.find(".//JournalIssue/PubDate")
    if pub_date is not None:
        try:
            y = int(pub_date.findtext("Year") or 0)
            m_str = pub_date.findtext("Month") or "1"
            # Month can be "Jan", "Feb", etc.
            try:
                m = int(m_str)
            except ValueError:
                m = datetime.strptime(m_str[:3], "%b").month
            d = int(pub_date.findtext("Day") or 1)
            if y:
                return datetime(y, m, d, tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            pass

    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _build_query(lookback_days: int) -> str:
    """
    Build a PubMed query:
      (journal filter) AND (surgical terms) AND (asset/sim terms) AND (date range)

    Both content clauses must match so papers are specifically about surgical
    robotics simulation — not just any surgery or any simulation paper.
    """
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    date_filter = f"{since.strftime('%Y/%m/%d')}:3000/01/01[dp]"

    journal_clause  = " OR ".join(f'"{j}"[ta]' for j in TARGET_JOURNALS)
    surgical_clause = " OR ".join(f'"{t}"[tiab]' for t in PUBMED_SURGICAL_TERMS)
    asset_clause    = " OR ".join(f'"{t}"[tiab]' for t in PUBMED_ASSET_TERMS)

    return (
        f"({journal_clause}) AND ({surgical_clause}) AND ({asset_clause})"
        f" AND ({date_filter})"
    )


def fetch_papers(
    known_pubmed_ids: set[str] | None = None,
    lookback_days: int = config.ARXIV_LOOKBACK_DAYS,
    max_results: int = config.ARXIV_MAX_RESULTS,
) -> Generator[Paper, None, None]:
    """
    Yield Paper objects from targeted surgical-robotics journals via PubMed.
    Deduplicates against `known_pubmed_ids`.
    """
    known_pubmed_ids = known_pubmed_ids or set()
    query = _build_query(lookback_days)

    log.info("PubMed query: %s", query[:120] + ("…" if len(query) > 120 else ""))

    # Step 1: esearch — get matching PMIDs
    resp = _get(_ESEARCH, {
        "db": "pubmed", "term": query,
        "retmax": str(max_results),
        "retmode": "json",
        "usehistory": "y",
    })
    if resp is None:
        log.error("PubMed esearch failed")
        return

    data = resp.json()
    pmids: list[str] = data.get("esearchresult", {}).get("idlist", [])
    total = int(data.get("esearchresult", {}).get("count", 0))
    log.info("PubMed esearch: %d total matches, fetching %d", total, len(pmids))

    if not pmids:
        return

    # Filter known
    new_pmids = [p for p in pmids if p not in known_pubmed_ids]
    log.info("PubMed: %d new (not yet in DB)", len(new_pmids))
    if not new_pmids:
        return

    time.sleep(_REQUEST_DELAY)

    # Step 2: efetch — retrieve full records in batches of 100
    BATCH = 100
    yielded = 0
    for i in range(0, len(new_pmids), BATCH):
        batch = new_pmids[i : i + BATCH]
        resp = _get(_EFETCH, {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
            "rettype": "abstract",
        })
        if resp is None:
            log.warning("PubMed efetch failed for batch starting at index %d", i)
            time.sleep(_REQUEST_DELAY)
            continue

        papers = _parse_pubmed_xml(resp.text)
        for paper in papers:
            log.debug("  PubMed: %s — %s", paper.pubmed_id, paper.title[:60])
            yield paper
            yielded += 1

        time.sleep(_REQUEST_DELAY)

    log.info("PubMed fetch complete: %d new papers", yielded)
