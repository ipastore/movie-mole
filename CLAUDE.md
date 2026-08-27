# CLAUDE.md

Guide for working in this repo with Claude Code. **Read `PLAN.md` first** — it holds the goal,
architecture, measured figures, and phase breakdown. This file is about how to work in the code
day to day, not what to build.

## What this project is

A graph-based movie explorer (inspired by ResearchRabbit): navigate from one movie to others
connected by similarity, director, cast, or genre, with year/decade filters and a timeline view.
Similarity comes from the MovieLens **tag genome** — a 1,128-dimension vector per movie that
GroupLens derived from 330,975 users' ratings and tags. No external API calls in production.

## Stack

- **Database**: Neo4j **AuraDB Free** (hosted). Not self-hosted, not Docker.
- **API**: **TypeScript on a Cloudflare Worker** — see `api/`. Not FastAPI.
- **Frontend**: Vite + Cytoscape.js on **Cloudflare Pages** — see `frontend/`
- **Ingestion**: Python, run by hand from this machine — see `ingestion/`
- **Deploy**: `wrangler` for the Worker and Pages. **No Docker, no nginx, no VPS.**
- **Routing**: the Worker mounts at `/api/*` on the Pages domain (same-origin, no CORS preflight)

The cronolix VPS is deliberately not used — it holds unrelated apps and their data.

## Structure

```
ingestion/   Python scripts that load Neo4j (run by hand, not on deploy)
api/         Cloudflare Worker, TypeScript — the endpoints the frontend calls
frontend/    Vite + Cytoscape.js SPA
data/        datasets — gitignored except METADATA.md, MANIFEST.md and samples/
docs/        additional technical notes
PLAN.md      goal, architecture, measured figures, phases — read before touching code
```

## Two transports, by runtime

| Where | How | Why |
|---|---|---|
| Ingestion (this Mac) | **Bolt driver**, `neo4j+s://…:7687` | batched parameterised writes, far faster for 348k relationships |
| Worker (production) | **Query API**, `POST https://<db>.databases.neo4j.io/db/<name>/query/v2` | one `fetch()`, no driver or pooling in a short-lived isolate |

Workers *can* open TCP sockets — HTTPS is chosen for simplicity, not forced by the platform.

## Conventions

- **Node and relationship names follow `PLAN.md`.** Don't invent labels without updating the plan.
- **Ingestion is clear-and-reload, not incremental.** `MERGE` alone is not reconciliation — it
  never removes stale edges when K drops or a source refreshes. Uniqueness constraints are global
  and the tier has one database, so there is nowhere to stage: delete, reload, verify, mark ready.
  Reloads are manual and rare, so the downtime is accepted.
- **Create uniqueness constraints before loading**, not after — they are required for `MERGE`
  correctness, not just speed.
- **`SIMILAR_TO` is written low→high `movieId` and queried undirected.** Cosine is symmetric;
  storing both directions wastes 16% of the relationship budget.
- **`DIRECTED` and `ACTED_IN` point Person→Movie.** Movie-centred traversals must be undirected or
  cast and directors silently vanish.
- **Every neighbour query has a `LIMIT` and a `DISTINCT` on the candidate movie.** Average
  `SIMILAR_TO` degree is ~17; a `genre` two-hop from one movie scans up to **25,956 paths yielding
  15,087 distinct candidates** in the worst case (`movieId` 81132, ten genres) — a movie's genres
  are unioned, so the largest single genre is not the bound. Two films can share several actors, so without `DISTINCT` the same movie
  returns repeatedly and eats the limit.
- **Parameterised Cypher only.** Never interpolate user input into a query string. `q` reaches a
  Lucene-interpreting full-text index — escape it and clamp its length.
- **The API never calls external services at request time.** All data is already in Neo4j.
  Posters and synopsis are explicitly Phase 5 and get discussed before being added.
- **Year and connection-type filters are always optional** — the graph must be navigable unfiltered.
- **Verify source checksums** against `data/MANIFEST.md` before ingesting. Both datasets are
  rolling releases; reproducibility only holds against pinned bytes.

## Data

Never commit the datasets — 3.3 GB, gitignored. What *is* committed and should stay current:

- `data/MANIFEST.md` — full SHA-256 for all 12 source files
- `data/METADATA.md` — every measured figure the plan relies on
- `data/samples/` — 100-line samples of each input, so the repo is self-describing

## Licensing

MovieLens and IMDb are both **non-commercial use only**. This project cannot become a
revenue-generating product on this data. Cite Harper & Konstan (2015) for MovieLens.

## How to run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r ingestion/requirements.txt
cp ingestion/.env.example ingestion/.env      # then fill in real values
.venv/bin/python -m pytest ingestion/tests -q # 21 fixture tests, no DB needed
.venv/bin/python -m ingestion.dry_run         # streams 3.3 GB, emits the expected-count manifest
.venv/bin/python -m ingestion.load            # the real load — needs credentials
.venv/bin/python -m ingestion.keepalive       # write-ping so the Free instance never pauses
```

`ingestion/.env` is gitignored and must stay that way — **the repo is public**. `NEO4J_URI` uses
the Aura **database ID**, not the instance display name: `neo4j+s://<dbid>.databases.neo4j.io`.
Copy it from the instance's Connection URI in the console.

Schedule the keepalive daily, well inside the 72h pause window:

```
0 4 * * *  cd /path/to/movie_mole && .venv/bin/python -m ingestion.keepalive >> /tmp/mm-keepalive.log 2>&1
```

## Status

Phase 0 complete. Plan hardened through a two-act grill and Codex adversarial review — see
`PLAN-REVIEW-LOG.md`.

**Phase 1 complete and live.** The graph is loaded into AuraDB Free instance `a2a3cb81`:
87,544 nodes / 348,080 relationships, `Meta.ready = true`. Both blocking preconditions passed —
capacity is 200k/400k (44% / 87% used) and the `movieSearch` index is `ONLINE` at 100%.
Spanish search verified: "El Padrino" returns The Godfather.

**Next: Phase 2** — the Cloudflare Worker, with the daily keep-alive Cron Trigger folded in.
