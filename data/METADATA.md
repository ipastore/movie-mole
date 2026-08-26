# Dataset metadata

Everything here was **measured** from the real files, not estimated. The files themselves are
gitignored (3.3 GB); 100-line samples of each live in `data/samples/`.

Where a shell one-liner produced a figure it is shown beside it. Coverage percentages,
relationship counts, dedup ratios and timings came from ad-hoc Python over the full files and are
**not yet reproducible from a committed script** — Phase 1 ingestion will emit them as a manifest.

## Sources

| Source | Release | Local path | Size |
|---|---|---|---|
| MovieLens `ml-latest` | 2023-07-20, full SHA-256 in `data/MANIFEST.md` | `data/ml-latest/` | 1.5 GB |
| IMDb non-commercial | downloaded 2026-08-26, full SHA-256 in `data/MANIFEST.md` | `data/imdb/` | 1.8 GB |

Both are **non-commercial use only**. See the Licensing section of `PLAN.md`.

## MovieLens `ml-latest`

Per its README: *"33832162 ratings and 2328315 tag applications across 86537 movies … created
by 330975 users between January 09, 1995 and July 20, 2023."*

| File | Size | Data rows | Schema |
|---|---|---|---|
| `ratings.csv` | 934 MB | 33,832,162 | `userId, movieId, rating, timestamp` |
| `genome-scores.csv` | 521 MB | 18,472,128 | `movieId, tagId, relevance` |
| `tags.csv` | 85 MB | 2,328,315 | `userId, movieId, tag, timestamp` |
| `movies.csv` | 4 MB | 86,537 | `movieId, title, genres` |
| `links.csv` | 1.9 MB | 86,537 | `movieId, imdbId, tmdbId` |
| `genome-tags.csv` | 18 KB | 1,128 | `tagId, tag` |

## The tag genome — the core of this project

`18,472,128 ÷ 1,128 = 16,376` with **remainder 0**. Every genome movie carries a relevance
score against all 1,128 tags, so the matrix is dense with no gaps.

```bash
tail -n +2 genome-scores.csv | cut -d, -f1 | sort -un | wc -l    # -> 16376
```

That dense `16,376 × 1,128` matrix is **73.9 MB as float32**. L2-normalising the rows makes the
dot product equal cosine similarity. Loading takes ~13 s, the cosine ~4 s.

Genome coverage lines up almost exactly with the movies that have enough ratings to matter —
GroupLens already made the "enough data" cut:

```
movies with >=   1 ratings : 83,239
movies with >=  10 ratings : 32,021
movies with >=  50 ratings : 16,116   <-- genome covers 16,376
movies with >= 100 ratings : 12,253
movies with >= 500 ratings :  6,312
movies with >=1000 ratings :  4,464
```

## IMDb non-commercial

| File | Size | Used? |
|---|---|---|
| `title.principals.tsv.gz` | 744 MB | ✅ cast (`category` = `actor`/`actress`) |
| `title.akas.tsv.gz` | 488 MB | ✅ Spanish search aliases |
| `name.basics.tsv.gz` | 294 MB | ✅ `nconst` → name |
| `title.basics.tsv.gz` | 216 MB | ✅ `startYear` backfill, `titleType` |
| `title.crew.tsv.gz` | 79 MB | ✅ directors |
| `title.ratings.tsv.gz` | 8.2 MB | ✅ `averageRating`, `numVotes` |
| `title.episode.tsv.gz` | 52 MB | ❌ TV episodes |

## Measured coverage over the 16,376 genome movies

| Attribute | Coverage | Missing |
|---|---|---|
| `imdbId` in `links.csv` | **100.00%** | 0 |
| `tmdbId` in `links.csv` | 99.91% | 15 |
| Year parseable from title | 99.72% | 46 |
| Director (`title.crew`) | 99.72% | 46 |
| **Cast (`title.principals`)** | **95.26%** | **776** |
| Any alternate title (`title.akas`) | 99.8% | 39 |
| **Spanish title** (`language=es` or Spanish-speaking `region`) | **91.9%** | 1,322 |

## Measured graph size (K=10, symmetric pairs stored once)

