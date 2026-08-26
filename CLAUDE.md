# CLAUDE.md

Guide for working in this repo with Claude Code. Read `PLAN.md` first — it has the goal, architecture, and full phase breakdown. This file is about how to work in the code day to day, not about what to build.

## What this project is

A graph-based movie explorer (inspired by ResearchRabbit): navigate from one movie to others connected by director, cast, genre, or taste-based similarity (computed from real ratings), with year/decade filters and a timeline view. Runs self-hosted on your own VPS, with no external API calls in production — all data is loaded once from public datasets (MovieLens, IMDb non-commercial datasets).

## Stack

- **Database**: Neo4j Community Edition (Docker)
- **API**: FastAPI (Python) — see `api/`
- **Frontend**: Vite + Cytoscape.js — see `frontend/`
- **Ingestion**: Python scripts in `ingestion/`, run manually, not on every deploy
- **Deploy**: Docker Compose + nginx, in `docker/`

## Structure

```
ingestion/    scripts that load data into Neo4j (run by hand, once or when refreshing the dataset)
api/          FastAPI app, exposes the endpoints the frontend uses
frontend/     SPA with the interactive graph
docker/       docker-compose.yml and nginx configs
docs/         additional technical notes, if needed
PLAN.md       project goal, architecture, and phases — read before touching code
```

## Conventions

- Node/relationship names in Cypher follow the model defined in `PLAN.md` section 4 — don't invent new labels without updating the plan.
- Ingestion is idempotent: running the script twice should not duplicate nodes (use `MERGE`, not `CREATE`, in Cypher).
- The API never calls external services at request time — all data already lives in Neo4j. If an external data point is ever needed (e.g. a movie poster), that's explicitly Phase 5 and gets discussed before it's added.
- Year/decade filters are always optional on endpoints — the graph must be navigable with no filters applied.

## How to run locally

(To be filled in once `docker-compose.yml` exists — for now the repo only has the plan and folder structure. First real coding step: Phase 1 in PLAN.md, the ingestion script.)

## Status

Just started. Phase 0 (setup) complete. Next step: Phase 1 — download the MovieLens ml-latest + IMDb non-commercial datasets and write the ingestion script in `ingestion/`. Update section 8 of `PLAN.md` as phases progress.
