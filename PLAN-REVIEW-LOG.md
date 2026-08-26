# Plan Review Log: movie-mole

Act 1 (grill) complete — plan locked with the user. MAX_ROUNDS=5, **extended by the user after
round 5** with instruction to continue until Codex returns `VERDICT: APPROVED`.

Decisions locked in Act 1, each backed by a measurement against the real data.

> **HISTORICAL — this table is a snapshot of Act 1 and is deliberately not updated.** Several
> entries were overturned by the Codex rounds below: the Aura cap is disputed, the Workers-TCP
> justification was false, `searchAliases` are not cost-free, and IMDb ratings are not the same
> signal as MovieLens ratings. `PLAN.md` is the current authority.

| Decision | Value | Evidence |
|---|---|---|
| Movie set | 16,376 genome-covered | `18,472,128 / 1,128 = 16,376` exactly |
| Similarity | genome cosine, K=10, symmetric pairs stored once | 163,760 → 137,568 deduped (16% saved) |
| Cast | all `actor`/`actress` | IMDb self-caps at ~10/title; "all" costs 3% over top-10 |
| Graph size | 87,543 nodes / 348,080 rels | 44% / 87% of the confirmed Aura Free cap |
| DB | AuraDB Free | cap 200k/400k confirmed on the Create Instance screen |
| Transports | Bolt for ingestion, HTTPS Query API for the Worker | Workers cannot open raw TCP |
| Expansion | top-N one hop, N≈8 | avg SIMILAR_TO degree is ~17, so depth-2 reaches ~290 nodes |
| Search | English + Spanish aliases | 91.9% Spanish coverage, zero cap cost (properties) |
| Not used | `ratings.csv` (934 MB) | `title.ratings.tsv.gz` gives the same signal in 8.2 MB |


## Round 1 — Codex (gpt-5.6-luna, effort=max)

`VERDICT: REVISE` — 21 findings. Usage: 1,022,146 in / 35,877 out (32,173 reasoning).

Material problems found; no files were modified.

