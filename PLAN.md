# Plan: movie-mole — graph-based movie explorer

_Act 1 (grill) complete — every decision was locked with the user and every figure measured from
the real data files. Revised after Codex adversarial review round 1 (20 of 21 findings accepted)._
_Pre-grill plan is in git history at commit `b4a0650`; the full critique is in `PLAN-REVIEW-LOG.md`._

## Goal

An interactive movie explorer in the spirit of ResearchRabbit: start from a movie, expand outward
through connections — taste-based similarity, director, cast, genre — filter by year or decade,
and view the result as a free graph or on a timeline. Fully serverless and free to run: no VPS,
no containers in production, no external API calls at request time.

## Data provenance — pinned

| Source | Release | Pinned by |
|---|---|---|
| MovieLens `ml-latest` | generated 2023-07-20 (stated in its README) | full SHA-256 in `data/MANIFEST.md` (committed) |
| IMDb non-commercial | downloaded 2026-08-26 | full SHA-256 in `data/MANIFEST.md` (committed) |

IMDb republishes daily and MovieLens `ml-latest` is explicitly a rolling *development* dataset, so
"reproducible" is only true against pinned bytes. `data/MANIFEST.md` holds **full SHA-256 hashes
for all 12 source files** and is committed. Ingestion **verifies every hash** before running and
aborts on mismatch. A refresh is a
deliberate act: re-download, update the manifest, rebuild a new generation.

## Approach

### Phase 1 — Ingestion (Python, runs locally, one-time)

**0. Preflight.** Verify source checksums. Create uniqueness constraints (below) *before* any
write — required for `MERGE` correctness under concurrency, not merely for speed. Then probe the
live instance's actual capacity and abort if the planned graph will not fit.

1. **Movie set.** Parse `movies.csv` (86,537 rows), keep the **16,376 movies covered by the tag
   genome**, join `links.csv` for `imdbId` / `tmdbId`. **No `titleType` filter is applied.**
   Genome membership is the curation — GroupLens included these because MovieLens users rated
   them as films. Measured composition: `movie` 15,298, `tvMovie` 264, `short` 232, `video` 227,
   `tvSpecial` 120, `tvMiniSeries` 105, `tvEpisode` 48, `tvSeries` 23, `tvShort` 20, absent from
   `title.basics` 39. Filtering to {`movie`,`tvMovie`} would discard **814 titles (4.97%)**
   including shorts and direct-to-video films that belong here; the genuinely non-film entries
   (`tvEpisode`/`tvSeries`/`tvShort`) are 0.6% and are accepted as noise. **All counts in this
   plan are over the full 16,376.**

2. **Year and title.** Year = the **last** `(\d{4})` in the title (99.72%; backfill 46 from
   `title.basics.startYear`). A movie with no year gets `year = null` and is excluded from
   year-filtered results rather than defaulted.

   **Article normalisation** — strict allowlist of `The`, `A`, `An` only, applied to the main
   title segment after the year is stripped, preserving any parenthetical. Measured: 2,281 genome
   titles end in a comma-plus-word outside parentheses, of which **45 are non-English** (`La` 11,
   `Les` 7, `Le` 6, `El` 4, `L'` 3, `Il`/`Der`/`Das` 2 each) — so the earlier assumption that
   non-English articles live only inside parentheses was wrong. Worse, some trailing words are
   not articles at all: `Die, Mommie, Die`, `Play It Again, Sam`, `Bye Bye, Love`. A naive rule
   produces `"Die Die, Mommie"`. **Fixture tests are mandatory**, covering those three plus one
   of each non-English article.

3. **Search aliases.** From `title.akas`, keep rows where `language=es` **or** `region` is in the
   explicit allowlist `{ES, MX, AR, CO, CL, PE, VE, UY}` — this exact set produced the figures
   below and must be used verbatim for them to reproduce. Store as `searchAliases[]`. Measured 91.9% coverage (15,054/16,376),
   35,520 strings. These add **no nodes or relationships**, but they are **not free**: they consume
   storage and full-text index memory on a tier with limited RAM. Included in the preflight budget.

4. **Genres.** 20 raw values, **19 after discarding `(no genres listed)`**.

