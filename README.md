# surgrobo-assets-db

**SurgSim DB** — a Surgical Robotics Asset Database that automatically discovers and catalogues simulation assets from surgical robotics research.

## Overview

A tool that mines academic literature and associated GitHub repositories to build a searchable database of **simulation assets** (3D models, robot descriptions, environments, etc.) for surgical robotics research.

## Architecture

### Backend (Python scraper) — `backend/scraper/`

Runs a multi-phase pipeline on a weekly schedule (every Sunday at 02:00 UTC):

- **Phase 1a** — arXiv: fetch surgical-robotics preprints matching keyword clusters
- **Phase 1b** — PubMed: fetch papers from targeted medical/surgical robotics journals
- **Phase 1c** — Semantic Scholar: fetch papers from ICRA, IROS, MICCAI, Hamlyn, etc.
- **Phase 2** — GitHub link extraction: parse paper abstracts/titles for repo URLs
- **Phase 3** — Direct GitHub search: secondary repo discovery pass
- **Phase 4** — Repo scanning: fetch metadata and walk git tree for simulation assets
- **Phase 5** — Persist: upsert papers, repos, assets, and audit record into SQLite

Detected asset file types: `URDF`, `USD`, `USDA`, `USDC`, `OBJ`, `STL`, `MJCF`, `GLTF`, `GLB`, `SDF`, `DAE`, `FBX`, `PLY`

### Frontend (React/Vite) — `src/`

A React web app for browsing the collected asset database.

## Data Models

| Model | Description |
|---|---|
| `Paper` | A research paper from arXiv, PubMed, or Semantic Scholar |
| `GitHubRepo` | A GitHub repo with detected simulation assets |
| `Asset` | A specific asset file/type found in a repo |
| `ScrapeRun` | Audit record of each scraper execution |

Paper IDs follow a canonical format: `arxiv:<id>`, `pmid:<id>`, or `doi:<id>`.

## Usage

```bash
# Run a single scrape cycle immediately
python -m backend.scraper.run --once

# Run as a persistent weekly process
python -m backend.scraper.run

# Back-fill with a longer lookback window
python -m backend.scraper.run --once --lookback-days 90

# Override schedule via environment variables
SCHEDULE_DAY=monday SCHEDULE_TIME=03:30 python -m backend.scraper.run
```

## Data

The SQLite database is stored at `data/surgsim.db`.