- Aura capacity is not settled: Neo4j’s public pages currently disagree between 50k/175k and 200k/400k limits; the graph exceeds the smaller cap. Fix: pin the actual tier limits and preflight node, relationship, storage, and index usage before writing. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:67), [Neo4j FAQ](https://neo4j.com/free-graph-database/), [Aura Free page](https://neo4j.com/videos/getting-started-with-aura-free-tier/))
- `searchAliases` and its full-text index are not cost-free; they consume storage and memory even if excluded from entity counters. Fix: include property/index size in the capacity check. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:30))
- Measurement provenance is incomplete: `METADATA.md` promises commands for every figure, but coverage, relationship counts, deduplication, timing, hardware, and peak RSS are undocumented. Fix: add a reproducible manifest script with pinned inputs and per-stage outputs. ([METADATA.md](/Users/ignaciopastorebenaim/movie_mole/data/METADATA.md:6))
- The genre table is labeled “genome subset” but explicitly counts all 86,537 movies, so it cannot validate the planned 35,217 genre edges. Fix: relabel it or recompute it for the subset. ([METADATA.md](/Users/ignaciopastorebenaim/movie_mole/data/METADATA.md:110))
- “100% reproducible” is false while IMDb is recorded only as `current`; a later download can change aliases, ratings, people, and counts. Fix: pin release dates/checksums and retain a source manifest. ([METADATA.md](/Users/ignaciopastorebenaim/movie_mole/data/METADATA.md:13))
- `MERGE` is not exact reconciliation: lowering K, removing cast, or changing scores leaves stale relationships/properties, and staged failures can expose partial data. Fix: rebuild into a clean generation and flip a readiness marker only after verification. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:47))
- No uniqueness constraints are planned; overlapping batches can race and create duplicate `Movie`, `Person`, or `Genre` nodes. Fix: create uniqueness constraints before loading and serialize/retry writes. ([CLAUDE.md](/Users/ignaciopastorebenaim/movie_mole/CLAUDE.md:31))
- “Store each unordered pair once” lacks a canonical write rule. Fix: sort movie IDs, always write lower→higher, and query the relationship undirected. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:42))
- `DIRECTED` and `ACTED_IN` point Person→Movie, so movie-outgoing traversal misses cast and directors. Fix: require undirected movie-neighbor queries and return relationship type/direction explicitly. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:112))
- `/movie/{id}` returns direct neighbours without a limit despite popular movies having unusually high similarity degree. Fix: make it detail-only or cap/paginate neighbours per relationship type. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:80))
- The goal promises expansion through cast, directors, and genres, but `expand?n` only defines highest-scoring neighbours, which applies only to similarity; connection toggles have no API contract. Fix: add an allowlisted type parameter with per-type limits/order, or narrow the MVP promise. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:79))
- Raw `q` is a Lucene query language, not plain text; operators and property scoping are accepted, but escaping, length limits, and result limits are unspecified. Fix: Lucene-escape user input, clamp length/results, and rate-limit/cache searches. ([Neo4j full-text docs](https://www.neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/))
- The API does not specify parameterized Cypher, ID/type allowlists, invalid-range handling, upstream timeouts, or sanitized errors. Fix: use fixed parameterized statements, validate `id`, `n`, and year bounds, and map database failures to bounded 4xx/5xx responses.
- The Query API section gives only the host; the actual endpoint is `/db/<databaseName>/query/v2` and requires authorization. Fix: pin the database name, URL path, and Worker-only database secret. ([Query API docs](https://neo4j.com/docs/query-api/current/query/))
- The claim that Workers cannot open raw TCP is outdated; Workers now expose outbound TCP sockets. Fix: retain HTTPS as a deliberate simplicity choice and remove the false platform constraint. ([Cloudflare TCP sockets](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/))
- A 48-hour keep-alive has little margin for one missed run, and a paused Aura hostname cannot serve a query; a loading state alone cannot resume it. Fix: run daily with retries/alerts and document operator resume or use a tier without this availability constraint. ([Aura instance actions](https://neo4j.com/docs/aura/managing-instances/instance-actions/))
- A full 16,376×16,376 float32 cosine matrix is about 1.07 GB, not 74 MB; the timing omits peak memory. Fix: specify blocked top-K computation and measure peak RSS. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:137))
- Top-K selection does not state self-exclusion, zero-vector handling, or deterministic tie-breaking. Fix: assert nonzero norms, set the diagonal to negative infinity, and break ties by movie ID.
- The plan has no null policy for the 15 missing TMDB IDs, remaining missing years, or IMDb `\N` values, and no explicit `titleType` allowlist. Fix: normalize sentinels to typed nulls, define unknown-year behavior, and reject or label non-film title types. ([METADATA.md](/Users/ignaciopastorebenaim/movie_mole/data/METADATA.md:72))
- Article normalization is underspecified: the supplied sample has `City of Lost Children, The` before nested foreign-title parentheses and `Misérables, Les` outside parentheses. Fix: parse the final year, normalize only the main-title segment, preserve parentheticals, and add fixture tests. ([movies.head.csv](/Users/ignaciopastorebenaim/movie_mole/data/samples/movies.head.csv:30))
- IMDb ratings are not “the same signal” as MovieLens ratings; they represent different populations. Fix: name them `imdbRating`/`imdbVotes` and document their semantics. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:147))

VERDICT: REVISE
### Claude's response

**Accepted: 20 of 21.** The review was substantially correct, including on several points I had
asserted confidently and wrongly.

Two findings verified against the data before accepting:

- **Article normalisation (#20).** Confirmed. 2,281 genome titles carry a trailing article
  *outside* parentheses; 45 are non-English (`La` 11, `Les` 7, `Le` 6, `El` 4, `L'` 3, `Il`/`Der`/
  `Das` 2 each), directly contradicting my claim that non-English articles only appear inside
  foreign-title parentheses. The scan also surfaced a trap Codex did not name: `Die, Mommie, Die
  (2003)`, `Play It Again, Sam (1972)` and `Bye Bye, Love (1995)` end in a comma-plus-word that is
  *not* an article. A naive rule yields `"Die Die, Mommie"`. Fixtures are mandatory.
- **IMDb pinning (#5).** Accepted. Checksums and download date now recorded in
  `data/derived/imdb_manifest.md` (downloaded 2026-08-26).

**Partially rejected: #17 (cosine matrix size).** Codex conflated two different matrices. The
*genome* matrix is 16,376 × 1,128 = **73.9 MB** as float32, which is what `PLAN.md` states and
what was measured. The full *similarity* matrix would indeed be 16,376² × 4 = 1.07 GB — which is
precisely why the measurement used 1024-row blocked computation and never materialised it. The
number in the plan is right; the omission Codex is really pointing at is that the plan never said
the computation is blocked. Accepted on that basis, and peak RSS will be recorded.

**Most consequential accepted findings**, in rough order:

1. **`MERGE` is not reconciliation (#6).** Lowering K or re-running after a data refresh leaves
   stale `SIMILAR_TO` edges forever. The repo convention "ingestion is idempotent — use MERGE" is
   necessary but not sufficient. Moving to generation-rebuild plus a readiness flag.
2. **API contract does not match the stated goal (#11).** The goal promises navigation by cast,
   director and genre, but `expand?n` only ever described similarity neighbours. This is a gap I
   introduced by closing the expansion question with only `SIMILAR_TO` in view.
3. **Lucene injection in search (#12)** and **unparameterised Cypher (#13).** `q` reaches a
   full-text index that interprets Lucene syntax. Both are security findings, not polish.
4. **`DIRECTED`/`ACTED_IN` are Person→Movie (#9).** Every movie-centred traversal must be
   undirected or the cast and directors silently vanish.
5. **The Workers TCP claim was false (#15).** Cloudflare does expose outbound TCP sockets. HTTPS
   remains the right choice for simplicity, but the justification in the plan was wrong and is
   removed rather than restated.
6. **Aura cap ambiguity (#1).** The user's own Create Instance screenshot states 200k/400k, which
   is the strongest available evidence and is retained. But Codex is right that other Neo4j pages
   say 50k/175k — under which this graph fails outright. A preflight check now gates ingestion
   instead of trusting either figure.

`METADATA.md` corrections: the genre table is relabelled (it counts all 86,537 movies, not the
genome subset, so it cannot validate the 35,217 figure), and the "reproduce any figure" claim is
downgraded to match what is actually documented.

## Round 2 — Codex

`VERDICT: REVISE` — 10 findings, **all 10 accepted**.

Most prior findings are addressed. These remain material:

- Capacity is still unresolved: if the 50k/175k Aura limit applies, K=0 still leaves 87,543 nodes and 210,512 fixed relationships; “K is the shrinkable parameter” cannot save it. Neo4j’s public pages conflict between 50k/175k and 200k/400k. Fix: make the live limit a hard precondition and specify a smaller dataset or paid-tier fallback. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:221), [Neo4j FAQ](https://neo4j.com/free-graph-database/), [Aura Free page](https://neo4j.com/videos/getting-started-with-aura-free-tier/))
- “Fresh generation” conflicts with global uniqueness constraints: duplicate `movieId`s cannot coexist, and retaining the old generation would peak around 175k nodes/696k relationships. Fix: use a separate staging database or explicitly accept downtime for clear-and-reload, including peak-capacity checks.
- The new `titleType` filter may reduce the 16,376-film set, but all matrix dimensions, tconst filters, coverage, and graph counts still assume 16,376. Fix: compute the allowed intersection first, use it everywhere, and remeasure all counts.
- Checksums are not actually pinned: `imdb_manifest.md` stores only the first 16 hex characters, is ignored by Git, and no MovieLens checksum exists. Fix: commit a manifest with full SHA-256 hashes for every source archive. ([imdb_manifest.md](/Users/ignaciopastorebenaim/movie_mole/data/derived/imdb_manifest.md:1), [.gitignore](/Users/ignaciopastorebenaim/movie_mole/.gitignore:28))
- `expand` still orders cast, director, and genre results by `imdbVotes`, although those one-hop targets are `Person` or `Genre` nodes without that property; year filters have the same problem. Fix: define type-specific ordering/filter semantics or make movie recommendations explicitly two-hop.
- `{id}` remains ambiguous between MovieLens `movieId`, IMDb ID, and TMDB ID. Fix: declare the namespace in the endpoint contract or provide separate routes.
- Verification still omits an explicit `Genre`/`HAS_GENRE` stage and does not require per-label/type counts, unresolved joins, duplicate pair checks, or a ready full-text index. Fix: emit those invariants and gate readiness on `SHOW FULLTEXT INDEXES` reporting `ONLINE`. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:88), [Neo4j full-text docs](https://www.neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/))
- The public API has injection defenses but no application-level rate limiting, caching, or concurrency budget; a scraper can still exhaust the Worker/Aura resources. The plan also does not require a read-only database credential. Fix: add bounded caching/rate limiting and isolate the Worker with a reader credential where the tier supports it. ([Aura pricing](https://neo4j.com/pricing/))
- “Spanish-speaking country” is not an explicit region allowlist, so the 91.9% alias figure is not reproducible across implementations. Fix: list the exact ISO codes and test the resulting count.
- `CLAUDE.md` still mandates Neo4j Community/Docker/FastAPI/nginx, while the plan now mandates Aura/Worker/Pages; the review log’s opening table also repeats obsolete cap, TCP, alias-cost, and rating claims. Fix: update or clearly mark those documents as historical. ([CLAUDE.md](/Users/ignaciopastorebenaim/movie_mole/CLAUDE.md:9), [PLAN-REVIEW-LOG.md](/Users/ignaciopastorebenaim/movie_mole/PLAN-REVIEW-LOG.md:7))

VERDICT: REVISE
### Claude's response

No rejections this round. The capacity finding is the one that matters, and it broke my previous
mitigation outright.

**1. Capacity — my round-1 fix was arithmetic nonsense.** I wrote that "K is the shrinkable
parameter." Codex pointed out that under a 50k node cap the graph fails on *nodes*, which K does
not touch: even at K=0 it is 16,376 Movies + 71,148 Persons + 19 Genres = 87,543, 75% over. A
real fallback is now computed — drop the `Person` layer and set K=8, giving 16,395 nodes /
145,643 relationships (33% / 83% of 50k/175k). K=10 in that fallback would be 172,785, 98.7% of
cap, too tight. This is now marked **BLOCKING**: nothing is built until the live limit is probed.

**2. Generation rebuild was impossible as specified.** Uniqueness constraints are global, so two
generations cannot both hold a `movieId`, and keeping both would peak near 175k nodes / 696k
relationships. AuraDB Free has one database, so there is nowhere to stage. Replaced with
clear-and-reload plus explicitly accepted downtime.

**3. `titleType` filter — self-inflicted, now removed.** I added it in round 1 while fixing a
different finding and never remeasured. Measured impact: it drops **814 titles (4.97%)**, taking
16,376 → 15,562 and invalidating every downstream count. Composition: `movie` 15,298, `tvMovie`
264, `short` 232, `video` 227, `tvSpecial` 120, `tvMiniSeries` 105, `tvEpisode` 48, `tvSeries` 23,
`tvShort` 20, absent 39. Decision: **no filter**. Genome membership is the curation, the filter
would discard shorts and direct-to-video films that belong, and the genuinely non-film entries are
0.6% noise. All counts stay valid at 16,376.

**5. `expand` was returning the wrong node type.** `cast`, `director` and `genre` are **two-hop**
traversals returning `Movie`; only `similar` is one hop. As written they returned `Person`/`Genre`
nodes, which carry neither `year` nor `imdbVotes` — so the year filter and vote ordering were
meaningless. Per-type patterns and ordering are now specified. `genre` flagged as dangerous: Drama
alone links 33,681 films.

**4, 6, 7, 8, 9, 10 — all accepted as stated:** full SHA-256 for all 12 source files in a
*committed* `data/MANIFEST.md` (the old one was truncated to 16 hex chars, gitignored, and had no
MovieLens entry); `{movieId}` namespace declared in the route; verification gated on per-label
counts, unresolved joins, duplicate-pair check and `SHOW FULLTEXT INDEXES` = `ONLINE`; rate
limiting, edge caching and a read-only credential required; the exact ISO region allowlist
`{ES,MX,AR,CO,CL,PE,VE,UY}` documented so the 91.9% figure reproduces; `CLAUDE.md` rewritten (it
still mandated Neo4j Community, Docker, FastAPI and nginx) and this log's Act 1 table marked
HISTORICAL.

## Round 3 — Codex

`VERDICT: REVISE` — 8 findings, **all 8 accepted**.

Most round-2 findings are addressed: checksums, ID namespace, API bounds, traversal direction, two-hop node type, rate limiting, CLAUDE.md, and the source manifest are improved.

Remaining/new issues:

- The duplicate-pair readiness check is guaranteed to fail. Undirected Cypher matching returns both orientations, so every low→high edge also produces a row where `a.movieId > b.movieId`. Fix: use `MATCH (a)-[:SIMILAR_TO]->(b)` for this invariant. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:109), [Cypher docs](https://neo4j.com/docs/cypher-manual/current/patterns/reference/node-and-relationship-patterns/))
- The low-cap fallback is not integrated with the product: dropping `Person` removes cast/director navigation, while the API, UI, and full expected-count table still promise it. The live-cap probe is also unspecified, and Neo4j’s public limits still conflict. Fix: require the 200k/400k profile, or define a separate reduced product with its own API, UI, counts, and verification. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:265), [Neo4j FAQ](https://neo4j.com/free-graph-database/), [Aura Free page](https://neo4j.com/videos/getting-started-with-aura-free-tier/))
- `DETACH DELETE everything` can erase unrelated data and deletes whatever readiness marker exists; requests during reload can observe an empty graph. Fix: assert the database is dedicated, delete only owned data, and keep readiness external or in an excluded sentinel that makes the API fail closed.
- `LIMIT 25` bounds the response, not the two-hop aggregation: genre/cast/director queries may scan and sort thousands of candidates before limiting. The `33,681` genre figure is also from all 86,537 movies, not the loaded genome subset. Fix: measure actual subset fanout and precompute/cap candidates; add `o <> m`, `count(DISTINCT ...)`, and a deterministic `movieId` tiebreaker. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:155))
- The selected Aura Free tier has no concrete read-only-credential path; “where the tier permits one” leaves the Worker potentially holding a write-capable password. Fix: make a reader-capable tier/user a hard prerequisite or explicitly document the residual admin-credential risk. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:178), [Neo4j pricing](https://neo4j.com/pricing/))
- `data/METADATA.md` still points to the obsolete `data/derived/imdb_manifest.md`, while PLAN.md and CLAUDE.md use `data/MANIFEST.md`. Fix: update the stale reference and remove the obsolete manifest.
- `.gitignore` still ignores the new `data/samples/title.*.tsv` files via `title.*.tsv*`, contradicting CLAUDE.md’s claim that samples of every input are committed. Fix: add a later negation for `data/samples/title.*.tsv` or scope the ignore rule to `data/imdb/`. ([.gitignore](/Users/ignaciopastorebenaim/movie_mole/.gitignore:34))
- The timeline only specifies behavior for year-filtered queries; movies with `year = null` still need explicit rendering behavior. Fix: omit them or place them in an “Unknown year” bucket.

VERDICT: REVISE
### Claude's response

Findings are narrowing — round 1 found 21, round 2 found 10, this round 8, and several are now
about internal consistency rather than design. Two were bugs in fixes I wrote in earlier rounds.

**1. My duplicate-pair check could never pass.** I specified verifying `(a)-[:SIMILAR_TO]-(b)
WHERE a.movieId > b.movieId` equals 0. Undirected matching returns **both** orientations of every
edge, so half the rows always satisfy that predicate — the invariant I wrote to catch corruption
was itself guaranteed to fail. Now a directed `->` match. This is the second time an undirected
traversal has bitten this plan, after `DIRECTED`/`ACTED_IN` in round 1.

**4. `genre` expansion is removed, and the figure I cited was the wrong one.** I justified genre
being "dangerous" with Drama = 33,681 films — a count over all 86,537 movies, not the loaded
graph, in a table I had *already relabelled* for that exact error in round 2. The real
genome-subset figure is **7,670**, which is still catastrophic: a Drama two-hop generates
**58,821,230 candidate pairs** to scan and sort before `LIMIT` applies, since `LIMIT` bounds the
response and not the aggregation. Rather than tune it, `genre` is dropped as an expansion type
and kept as a filter on the others — where its weak signal belongs. Also added, all missing:
`o <> m`, `count(DISTINCT ...)`, and a deterministic `movieId` tiebreaker.

**2. The low-cap fallback is now a gate, not a paragraph.** Codex's point stands: a fallback that
drops `Person` while the Goal, API allowlist, UI toggles, count table and verification invariants
all still promise cast navigation leaves the document self-contradictory. The probe now
**stops the project** on a low cap rather than silently degrading, and the reduced product — which
is genuinely viable at 16,395 nodes / 145,643 relationships — gets its own planning pass if needed.

**7. Six of fourteen samples were never committed.** The `title.*.tsv*` ignore rule silently
matched `data/samples/title.basics.head.tsv` and five siblings, so `CLAUDE.md`'s claim that samples
of every input are committed was false. Rules scoped to `data/imdb/`; all 14 samples verified
tracked and all bulk data verified still ignored.

**3, 5, 6, 8 accepted as stated:** blanket `DETACH DELETE` replaced with an assert-then-delete-own-
labels sequence plus external fail-closed readiness (503 mid-reload, never an empty graph presented
as real); the read-only credential weasel-wording replaced with a plain statement that AuraDB Free
has no RBAC so the Worker holds a write-capable credential, stated as accepted residual risk;
`METADATA.md`'s stale `data/derived/imdb_manifest.md` reference fixed; and `year = null` movies get
an explicit "Unknown year" timeline bucket.

## Round 4 — Codex

`VERDICT: REVISE` — 9 findings, **all 9 accepted**. One reverses a change I made in round 3.

Most round-3 findings are closed: the directed duplicate check, scoped deletion, readiness failure mode, checksum references, sample ignore rules, namespace, and null-year UI behavior.

Remaining issues:

- `genre` is still in the API allowlist and UI toggle mapping, but the plan later says it is not an expansion type; the Goal and CLAUDE.md still promise genre navigation, and no genre-filter API parameter exists. Fix: remove genre from the promise/allowlist or define a real bounded genre filter.
- The `58,821,230` genre figure is global ordered pairs (`7,670 × 7,669`), not the candidate count for one request with a fixed starting movie; one request sees at most about 7,669 Drama candidates. Fix: benchmark worst-case per-movie latency before deleting the feature, and do not justify the scope change with the global count. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:173))
- The capacity “probe” fills the live database with throwaway data until a write fails, then relies on cleanup; an OOM, storage failure, or interrupted cleanup can leave the instance unusable. Fix: use documented live-tier metadata or a disposable instance, not saturation of the target database. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:307))
- The lower-cap branch now correctly stops rather than silently dropping `Person`, but the plan still depends on conflicting Aura limits; current Neo4j pages advertise both 50k/175k and 200k/400k. Fix: make the actual capacity an externally verified prerequisite before any destructive operation. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:299), [Neo4j FAQ](https://neo4j.com/free-graph-database/), [Aura Free page](https://neo4j.com/videos/getting-started-with-aura-free-tier/))
- “Dedicated database” is inferred only from labels; unlabeled data or another application using `Movie`, `Person`, or `Genre` would survive the check while its relationships could be detached. Fix: require a dedicated database or assert ownership of every node and relationship type before deletion. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:97))
- The readiness record’s storage location is unspecified; an in-database sentinel outside the three allowed labels would trigger the ownership abort, while an external record needs a concrete Worker/KV deployment and versioning plan. Fix: specify the readiness store and its fail-closed state transition.
- A director can connect the same candidate movie through multiple directors; the plan requires distinct actor counting but not distinct candidate movies for every expansion type. Fix: group/deduplicate by `o` before ordering and limiting, with the stated movie-ID tiebreaker.
- The hard-coded expected counts are tied to the current snapshot, while refreshes are explicitly supported and `METADATA.md` admits the derived counts are still ad hoc. Fix: compute a source-versioned dry-run manifest before deletion and verify against that manifest.
- Storage/index headroom and similarity peak RSS remain open; entity counts alone do not prove the full-text index and blocked computation fit the Free instance. Fix: require measured store growth and peak RSS with safety margins before clearing the database. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:326))

VERDICT: REVISE
### Claude's response

**The important one is #2, and it is a correction of me.** In round 3 I deleted `genre` from the
expansion allowlist, justifying it with "58,821,230 candidate pairs". Codex pointed out that this
is `7,670 × 7,669` — every Drama pair in the graph — not the candidates for one request. A single
expansion from one movie sees at most **~7,669** candidates, which is unremarkable for Neo4j. I
removed a feature named in the Goal on the strength of multiplying two numbers that should never
have been multiplied.

`genre` is **restored**, with the real constraint stated (it is the weakest signal and should rank
below `similar`), and with worst-case per-movie latency flagged for benchmarking against the live
instance — bounded is not the same as fast on limited vCPU. This is the third round in which the
error was mine and the review caught it; it is also the first time the review has argued me *out*
of a restriction rather than into one.

**#3 and #4 — the capacity probe was itself dangerous.** I specified filling the live database with
throwaway data until writes fail. Codex is right that an OOM, storage failure, or interrupted
cleanup could leave the instance unusable, and that saturating the target destroys what is being
measured. Replaced: **the first ingestion into a fresh empty instance is the probe.** Nothing of
value exists there yet, so a refused write costs nothing and reveals the exact cap. The destructive
clear-and-reload path is now only ever used on an instance whose capacity a successful first load
has already proven.

**#5 — "dedicated database" was an inference, not an assertion.** Checking that no label outside the
allowlist exists cannot see unlabelled nodes, and another application using `Movie`/`Person`/`Genre`
would pass while having its relationships detached. Now asserted by construction: total node count
must equal the sum of owned labels, total relationship count the sum of owned types. Abort on
mismatch.

**#6 — the readiness record had nowhere to live.** An in-database sentinel outside the three allowed
labels would have tripped the ownership abort I had just specified. Resolved with a `(:Meta)` node —
inside the ownership allowlist, explicitly excluded from deletion, holding `ready`, the source
manifest hash, and a timestamp. API fails closed with 503.

**#7, #8, #9 accepted:** `DISTINCT o` required for *every* expansion type, not just shared-actor
counting (a co-directed film is otherwise reachable through each director and returned twice);
expected counts now come from a **dry-run manifest computed from the sources before any deletion**,
stamped with the source hash, rather than the snapshot figures written into this document, which go
stale by design once refreshes are supported; and storage/index headroom is promoted to **BLOCKING**
— entity counts prove the counters fit, not that the store and full-text index fit on a
memory-limited tier.

## Round 5 — Codex (final round, MAX_ROUNDS=5)

`VERDICT: REVISE` — 2 blocking, 4 refinements. **All applied.**

Round-4 findings are mostly addressed: the duplicate check, scoped deletion, readiness failure mode, dry-run counts, sample ignores, explicit residual credential risk, and restored genre path are all reflected.

Blocking issues:

- `(:Meta {key:'readiness'})` is now a real owned node, but it is absent from the data model, expected node table, and total `87,543` count; the readiness count check can therefore fail by one. Fix: add `Meta: 1` and a `Meta.key` uniqueness constraint, or explicitly exclude `Meta` from all source-graph counts.
- Pages and the Worker are separate deployments, but no same-origin routing or CORS/`OPTIONS` contract exists; the browser can be unable to call the API. Fix: choose same-origin routing or allow only the Pages origin explicitly.

Phase 1 refinements:

- The restored genre estimate is still too low as a bound: a movie with multiple genres can scan the union of several genre fanouts, not merely the largest single genre’s 7,669 films. Fix: measure maximum per-movie candidate paths across all genres and use that in the latency/abuse gate. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:194))
- The risk list still calls expansion “one hop,” while cast, director, and genre are two-hop; this can mislead implementation. Fix: call it type-specific one- or two-hop expansion. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:318))
- Give the full-text index a stable name in the schema contract so the Worker can query the intended index unambiguously.
- Peak RSS remains unmeasured, but this is local-only and can be handled during the first Phase 1 run; it does not block the design if the run is a hard gate before deployment.