5. **People.** Stream `title.crew` (directors) and `title.principals` (`category` in
   `actor`/`actress`), testing each row against the 16,376 tconsts in
   `data/derived/genome_imdb_tconsts.txt` **while streaming**. Keep **all** cast — IMDb self-caps
   at ~10 principals per title, so a top-N cutoff saves 3% of edges for no benefit. Resolve
   `nconst` → name via `name.basics`. **`MERGE` `Person` on `nconst` once** and attach both
   relationship types — 1,045 people both act and direct.

6. **Similarity.** Build the dense `16,376 × 1,128` genome matrix (**73.9 MB** float32) and
   L2-normalise rows so the dot product equals cosine.

   **Compute top-K in row blocks of ~1024.** The full similarity matrix would be
   `16,376² × 4 = 1.07 GB`; it is never materialised. Required within each block: set the diagonal
   to `-inf` so a movie cannot be its own neighbour; **assert all norms are non-zero** before
   dividing, or a zero vector yields NaN and silently poisons its row; break score ties by
   ascending `movieId` so runs are deterministic.

   **Store each unordered pair exactly once, always written low→high `movieId`.** Cosine is
   symmetric and Cypher traverses `-[:SIMILAR_TO]-` either way, so storing both directions costs
   16% of the relationship budget for nothing. Measured at K=10: 163,760 directed → **137,568
   deduped**. Runs in ~17s (13s load, 4s cosine); **peak RSS to be recorded**.

7. **Load** with the **Python driver over Bolt** (`neo4j+s://`, port 7687) — batched parameterised
   writes, far faster than HTTP for 348k relationships.

8. **Clear-and-reload, with accepted downtime.** `MERGE` alone is *not* reconciliation: lowering
   K, dropping a cast member, or refreshing IMDb leaves stale relationships and properties behind
   forever. But a side-by-side "new generation" is **impossible here**: the uniqueness constraints
   are global, so two generations cannot hold the same `movieId`, and keeping both would peak near
   175k nodes / 696k relationships — far past the cap. AuraDB Free provides a single database, so
   there is nowhere to stage.

   Therefore: **delete only this project's own data, reload, verify, then mark ready.**

   **A dedicated database is a hard prerequisite, not an inference.** Checking that no label
   outside {`Movie`,`Person`,`Genre`,`Meta`} exists is *not* sufficient — unlabelled nodes are
   invisible to it, and another application using the same three label names would pass the check
   while having its relationships detached. The instance must be dedicated to movie-mole by
   construction, asserted by: total node count equals the sum of the four owned labels (proving no
   unlabelled nodes), and total relationship count equals the sum of the four owned types. Abort
   on any mismatch.

   Deletion is then `DETACH DELETE` over the owned labels in batches. A blanket
   `MATCH (n) DETACH DELETE n` is forbidden.

   **Readiness lives in a `(:Meta {key:'readiness'})` node** — inside the ownership allowlist so it
   does not trip the assertion, but **explicitly excluded from deletion**. It holds `ready`
   (boolean), the source-manifest hash it was built from, and a timestamp. The sequence is: set
   `ready = false` → delete → reload → verify → set `ready = true`. The API **fails closed**:
   absent or `false` readiness returns **503**, so a request arriving mid-reload gets an honest
   error rather than an empty graph presented as a real result. The graph is unavailable for the duration
   of a reload; this is accepted, since reloads are manual and rare. The alternative — a second
   Free instance and a secret swap — is noted but not planned.
   This supersedes the bare "use `MERGE`, not `CREATE`" convention in `CLAUDE.md`, which is
   necessary but not sufficient.

9. **Verify against a dry-run manifest, then flip readiness.** Load order: Movies → Genres +
   `HAS_GENRE` → Persons + `DIRECTED`/`ACTED_IN` → `SIMILAR_TO` last, since K is the only value
   that can shrink.

   **Expected counts are computed, not hardcoded.** The table below describes the 2026-08-26
   snapshot; refreshes are explicitly supported, so those figures go stale by design. Ingestion
   therefore runs a **dry pass over the sources first**, emitting a manifest of expected per-label
   and per-type counts stamped with the source-manifest hash, and verifies the load against *that*
   — never against numbers written into this document. The dry pass runs **before any deletion**,
   so a source problem is caught while the existing graph is still intact.

   Readiness is gated on **all** of:

   - per-label node counts (**`Meta` included**) and per-type relationship counts matching the
     dry-run manifest
   - zero unresolved joins (no `Person` without a name, no relationship to a missing `Movie`)
   - zero duplicate `SIMILAR_TO` pairs — enforced by the low→high write rule and verified with a
     **directed** match:
     `MATCH (a)-[:SIMILAR_TO]->(b) WHERE a.movieId > b.movieId RETURN count(*)` must be 0.
     The arrow is essential: an undirected `-[:SIMILAR_TO]-` match returns **both** orientations
     of every edge, so half the rows always satisfy `a.movieId > b.movieId` and the check can
     never pass. (Caught in review round 3 — the original form was guaranteed to fail.)
   - `SHOW FULLTEXT INDEXES` reporting state `ONLINE` — a populating index silently returns
     partial search results