| Nodes | | Relationships | |
|---|---|---|---|
| `Movie` | 16,376 | `ACTED_IN` | 156,759 |
| `Person` | 71,148 | `SIMILAR_TO` | 137,568 |
| `Genre` | 19 | `HAS_GENRE` | 35,217 |
| | | `DIRECTED` | 18,536 |
| **total** | **87,543** | **total** | **348,080** |

Against the AuraDB Free cap of 200,000 / 400,000: **44% of nodes, 87% of relationships.**

`SIMILAR_TO` symmetric dedup, measured:

| K | directed | deduped | saved |
|---|---|---|---|
| 8 | 131,008 | 110,426 | 15.7% |
| **10** | 163,760 | **137,568** | **16.0%** |
| 12 | 196,512 | 164,652 | 16.2% |

Average `SIMILAR_TO` degree is `137,568 × 2 ÷ 16,376 = 16.8` — a movie holds its own top-10 plus
every movie that selected it. **Expansion queries must always `LIMIT`.**

Cast depth is not worth tuning — IMDb self-caps `title.principals` at ~10 principals per title
(mean 10.0, max 31), so taking *all* cast costs only 3% more edges than top-10:

```
top-3   46,387    top-8  122,241
top-5   76,923    top-10 151,983    ALL 156,759
```

## Genre distribution — ALL 86,537 movies, not the genome subset

19 real genres; `(no genres listed)` is a placeholder and is discarded.

```
Drama 33,681 · Comedy 22,830 · Thriller 11,675 · Romance 10,172 · Action 9,563
Documentary 9,283 · Horror 8,570 · Crime 6,917 · Adventure 5,349 · Sci-Fi 4,850
Animation 4,579 · Children 4,367 · Mystery 3,972 · Fantasy 3,821 · War 2,301
Western 1,690 · Musical 1,059 · Film-Noir 354 · IMAX 195
```
**These counts are over the full 86,537-movie file and therefore do NOT validate the 35,217
`HAS_GENRE` edges**, which are counted over the 16,376 genome movies only. `(no genres listed)`
applies to 7,060 of the 86,537 and is discarded.

## Year distribution (genome subset, 1888–2023)

```
1920s     93      1970s    909      2010s  4,281
1930s    230      1980s  1,684      2020s    666
1940s    353      1990s  2,839
1950s    491      2000s  4,063
1960s    700
```

## Ingestion gotchas — all confirmed in the real files

1. **`movieId` is sparse, not a count.** `max(movieId) = 288,983` but only 86,537 rows exist;
   `genome-scores` reaches 288,167 for 16,376 movies. Never size arrays by max ID or assume
   density — use dicts and sets keyed by the real IDs, and an explicit `movieId → row_index`
   map when building the genome matrix.
2. **CRLF line endings** in the MovieLens CSVs. Naive `split(',')` leaves `\r` on the last field.
3. **7,540 titles contain commas** and are quote-escaped: `11,"American President, The (1995)",…`.
   Use a real CSV parser.
4. **Year is embedded in the title**, sometimes with more than one parenthesised group:
   `"City of Lost Children, The (Cité des enfants perdus, La) (1995)"`. Take the **last**
   `(\d{4})`.
5. **`links.csv` `imdbId` has no `tt` prefix** and is zero-padded to 7 digits (`0114709`).
   IMDb uses `tt0114709` — format as `"tt" + str(id).zfill(7)` or every join silently returns
   nothing. Pre-built list: `data/derived/genome_imdb_tconsts.txt`.
6. **1,045 people both act and direct.** `MERGE` `Person` on `nconst` once and attach both
   relationship types, or they are duplicated.
7. **Titles are sorted-form** — `"American President, The"`. Normalised on ingest (English
   articles only).
8. **`title.akas` averages 38 alternate titles per movie** across all languages. Filter to
   Spanish at ingest or you store ~620k strings instead of 35,520.

## Derived artefacts

| File | Contents |
|---|---|
| `data/derived/genome_movie_ids.txt` | 16,376 MovieLens `movieId`s, one per line (128 KB) |
| `data/derived/genome_imdb_tconsts.txt` | the same films as `tt`-prefixed IMDb ids (164 KB) |

Both are regenerated by ingestion and are gitignored.