The Aura capacity and storage/index checks remain genuine external preconditions, but the plan now correctly refuses to proceed when they fail; they are not additional review defects.

VERDICT: REVISE
### Claude's response

Both blockers were real, small, and are now fixed. Codex also explicitly confirmed that the Aura
capacity and storage/index gates "remain genuine external preconditions, but the plan now correctly
refuses to proceed when they fail; they are not additional review defects" — those are the two
things only the live instance can settle.

**Blocker 1 — an off-by-one that would have aborted every run.** I introduced `(:Meta)` in round 4
to hold readiness, added it to the ownership allowlist, and never added it to the expected node
count. The assertion I wrote one paragraph earlier compares total nodes against the sum of owned
labels — so it would have computed 87,544 against an expected 87,543 and aborted, every time.
Fixed: `Meta` appears in the data model, the count table (total now **87,544**), and has its own
uniqueness constraint.

**Blocker 2 — the browser could not have called the API.** Pages and the Worker are separate
deployments on different origins, and no routing or CORS contract existed anywhere in the plan.
Chosen: **same-origin routing**, mounting the Worker under the Pages domain at `/api/*`, so the SPA
calls relative paths and no preflight occurs. The CORS fallback is specified as naming *only* the
Pages origin — never `*`, which on a free-tier budget would let any site drive the API.