**Constraints created before loading:**

```cypher
CREATE CONSTRAINT movie_id  IF NOT EXISTS FOR (m:Movie)  REQUIRE m.movieId IS UNIQUE;
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.nconst  IS UNIQUE;
CREATE CONSTRAINT genre_nm  IF NOT EXISTS FOR (g:Genre)  REQUIRE g.name    IS UNIQUE;
CREATE CONSTRAINT meta_key  IF NOT EXISTS FOR (x:Meta)   REQUIRE x.key     IS UNIQUE;
```

**Full-text index, named explicitly** so the Worker addresses the intended index rather than
whatever `db.index.fulltext.queryNodes` happens to resolve:

```cypher
CREATE FULLTEXT INDEX movieSearch IF NOT EXISTS
FOR (m:Movie) ON EACH [m.title, m.searchAliases];
```

**Measured size at K=10** for the 2026-08-26 snapshot (every figure counted from the real files,
none estimated). **Illustrative, not authoritative** — verification uses the dry-run manifest:

| Nodes | | Relationships | |
|---|---|---|---|
| `Movie` | 16,376 | `ACTED_IN` | 156,759 |
| `Person` | 71,148 | `SIMILAR_TO` | 137,568 |
| `Genre` | 19 | `HAS_GENRE` | 35,217 |
| `Meta` | 1 | `DIRECTED` | 18,536 |
| **total** | **87,544** | **total** | **348,080** |

`Meta` is one node carrying the readiness flag. It is **counted** here because the ownership
assertion compares total node count against the sum of owned labels — omitting it would make that
check fail by exactly one on every run.

Coverage: 99.72% have a director, **95.26% have cast** (776 have none — the UI must tolerate an
empty cast list).

**Average `SIMILAR_TO` degree is ~17, not 10** (`137,568 × 2 ÷ 16,376`): a movie carries its own
top-10 plus every movie that selected it. **Every neighbour query must `LIMIT`.**

### Phase 2 — API (TypeScript, Cloudflare Worker)

**All routes are served under `/api`** — the public contract is `/api/search`,
`/api/movie/{movieId}` and `/api/movie/{movieId}/expand`. The Worker is mounted at `/api/*` on the
Pages domain and **strips the `/api` prefix internally**, so handler paths stay `/search` and
`/movie/...` as tabled below. One place to change if the mount point ever moves.

**`{movieId}` is the MovieLens id**, declared in the route. `imdbId` and `tmdbId` are returned as
properties but are never route parameters — three id namespaces in one path is a bug waiting to
happen.

| Endpoint | Contract |
|---|---|
| `GET /search?q=&limit=` | full-text over `title` + `searchAliases`. `q` **Lucene-escaped**, length-clamped; `limit` clamped (default 20, max 50) |
| `GET /movie/{movieId}` | detail only — properties plus **counts** per relationship type. Never an unbounded neighbour list |
| `GET /movie/{movieId}/expand?type=&n=&year_min=&year_max=` | `type` from the allowlist {`similar`,`cast`,`director`,`genre`}. **Always returns `Movie` nodes.** `n` clamped (default 8, max 25) |

**Every `expand` type returns movies, not people or genres.** "Films sharing an actor" is a
**two-hop** traversal; only `similar` is one hop. This matters because `Person` and `Genre` nodes
carry neither `year` nor `imdbVotes`, so year filters and vote ordering are meaningless against
them:

| `type` | Pattern | Ordering |
|---|---|---|
| `similar` | `(m)-[:SIMILAR_TO]-(o)` | `score DESC` |
| `cast` | `(m)<-[:ACTED_IN]-(:Person)-[:ACTED_IN]->(o)` | shared-actor count DESC, then `imdbVotes` |
| `director` | `(m)<-[:DIRECTED]-(:Person)-[:DIRECTED]->(o)` | `imdbVotes` DESC |
| `genre` | `(m)-[:HAS_GENRE]->(:Genre)<-[:HAS_GENRE]-(o)` | shared-genre count DESC, then `imdbVotes` |

