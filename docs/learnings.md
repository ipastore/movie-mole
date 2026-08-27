# Learnings

Compounding notes from this repo. Newest at the bottom. Each entry: what happened, why it
mattered, and what to do differently — not a changelog.

---

## 2026-08-26 — Phase 0 → Phase 1, via grill + 6 rounds of Codex review

### Measure the data before you plan around it

The original plan specified computing movie similarity from co-ratings: 33.8M ratings in a 934 MB
file, an item-item shuffle measured in hours, and the single riskiest step in the project.

It never needed to exist. `genome-scores.csv` has 18,472,128 rows and `genome-tags.csv` has 1,128
tags. `18,472,128 ÷ 1,128 = 16,376` **remainder 0** — a dense matrix, every movie scored against
every tag, already derived by GroupLens from 330,975 users' ratings *and* tags. The hours-long
computation became a 74 MB matrix and a 4-second blocked cosine, and `ratings.csv` left the design
entirely.

That was not a clever insight. It was `wc -l` and a division. The plan had been reasoning *about*
the dataset instead of *measuring* it.

**Do differently:** before planning anything data-shaped, count the rows, check the coverage,
sample the file. A plan whose numbers are estimates will be wrong in ways review cannot catch,
because review can only check internal consistency — it cannot know that 16,376 is the real number.

### `max(id)` is not `count(rows)`

Reading `movies.csv`, it looked like 288,983 movies. It is 86,537 rows whose IDs run *up to*
288,983 — MovieLens has assigned IDs since 1995 and the space is full of gaps.

This class of error fails silently. Size an array by `max(movieId)` and you allocate 3.3× what you
need; assume density and you index into gaps and get empty results with no exception. The same
trap sits in `userId`.

**Do differently:** `sort -u | wc -l`, never `tail -1`. Dicts and sets keyed by real IDs, never
positional arrays. And when a count is surprising, check whether you measured a count or a maximum.

### A green proof is not a correct build

Codex's Phase 1 build passed its proof on the first run: 20 tests green, all seven graph counts
exactly matching figures measured independently. It looked like unambiguous success.

It shipped a corrupted title. `movieId` 171749 is `Death Note: Desu nôto (2006–2007)` — a year
*range*. The year regex omitted the parentheses the spec required, matched `2007`, and stripped it
from *inside* the parenthetical, producing `Death Note: Desu nôto (2006–)`.

A mangled title changes no count. Every number stayed correct, so the proof could not see it. It
surfaced only from reading the regex against the spec and then hunting the real data for a case
that would expose the difference.

**Do differently:** proof tests verify the properties you thought to check. Read the diff against
the spec anyway, and when an implementation deviates from spec — even harmlessly-looking — go find
the input that makes the deviation visible. There was exactly one such title in 16,376.

### Fixes introduce bugs at a rate worth planning for

Five of six adversarial review rounds found defects in fixes made in *earlier rounds*:

- Round 1's `MERGE`-is-idempotent fix ignored that `MERGE` never removes stale edges
- Round 2's "generation rebuild" was impossible — global uniqueness constraints, one database
- Round 2's `titleType` filter silently dropped 814 movies, invalidating every count in the document
- Round 3's `SIMILAR_TO` integrity check could **never pass**: an undirected match returns both
  orientations, so half the rows always violate `a.movieId > b.movieId`
- Round 4's `(:Meta)` node was added to the ownership allowlist but not the expected count — it
  would have aborted every ingestion run by exactly one

**Do differently:** re-review after fixing, not just after building. And when a fix changes a
number, grep the whole document for that number — most of these were consistency failures, not
reasoning failures.

### Adversarial review also catches over-correction

Round 3 deleted `genre` expansion — a feature named in the project goal — justified by "58,821,230
candidate pairs." Round 4 pointed out that figure is `7,670 × 7,669`: every Drama pair in the
graph, not the candidates for one request. A single expansion sees ~7,669. The feature came back.

Worth noting because the failure mode of adversarial review is assumed to be excessive caution.
Here it argued *against* a restriction, on arithmetic grounds.

**Do differently:** when a number justifies removing scope, state what it counts. "58 million
pairs" and "58 million pairs *for a query nobody runs*" are different facts.

### Cross-document drift is the convergence signal

Findings went 21 → 10 → 8 → 9 → 6 → APPROVED. The final round's findings were almost all *drift*:
`CLAUDE.md` carried a bound `PLAN.md` had already corrected; prose said 87,543 where the table said
87,544. Two files, two numbers, one wrong.

When a review stops finding design flaws and starts finding disagreements between your own
documents, the design has converged and the remaining work is bookkeeping.

### Give a review agent samples, not archives

The first Codex run stalled and hit a 10-minute ceiling with no output, against a repo that had
just grown to 3.3 GB of compressed datasets.

The fix was not to tell it to skip `data/` — that would have left it reviewing data claims it could
not check. It was 100-line samples of all 12 inputs plus a `METADATA.md` of measured figures: 84 KB
that let it verify the plan's claims rather than trust them. It then found that my genre table was
labelled "genome subset" while counting all 86,537 movies — an error only visible to something that
could see both the number and the data.

**Do differently:** a self-describing repo (samples + measured metadata, committed) is worth more
than access to the raw data, for humans and agents alike.

### Undirected traversal, twice

Neo4j relationships have direction; queries need not respect it. Both mistakes cost a round:

- `DIRECTED` and `ACTED_IN` point Person→Movie, so a movie-outgoing pattern returns **nothing** —
  cast and directors silently vanish
- The duplicate-pair check must be `-[:SIMILAR_TO]->` — undirected returns both orientations, so
  the check can never pass

**Do differently:** for every traversal, ask which way the arrow points and whether the query cares.
Write it down in the schema, next to the relationship.

### Provenance is not a checksum you didn't commit

The plan claimed the graph was "100% reproducible." It pinned IMDb as `current` — a dataset that
republishes daily. When challenged, the first fix stored 16 hex characters of SHA-256, in a
gitignored directory, with no MovieLens entry at all.

**Do differently:** full hashes, every source, committed, verified before the run aborts. Anything
less is a gesture at reproducibility rather than the thing.