**Refinement — my restored genre bound was still 3.4× too low.** I used Drama's 7,670 films as the
worst case. Codex noted a movie carries several genres and scans their union. Measured: worst case
is `movieId` 81132 with ten genres — **25,956 paths and 15,087 distinct candidates**, against my
stated 7,669. Still bounded and fine for Neo4j, but the corrected figures are now in the plan.
This is the second consecutive round where a genre number of mine was wrong in a different way.

**Also applied:** the risk list called expansion "one hop" while three of four types are two-hop
(misleading to implement against); and the full-text index now has an explicit name, `movieSearch`,
so the Worker addresses the intended index unambiguously.

**Peak RSS** stays open by agreement — local-only, no effect on the database, recorded during the
first Phase 1 run, which is itself a hard gate before deployment.

---

## Act 2 resolution — MAX_ROUNDS reached

Five rounds, 50 findings, **49 accepted**. The single partial rejection was round 1's cosine matrix
size, where Codex conflated the genome matrix (73.9 MB, correct as stated) with the similarity
matrix (1.07 GB, never materialised) — accepted on the different grounds that the plan had failed
to say the computation is blocked.

| Round | Findings | Accepted |
|---|---|---|
| 1 | 21 | 20 |
| 2 | 10 | 10 |
| 3 | 8 | 8 |
| 4 | 9 | 9 |
| 5 | 6 | 6 |