**On `genre` fanout.** Measured over the loaded 16,376: Drama holds 7,670 films, Comedy 5,524,
Thriller 3,181, down to Film-Noir 149. But a movie carries **several** genres and the expansion
scans the union, so the largest single genre is not the bound. Measured across all 16,376:

| Per one expansion request | mean | median | **max** |
|---|---|---|---|
| paths scanned before `DISTINCT` | 7,970 | 7,670 | **25,956** |
| distinct candidate movies | 6,919 | 7,669 | **15,087** |

Worst case is `movieId` 81132, which carries ten genres. **25,956 paths, not 7,669** — bounded and
still unremarkable for Neo4j, but 3.4× the figure a single-genre estimate suggests.

An earlier revision of this plan removed `genre` entirely, citing 58,821,230 "candidate pairs".
That figure is `7,670 × 7,669` — every Drama pair in the graph, not the candidates for one
request. It described a query nobody would ever run. `genre` is restored; the real constraint is
simply that it is the **weakest signal** and should rank below `similar` in the UI.

**Worst-case per-movie latency must still be benchmarked** against the live instance before Phase 3
depends on it — bounded is not the same as fast on limited vCPU.

**Required in every expansion query**, not optional:

- `o <> m` — a movie must never be its own neighbour
- **`DISTINCT o` — deduplicate candidate *movies* before ordering and limiting, for every type.**
  Two films can share three actors, or a co-directed film can be reached through each director;
  without this the same movie is returned repeatedly and consumes the `LIMIT`.
- `count(DISTINCT p)` for the shared-person and shared-genre ordering counts
- a deterministic final tiebreaker on `o.movieId`, so equal scores do not reorder between calls

`year_min`/`year_max` apply to `o.year` in every case.

**Traversal is undirected for person edges.** `DIRECTED` and `ACTED_IN` point Person→Movie, so a
movie-outgoing pattern silently returns nothing. Queries use `-[:ACTED_IN]-` and return the
relationship type and direction explicitly.

**Security, non-negotiable:**

- **Fixed parameterised Cypher only.** No string interpolation into queries, ever.
- **`q` is Lucene, not plain text** — the full-text index interprets operators and field scoping.
  Escape it, clamp its length, clamp result count.
- Validate `id`, `n` and year bounds; reject inverted ranges rather than returning empty.
- Upstream timeout on the Aura call; map failures to bounded 4xx/5xx with **sanitised** messages —
  never surface a database error to the client.
- The Aura credential is a **Worker secret**, never in the repo or in client-reachable code.
  **Residual risk, accepted and stated plainly:** AuraDB Free offers no separate read-only user —
  role-based access control is a paid-tier feature — so the Worker necessarily holds a
  **write-capable credential** for a database it only ever reads. Mitigations are the
  parameterised-Cypher rule and the fixed statement set above; the exposure is real and is the
  price of the free tier. Moving to a tier with RBAC is the fix if this ever matters.
- **Rate limiting and caching are required, not optional.** The API is public and backed by a free
  tier with limited vCPU; an unthrottled scraper can exhaust both the Worker budget and the
  database. Cache `search` and `expand` responses at the edge with a bounded TTL, and apply a
  per-IP request budget.
- **The cache must not outlive readiness.** A cached response served during a reload would bypass
  the `Meta.ready = false` check entirely and hand the client stale data from the previous
  generation while the graph is half-deleted. Cache keys therefore **include the readiness
  generation stamp** (`sourceManifestHash` + `builtAt`), so a new load implicitly invalidates every
  prior entry and no purge step can be forgotten.

**Connection.** Query API over HTTPS:
`POST https://<databaseID>.databases.neo4j.io/db/<database>/query/v2` with an authorization
header. Database name and full path are pinned, not just the host.

HTTPS is chosen for **simplicity** — one `fetch()`, no driver, no connection pooling in a
short-lived isolate. It is *not* chosen because Workers cannot do TCP: they now expose outbound
TCP sockets, and this plan's earlier claim to the contrary was wrong.

