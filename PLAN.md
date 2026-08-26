# Grafo-Pelis — Project Plan

An interactive movie explorer in the spirit of ResearchRabbit: start from a movie (or director), navigate a graph of connections (director, cast, genre), filter by year/decade, and see it all on a timeline. Runs entirely on your own VPS, with no external API dependency in production.

## 1. MVP goal

A navigable graph where:
- You pick a seed movie (search by title).
- The node expands to show connected movies sharing a director, a cast member, or a genre.
- You can filter the visible graph by year range / decade.
- There's a timeline view (temporal axis) in addition to the free graph view.
- Clicking a node shows a side panel with details (title, year, director, main cast, genre, synopsis if available).

Out of scope for the MVP (phase 2): login/users, saved collections, export, multiple linked panels, posters/images.

## 2. Why Neo4j

The queries we need ("movies 2 hops from this one via director or cast, filtered by decade") are native graph queries — short and fast in Cypher, whereas relational SQL would need several recursive JOINs or messy CTEs. Neo4j Community Edition is free and runs comfortably on a small VPS via Docker.

## 3. Where the data comes from (without depending on an API in production)

Any external API (TMDB or otherwise) is used **once, in development, for the initial load** — never in production. Candidate sources, combinable:

- **MovieLens (full dataset, ml-latest)**: free, one-time download. Contains real user ratings for ~86,000 movies, with a `links.csv` file mapping each movie to its IMDb and TMDB IDs. The ratings let us compute movie-to-movie similarity from real taste overlap (collaborative filtering), not just shared metadata — this is what gives the graph a "recommendation" feel rather than pure taxonomy.
- **IMDb non-commercial datasets** (`title.basics`, `title.crew`, `title.principals`, `name.basics`): free, direct download, provide director, main cast, year, genre, with no API calls needed.
- **Wikidata (SPARQL)**: optional, to fill in synopsis/metadata gaps, via a one-time batch query.

Ingestion pipeline: runs **once** (or occasionally by hand, when refreshing the dataset) — it is not part of the request/response cycle in production.

## 4. Neo4j data model

Nodes:
- `(:Movie {id, title, year, genres: [...], synopsis?})`
- `(:Person {id, name})` — reused for both directors and actors, with the relationship indicating the role
- `(:Genre {name})`

Relationships:
- `(:Person)-[:DIRECTED]->(:Movie)`
- `(:Person)-[:ACTED_IN]->(:Movie)`
- `(:Movie)-[:HAS_GENRE]->(:Genre)`
- `(:Movie)-[:SIMILAR_TO {score}]->(:Movie)` — precomputed during ingestion from MovieLens ratings (co-occurrence of high ratings by the same user) and/or shared genre+decade. This relationship is what makes expanding a node feel like "recommendation" rather than just "shares a director."

Indexes: full-text index on `Movie.title` for the search box, index on `Movie.year` for decade filters.

## 5. Architecture

```
VPS (Docker Compose)
├── neo4j          → graph database, internal ports 7687 (bolt) + 7474 (browser, localhost only)
├── api             → FastAPI (Python) or Express (Node), translates frontend filters into Cypher, exposes REST
├── frontend        → static SPA (Vite + Cytoscape.js or Sigma.js), served by nginx
└── nginx           → reverse proxy: your domain → static frontend + /api → api container
```

Graph library choice: **Cytoscape.js** (simplest for dynamically expanding/collapsing nodes with filters, good documentation) over Sigma.js (better for huge static graphs, not our case) or raw D3 (more maintenance work).

## 6. Phases

**Phase 0 — Repo setup** (this moment): PLAN.md, CLAUDE.md, folder structure.

**Phase 1 — Data**: download MovieLens ml-latest + IMDb non-commercial datasets, write an ingestion script in `ingestion/` that processes them and loads them into Neo4j via the `neo4j` Python driver or `LOAD CSV`. Compute `SIMILAR_TO` via simple collaborative filtering (co-rating).

**Phase 2 — API**: minimal endpoints —
- `GET /search?q=` → search movies by title
- `GET /movie/{id}` → detail + direct neighbors (director, cast, similar), with optional `year_min`/`year_max` filter
- `GET /movie/{id}/expand?depth=2&year_min=&year_max=` → subgraph for expanding a node

**Phase 3 — Frontend**: initial search box, graph rendering with Cytoscape.js, filter panel (year range slider, checkboxes for connection type: director/cast/genre/similar), side detail panel on click, alternate timeline view (X axis = year).

**Phase 4 — Deploy**: Docker Compose on the VPS, nginx + TLS certificate (Let's Encrypt) for your domain.

**Phase 5 (post-MVP)**: saved collections, posters (maybe, at that point, a one-off call to an image source), multiple linked panels.

## 7. Open questions / pending decisions

- Final domain/subdomain to use.
- API in Python (FastAPI, a natural fit for the ingestion/data-science work) or Node (if you'd rather keep one language across frontend and backend)? Defaulting to FastAPI.
- VPS size? Full MovieLens + Neo4j runs fine with 2GB RAM, but confirm specs before Phase 4.

## 8. Current status

Phase 0 in progress. See `CLAUDE.md` for repo conventions before writing code.