Trajectory: design-level flaws in rounds 1–2, internal contradictions in 3–4, and by round 5 an
off-by-one and a missing deployment contract. Notably, four rounds caught errors in fixes made in
*previous* rounds, and round 4 argued me **out** of an over-correction rather than into a
restriction.

No `VERDICT: APPROVED` was reached, and convergence is not being faked. What remains is not a
disagreement between Claude and Codex — every round-5 finding is applied. What remains are two
**external preconditions** that no amount of review can settle, and which the plan now refuses to
proceed without:

1. **AuraDB Free's real capacity.** Neo4j's own pages say both 200k/400k and 50k/175k. The design
   survives the former and not the latter.
2. **Storage and full-text index headroom.** Entity counts fit; store bytes and index memory on a
   "limited memory" tier are unproven.

Both are answered by the first ingestion into a fresh instance, which is now specified as a
non-destructive gate.

## Round 6 — Codex ✅

`VERDICT: APPROVED` — 5 refinements, explicitly "not design blockers". All applied anyway.

Round-4 findings are addressed. The corrected genre figures are coherent, `Meta` is counted, routing/CORS is specified, and `movieSearch` is named. I am not counting the accepted Aura capacity/storage gates as defects.

Remaining refinements, none blocking implementation:

- The API table uses `/search` and `/movie/...`, while same-origin routing mounts the Worker at `/api/*`; define whether the Worker strips `/api` or make `/api/...` the public contract.
- `CLAUDE.md` still says a genre expansion reaches at most ~7,669 candidates, but the corrected worst case is 25,956 paths and 15,087 candidates. Update the stale bound. ([CLAUDE.md](/Users/ignaciopastorebenaim/movie_mole/CLAUDE.md:58))
- The plan’s capacity narrative still says 87,543 nodes in places, while the authoritative table is 87,544 including `Meta`; update the stale prose. ([PLAN.md](/Users/ignaciopastorebenaim/movie_mole/PLAN.md:357))
- Add an exclusive ingestion lock or explicit single-run runbook before supporting refreshes; concurrent clear-and-reload processes could race on `Meta.ready`.
- Ensure edge-cache lookups cannot bypass the `Meta.ready = false` check during reload; check readiness before cache reads or version/purge cached responses.