**Browser-to-API origin contract.** Pages and the Worker are separate deployments on different
origins, so without an explicit decision the browser simply cannot call the API. **Chosen:
same-origin routing** — the Worker is mounted under the Pages domain at `/api/*` via a Worker
route, so the SPA calls same-origin relative paths and no CORS preflight ever occurs. This is
preferred over CORS headers because there is nothing to misconfigure and no `OPTIONS` round-trip
on every request. If routing proves impossible, the fallback is an explicit
`Access-Control-Allow-Origin` naming **only** the Pages origin — never `*`, which would let any
site drive the API against a free-tier budget — plus an `OPTIONS` handler.

### Phase 3 — Frontend (Vite + Cytoscape.js, Cloudflare Pages)

Search box, graph canvas, filter panel (year range, connection-type toggles mapping to `expand`'s
`type` allowlist), detail side panel, timeline view with year on the X axis.

Required behaviours: render a movie with **no cast** (776 have none); show an honest error state
when the database is **paused or not ready** rather than an empty graph; and place movies with
`year = null` in an explicit **"Unknown year"** bucket at the end of the timeline rather than
dropping them silently or coercing them to 0.

### Phase 4 — Keep-alive

Cloudflare Cron Trigger, **daily**, with retry and alert on failure. A 48-hour interval against a
72-hour pause window leaves no margin for one missed run, and **a paused instance cannot be woken
by a query** — the hostname does not serve. No client-side handling can recover from this; it
requires an operator resume or a paid tier.

## Data model

**Nodes**

| Label | Count | Properties |
|---|---|---|
| `Movie` | 16,376 | `movieId`, `title`, `year`, `imdbId`, `tmdbId`, `imdbRating`, `imdbVotes`, `searchAliases[]` |
| `Person` | 71,148 | `nconst`, `name` |
| `Genre` | 19 | `name` |
| `Meta` | 1 | `key`, `ready`, `sourceManifestHash`, `builtAt` |

**Relationships**

| Type | Direction | Source |
|---|---|---|
| `(:Person)-[:DIRECTED]->(:Movie)` | Person→Movie | IMDb `title.crew` |
| `(:Person)-[:ACTED_IN]->(:Movie)` | Person→Movie | IMDb `title.principals` |
| `(:Movie)-[:HAS_GENRE]->(:Genre)` | Movie→Genre | MovieLens `movies.csv` |
| `(:Movie)-[:SIMILAR_TO {score}]->(:Movie)` | written low→high `movieId`, **queried undirected** | genome cosine |

**Null policy.** IMDb `\N` normalises to a typed null, never the literal string. 15 movies lack
`tmdbId`; movies lacking a year get `year = null` and drop out of year-filtered results.

**Indexes.** Full-text over `Movie.title` **and** `Movie.searchAliases`; range index on `Movie.year`.

## Key decisions & tradeoffs

**Neo4j AuraDB Free, not self-hosted.** The VPS holds unrelated apps and their data; exposing a
public service beside them widens the blast radius for no benefit. Accepted costs: a capacity cap,
no backups, 72h auto-pause, deletion after 30 days paused.

**The graph is fully reproducible from pinned sources, so the lack of backups is tolerable.** A hard
constraint: nothing may be stored in Neo4j that cannot be regenerated by re-running ingestion
against the checksummed snapshot.

**Cloudflare Worker in TypeScript, replacing FastAPI.** The API is three endpoints translating
params into Cypher; little is lost by leaving Python, and Python stays where it earns its keep —
ingestion, the genome matrix, numpy cosine.

**Similarity from the tag genome, not co-rating.** GroupLens already derived a 1,128-dimension
vector per movie from 330,975 users' ratings and tags. Using it replaces a multi-hour item-item
computation over 33.8M ratings with a blocked matrix multiply over 74 MB.

**The genome set defines the movie set.** Its 16,376 movies align with the 16,116 having ≥50
ratings — GroupLens already made the "enough data" cut. All 86,537 would leave 70,161 movies with
no usable similarity and two visibly different classes of node.

**IMDb ratings, stored as `imdbRating` / `imdbVotes`.** `title.ratings.tsv.gz` is 8.2 MB against
`ratings.csv`'s 934 MB. They are **not the same signal** — IMDb voters and MovieLens users are
different populations with different biases — so the properties are named for their source and
must never be described as MovieLens ratings. **`ratings.csv` is not used at all.**