These are straightforward Phase 1/2 implementation details, not design blockers.

VERDICT: APPROVED
### Claude's response

Approved. Codex confirmed it was not counting the Aura capacity and storage gates as defects, as
agreed in round 5. All five refinements applied:

1. **`/api` prefix contract.** The route table said `/search` while same-origin routing mounts the
   Worker at `/api/*` — genuinely ambiguous. Now stated: the public contract is `/api/...`, the
   Worker strips the prefix internally, handler paths stay as tabled.
2. **`CLAUDE.md` carried the superseded genre bound** (~7,669) that round 4 had already corrected
   in `PLAN.md`. Two documents, two numbers, one of them wrong — the exact drift this review keeps
   catching. Now 25,956 paths / 15,087 candidates in both.
3. **Stale `87,543` in prose** where the authoritative table says 87,544 including `Meta`. Four
   occurrences fixed; the fallback node figure corrected to 16,396 for the same reason.
4. **Ingestion lock.** `Meta` gains `lockedBy`/`lockedAt`, claimed in a conditional write. Two
   concurrent clear-and-reload runs could otherwise interleave one's delete with the other's load.
5. **Cache invalidation tied to readiness.** A cached response served mid-reload would bypass the
   `Meta.ready = false` check entirely and hand back the previous generation while the graph is
   half-deleted. Cache keys now include the readiness generation stamp, so a new load implicitly
   invalidates every prior entry and no purge step can be forgotten.