## Risks / open questions

- **[CLOSED]** Cast depth — all `actor`/`actress` rows.
- **[CLOSED]** K = 10, symmetric pairs stored once → 348,080 relationships.
- **[CLOSED]** Expansion — top-N with a `type` allowlist. **`similar` is one hop; `cast`,
  `director` and `genre` are two-hop and return `Movie` nodes**, never `Person` or `Genre`.
- **[CLOSED]** Article normalisation on ingest, English allowlist, fixture-tested.
- **[CLOSED]** Spanish search in the MVP.
- **[MEASURED]** IMDb coverage — 16,330/16,376 directors, 15,600/16,376 cast.
- **[BLOCKING PRECONDITION] The 200k/400k capacity profile is required, not assumed.**
  The Create Instance screen states **200k nodes / 400k relationships**; other Neo4j pages state
  **50k / 175k**. This plan is sized against the former: 87,544 nodes (44%), 348,080
  relationships (87%).

  Under 50k/175k the design **fails on nodes, and K cannot help** — K only moves `SIMILAR_TO`,
  while 71,148 of the 87,544 nodes are `Person`. Even K=0 is 75% over a 50k cap.

  **The first ingestion into a fresh, empty instance IS the probe — there is no separate
  saturation test.** Deliberately filling the live database with throwaway data until writes fail
  is rejected: an OOM, a storage failure, or an interrupted cleanup can leave the instance
  unusable, and it destroys the very thing being measured.

  Instead:

  1. Provision a **fresh, empty, dedicated** instance. Nothing of value exists on it yet, so a
     failed load costs nothing.
  2. Load in the documented order — Movies → Genres → Persons → `SIMILAR_TO` — recording counts
     between stages. If a write is refused, the exact cap is now known and nothing was lost.
  3. **Full load succeeds → capacity confirmed; proceed.**
  4. **A write is refused → STOP and re-plan. Do not degrade silently.**

  **The destructive clear-and-reload path is only ever used after a first load has already proven
  capacity on that instance.** Reload never runs against an unproven instance.

  A reduced product is *viable* — dropping `Person` and setting K=8 gives 16,395 nodes / 145,643
  relationships (33% / 83% of 50k/175k) — but it is **a different product**: no cast or director
  navigation, so the Goal, the `expand` type allowlist, the UI toggles, the expected-count table
  and the verification invariants would all need rewriting. Specifying it here in a paragraph
  while the rest of the document promises cast navigation would leave the plan self-contradictory,
  which is exactly the failure mode this review keeps catching. If the probe returns the low cap,
  that reduced product gets its own planning pass.

- **[RISK] 72h auto-pause is not recoverable by traffic.** A paused instance does not serve, so no
  client-side handling can wake it. Daily cron with alerting reduces the odds; it does not
  eliminate them.
- **[BLOCKING] Storage and index headroom are unproven, and entity counts do not prove them.**
  87,544 nodes and 348,080 relationships fit the *counters*, but `searchAliases` (35,520 strings)
  and its full-text index consume store bytes and RAM on a tier explicitly labelled "limited
  memory and vCPU". A graph that fits by count can still fail to fit on disk or fail to build its
  index. **Required before any destructive reload:** measured store growth per stage and confirmed
  `ONLINE` full-text index on the first (non-destructive) load, with a stated safety margin.
- **[OPEN] Peak RSS of the similarity step** is unrecorded. Blocked 1024-row computation should
  keep it near the 74 MB matrix plus one block (~140 MB), but that is asserted, not measured. This
  is local-only and does not affect the database; record it during the first real run.

## Licensing

Both sources are **non-commercial only**:

- **MovieLens** — "may not be used for any commercial or revenue-bearing purposes without first
  obtaining permission from a faculty member of the GroupLens Research Project." Requires citing
  Harper & Konstan (2015), *The MovieLens Datasets: History and Context*.
- **IMDb** — "The data files available on this page are provided for non-commercial use only."
  Used: `title.basics`, `title.crew`, `title.principals`, `title.ratings`, `title.akas`,
  `name.basics`.

This project cannot become a revenue-generating product on this data.

## Out of scope

Login and user accounts, saved collections, export, multiple linked panels, posters and synopsis
(Phase 5, via one-time dev-time TMDB API calls — `tmdbId` is retained for that join), and any use
of the cronolix VPS.