## Act 2 final — APPROVED at round 6

| Round | Findings | Accepted | Character |
|---|---|---|---|
| 1 | 21 | 20 | design flaws: security, reconciliation, false platform claims |
| 2 | 10 | 10 | broken fixes: K could not rescue the cap; generations impossible |
| 3 | 8 | 8 | internal contradictions: an invariant that could never pass |
| 4 | 9 | 9 | over-correction: argued Claude back into a deleted feature |
| 5 | 6 | 6 | an off-by-one that would abort every run; missing CORS contract |
| 6 | 5 | 5 | cross-document drift — **APPROVED** |
| **total** | **59** | **58** | |

One partial rejection across six rounds: round 1's cosine matrix size, where Codex conflated the
genome matrix (73.9 MB, correct as written) with the similarity matrix (1.07 GB, never
materialised) — accepted on the different grounds that the plan had not said the computation is
blocked.

Five of six rounds caught errors in fixes made in earlier rounds. Round 4 is the one that most
justifies cross-model review: it argued Claude *out* of deleting a feature named in the project
Goal, on the grounds that the justifying arithmetic multiplied two numbers that should never have
been multiplied.

Two external preconditions remain by design, and the plan refuses to proceed without either:
AuraDB Free's real capacity, and storage/full-text-index headroom. Both are answered by the first
non-destructive ingestion into a fresh instance.
