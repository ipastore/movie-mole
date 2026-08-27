from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import resource
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np


csv.field_size_limit(sys.maxsize)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "MANIFEST.md"
INGESTION_MANIFEST_PATH = ROOT / "data" / "derived" / "ingestion-manifest.json"

SOURCE_RELATIVE_PATHS = {
    "genome-scores.csv": "data/ml-latest/genome-scores.csv",
    "genome-tags.csv": "data/ml-latest/genome-tags.csv",
    "links.csv": "data/ml-latest/links.csv",
    "movies.csv": "data/ml-latest/movies.csv",
    "ratings.csv": "data/ml-latest/ratings.csv",
    "tags.csv": "data/ml-latest/tags.csv",
    "name.basics.tsv.gz": "data/imdb/name.basics.tsv.gz",
    "title.akas.tsv.gz": "data/imdb/title.akas.tsv.gz",
    "title.basics.tsv.gz": "data/imdb/title.basics.tsv.gz",
    "title.crew.tsv.gz": "data/imdb/title.crew.tsv.gz",
    "title.principals.tsv.gz": "data/imdb/title.principals.tsv.gz",
    "title.ratings.tsv.gz": "data/imdb/title.ratings.tsv.gz",
}

SPANISH_REGIONS = {"ES", "MX", "AR", "CO", "CL", "PE", "VE", "UY"}
ENGLISH_ARTICLES = {"The", "A", "An"}
YEAR_RE = re.compile(r"\((\d{4})\)")
YEAR_SUFFIX_RE = re.compile(r"\s*\(\s*(\d{4})\s*\)\s*$")


class ChecksumError(RuntimeError):
    pass


@dataclass(slots=True)
class Movie:
    movie_id: int
    title: str
    year: int | None
    imdb_id: str
    tmdb_id: int | None
    imdb_rating: float | None = None
    imdb_votes: int | None = None
    search_aliases: list[str] = field(default_factory=list)
    genres: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Person:
    nconst: str
    name: str


@dataclass(frozen=True, slots=True)
class Similarity:
    low_movie_id: int
    high_movie_id: int
    score: float


@dataclass(slots=True)
class Dataset:
    movies: list[Movie]
    people: list[Person]
    acted_in: list[tuple[str, int]]
    directed: list[tuple[str, int]]
    has_genre: list[tuple[int, str]]
    similar_to: list[Similarity]
    similarity_peak_rss_mib: float | None = None


def _source_paths(root: Path) -> dict[str, Path]:
    return {name: root / relative for name, relative in SOURCE_RELATIVE_PATHS.items()}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_manifest_hash(manifest_path: Path = MANIFEST_PATH) -> str:
    return _sha256(manifest_path)


def _manifest_entries(manifest_path: Path) -> dict[str, tuple[int, str]]:
    entries: dict[str, tuple[int, str]] = {}
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*`([0-9a-f]{64})`\s*\|")
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        match = pattern.fullmatch(line)
        if match:
            entries[match.group(1)] = (int(match.group(2)), match.group(3))
    return entries


def verify_sources(root: Path = ROOT, manifest_path: Path = MANIFEST_PATH) -> str:
    expected = _manifest_entries(manifest_path)
    missing_manifest = set(SOURCE_RELATIVE_PATHS) - set(expected)
    if missing_manifest:
        raise ChecksumError(f"manifest is missing: {sorted(missing_manifest)}")

    for name, relative in SOURCE_RELATIVE_PATHS.items():
        path = root / relative
        if not path.is_file():
            raise ChecksumError(f"source is missing: {path}")
        expected_bytes, expected_hash = expected[name]
        actual_bytes = path.stat().st_size
        if actual_bytes != expected_bytes:
            raise ChecksumError(
                f"size mismatch for {path}: expected {expected_bytes}, got {actual_bytes}"
            )
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise ChecksumError(
                f"SHA-256 mismatch for {path}: expected {expected_hash}, got {actual_hash}"
            )
    return _sha256(manifest_path)


def _open_csv(path: Path):
    return path.open("r", encoding="utf-8-sig", newline="")


def _open_tsv(path: Path):
    return gzip.open(path, "rt", encoding="utf-8", newline="")


def _nullable(value: str) -> str | None:
    return None if value in {"", r"\N"} else value


def _nullable_int(value: str) -> int | None:
    value = _nullable(value)
    return None if value is None else int(value)


def _nullable_float(value: str) -> float | None:
    value = _nullable(value)
    return None if value is None else float(value)


def format_tconst(imdb_id: str | int) -> str:
    return f"tt{str(imdb_id).zfill(7)}"


def extract_year(title: str) -> int | None:
    matches = list(YEAR_RE.finditer(title))
    return None if not matches else int(matches[-1].group(1))


def title_without_year(title: str) -> str:
    matches = list(YEAR_RE.finditer(title))
    if not matches:
        return title.strip()

    last = matches[-1]
    suffix = YEAR_SUFFIX_RE.search(title)
    if suffix and suffix.start() <= last.start() and suffix.group(1) == last.group(1):
        return title[: suffix.start()].rstrip()

    without = title[: last.start()] + title[last.end() :]
    return re.sub(r"\s{2,}", " ", without).strip()


def normalize_title(title: str) -> str:
    clean = title_without_year(title)
    open_parenthesis = clean.find("(")
    if open_parenthesis == -1:
        main, parenthetical = clean.strip(), ""
    else:
        main = clean[:open_parenthesis].rstrip()
        parenthetical = clean[open_parenthesis:].strip()

    match = re.fullmatch(r"(.+), (The|A|An)", main)
    if match and match.group(2) in ENGLISH_ARTICLES:
        main = f"{match.group(2)} {match.group(1)}"
    return main + (f" {parenthetical}" if parenthetical else "")


def read_genome_movie_ids(path: Path) -> list[int]:
    movie_ids: set[int] = set()
    with _open_csv(path) as source:
        rows = csv.reader(source)
        next(rows, None)
        for row in rows:
            if row:
                movie_ids.add(int(row[0]))
    return sorted(movie_ids)


def read_genome_tags(path: Path) -> dict[int, int]:
    tag_columns: dict[int, int] = {}
    with _open_csv(path) as source:
        rows = csv.reader(source)
        next(rows, None)
        for column, row in enumerate(rows):
            if not row:
                continue
            tag_id = int(row[0])
            if tag_id in tag_columns:
                raise ValueError(f"duplicate tagId: {tag_id}")
            tag_columns[tag_id] = column
    return tag_columns


def build_genome_matrix(
    path: Path, movie_ids: Iterable[int], tag_columns: dict[int, int]
) -> np.ndarray:
    movie_ids = list(movie_ids)
    row_by_movie_id = {movie_id: row for row, movie_id in enumerate(movie_ids)}
    matrix = np.zeros((len(movie_ids), len(tag_columns)), dtype=np.float32)
    counts = np.zeros(len(movie_ids), dtype=np.int32)

    with _open_csv(path) as source:
        rows = csv.reader(source)
        next(rows, None)
        for row in rows:
            if not row:
                continue
            movie_id, tag_id, relevance = int(row[0]), int(row[1]), float(row[2])
            try:
                row_index = row_by_movie_id[movie_id]
                column = tag_columns[tag_id]
            except KeyError as error:
                raise ValueError(f"genome score references unknown id: {error.args[0]}") from error
            matrix[row_index, column] = relevance
            counts[row_index] += 1

    if not np.all(counts == len(tag_columns)):
        bad_rows = np.flatnonzero(counts != len(tag_columns))[:10].tolist()
        raise ValueError(f"genome matrix is not dense; bad row indexes: {bad_rows}")
    return matrix


def _normalise_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1)
    assert np.all(norms > 0), "genome contains a zero-norm movie"
    matrix /= norms[:, None]
    return matrix


def _top_k_indices(scores: np.ndarray, movie_ids: np.ndarray, k: int) -> np.ndarray:
    partition = np.argpartition(-scores, k - 1)[:k]
    threshold = scores[partition].min()
    selected_thresholds = np.count_nonzero(scores[partition] == threshold)
    all_thresholds = np.flatnonzero(scores == threshold)
    candidates = np.flatnonzero(scores >= threshold) if len(all_thresholds) > selected_thresholds else partition
    order = np.lexsort((movie_ids[candidates], -scores[candidates]))
    return candidates[order[:k]]


def compute_similarities(
    matrix: np.ndarray,
    movie_ids: Iterable[int],
    k: int = 10,
    block_size: int = 1024,
) -> list[Similarity]:
    movie_ids = np.asarray(list(movie_ids), dtype=np.int64)
    if matrix.ndim != 2 or matrix.shape[0] != len(movie_ids):
        raise ValueError("matrix rows and movie IDs do not match")
    if not 0 < k < len(movie_ids):
        raise ValueError("k must be between 1 and the number of movies minus 1")
    if block_size < 1:
        raise ValueError("block_size must be positive")

    matrix = _normalise_rows(np.asarray(matrix, dtype=np.float32))
    pairs: dict[tuple[int, int], float] = {}
    for start in range(0, len(movie_ids), block_size):
        end = min(start + block_size, len(movie_ids))
        scores = matrix[start:end] @ matrix.T
        local_rows = np.arange(end - start)
        scores[local_rows, np.arange(start, end)] = -np.inf
        for local_row, row_scores in enumerate(scores):
            row_index = start + local_row
            neighbours = _top_k_indices(row_scores, movie_ids, k)
            for neighbour_index in neighbours:
                left, right = int(movie_ids[row_index]), int(movie_ids[neighbour_index])
                low, high = sorted((left, right))
                pairs.setdefault((low, high), float(row_scores[neighbour_index]))

    return [
        Similarity(low, high, score)
        for (low, high), score in sorted(pairs.items())
    ]


def _read_links(path: Path) -> dict[int, tuple[str, int | None]]:
    links: dict[int, tuple[str, int | None]] = {}
    with _open_csv(path) as source:
        rows = csv.reader(source)
        next(rows, None)
        for row in rows:
            if not row:
                continue
            movie_id = int(row[0])
            links[movie_id] = (format_tconst(row[1]), _nullable_int(row[2]))
    return links


def _read_movies(path: Path, genome_ids: set[int]) -> dict[int, dict[str, object]]:
    movies: dict[int, dict[str, object]] = {}
    with _open_csv(path) as source:
        rows = csv.reader(source)
        next(rows, None)
        for row in rows:
            if not row:
                continue
            movie_id = int(row[0])
            if movie_id not in genome_ids:
                continue
            genres = tuple(
                genre
                for genre in row[2].split("|")
                if genre and genre != "(no genres listed)"
            )
            movies[movie_id] = {
                "title": row[1],
                "year": extract_year(row[1]),
                "genres": genres,
            }
    return movies


def _read_year_backfills(path: Path, missing_tconsts: set[str]) -> dict[str, int]:
    years: dict[str, int] = {}
    with _open_tsv(path) as source:
        rows = csv.reader(source, delimiter="\t")
        next(rows, None)
        for row in rows:
            if len(row) > 5 and row[0] in missing_tconsts and row[5] != r"\N":
                years[row[0]] = int(row[5])
    return years


def _read_ratings(path: Path, tconsts: set[str]) -> dict[str, tuple[float, int]]:
    ratings: dict[str, tuple[float, int]] = {}
    with _open_tsv(path) as source:
        rows = csv.reader(source, delimiter="\t")
        next(rows, None)
        for row in rows:
            if row and row[0] in tconsts:
                ratings[row[0]] = (float(row[1]), int(row[2]))
    return ratings


def _read_aliases(path: Path, tconsts: set[str]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = defaultdict(list)
    with _open_tsv(path) as source:
        rows = csv.reader(source, delimiter="\t")
        next(rows, None)
        for row in rows:
            if len(row) < 5 or row[0] not in tconsts:
                continue
            if row[4] == "es" or row[3] in SPANISH_REGIONS:
                aliases[row[0]].append(row[2])
    return aliases


def _read_directors(path: Path, tconsts: set[str]) -> dict[str, set[str]]:
    directors: dict[str, set[str]] = defaultdict(set)
    with _open_tsv(path) as source:
        rows = csv.reader(source, delimiter="\t")
        next(rows, None)
        for row in rows:
            if len(row) < 2 or row[0] not in tconsts or row[1] == r"\N":
                continue
            directors[row[0]].update(nconst for nconst in row[1].split(",") if nconst)
    return directors


def _read_actors(path: Path, tconsts: set[str]) -> dict[str, list[str]]:
    actors: dict[str, list[str]] = defaultdict(list)
    with _open_tsv(path) as source:
        rows = csv.reader(source, delimiter="\t")
        next(rows, None)
        for row in rows:
            if len(row) >= 4 and row[0] in tconsts and row[3] in {"actor", "actress"}:
                actors[row[0]].append(row[2])
    return actors


def _read_names(path: Path, person_ids: set[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    with _open_tsv(path) as source:
        rows = csv.reader(source, delimiter="\t")
        next(rows, None)
        for row in rows:
            if row and row[0] in person_ids:
                names[row[0]] = row[1]
                if len(names) == len(person_ids):
                    break
    missing = person_ids - names.keys()
    if missing:
        # ponytail: one pinned IMDb principal has no name row; keep its edge with a stable placeholder.
        names.update({nconst: f"Unknown ({nconst})" for nconst in missing})
    return names


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if __import__("sys").platform == "darwin":
        return value / (1024 * 1024)
    return value / 1024


def _write_derived(root: Path, movie_ids: list[int], movies: list[Movie]) -> None:
    derived = root / "data" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    (derived / "genome_movie_ids.txt").write_text(
        "".join(f"{movie_id}\n" for movie_id in movie_ids), encoding="utf-8"
    )
    (derived / "genome_imdb_tconsts.txt").write_text(
        "".join(f"{movie.imdb_id}\n" for movie in movies), encoding="utf-8"
    )


def build_dataset(
    root: Path = ROOT,
    similarity_k: int = 10,
    similarity_block_size: int = 1024,
    write_derived: bool = True,
) -> Dataset:
    paths = _source_paths(root)
    tag_columns = read_genome_tags(paths["genome-tags.csv"])
    movie_ids = read_genome_movie_ids(paths["genome-scores.csv"])
    genome_id_set = set(movie_ids)
    links = _read_links(paths["links.csv"])
    raw_movies = _read_movies(paths["movies.csv"], genome_id_set)

    missing_movies = genome_id_set - raw_movies.keys()
    missing_links = genome_id_set - links.keys()
    if missing_movies:
        raise ValueError(f"genome movies missing from movies.csv: {sorted(missing_movies)[:10]}")
    if missing_links:
        raise ValueError(f"genome movies missing from links.csv: {sorted(missing_links)[:10]}")

    movies: list[Movie] = []
    for movie_id in movie_ids:
        raw = raw_movies[movie_id]
        imdb_id, tmdb_id = links[movie_id]
        movies.append(
            Movie(
                movie_id=movie_id,
                title=normalize_title(raw["title"]),
                year=raw["year"],
                imdb_id=imdb_id,
                tmdb_id=tmdb_id,
                genres=raw["genres"],
            )
        )
    movie_by_tconst = {movie.imdb_id: movie for movie in movies}
    tconsts = set(movie_by_tconst)

    missing_year_tconsts = {
        movie.imdb_id for movie in movies if movie.year is None
    }
    backfill_years = _read_year_backfills(paths["title.basics.tsv.gz"], missing_year_tconsts)
    for tconst, year in backfill_years.items():
        movie_by_tconst[tconst].year = year

    ratings = _read_ratings(paths["title.ratings.tsv.gz"], tconsts)
    aliases = _read_aliases(paths["title.akas.tsv.gz"], tconsts)
    for movie in movies:
        rating = ratings.get(movie.imdb_id)
        if rating:
            movie.imdb_rating, movie.imdb_votes = rating
        movie.search_aliases = aliases.get(movie.imdb_id, [])

    directors = _read_directors(paths["title.crew.tsv.gz"], tconsts)
    actors = _read_actors(paths["title.principals.tsv.gz"], tconsts)
    person_ids = set().union(*directors.values(), *actors.values()) if (directors or actors) else set()
    names = _read_names(paths["name.basics.tsv.gz"], person_ids)
    people = [Person(nconst, names[nconst]) for nconst in sorted(person_ids)]
    movie_id_by_tconst = {movie.imdb_id: movie.movie_id for movie in movies}
    directed = sorted(
        (nconst, movie_id_by_tconst[tconst])
        for tconst, nconsts in directors.items()
        for nconst in nconsts
    )
    acted_in = sorted(
        (nconst, movie_id_by_tconst[tconst])
        for tconst, nconsts in actors.items()
        for nconst in nconsts
    )

    has_genre = [
        (movie.movie_id, genre)
        for movie in movies
        for genre in movie.genres
    ]

    matrix = build_genome_matrix(paths["genome-scores.csv"], movie_ids, tag_columns)
    similarities = compute_similarities(
        matrix,
        movie_ids,
        k=similarity_k,
        block_size=similarity_block_size,
    )
    similarity_peak_rss_mib = _rss_mib()
    if write_derived:
        _write_derived(root, movie_ids, movies)

    del matrix
    return Dataset(
        movies=movies,
        people=people,
        acted_in=acted_in,
        directed=directed,
        has_genre=has_genre,
        similar_to=similarities,
        similarity_peak_rss_mib=similarity_peak_rss_mib,
    )


def manifest_for(dataset: Dataset, source_hash: str, similarity_k: int = 10) -> dict[str, object]:
    return {
        "sourceManifestHash": source_hash,
        "similarityK": similarity_k,
        "nodes": {
            "Movie": len(dataset.movies),
            "Person": len(dataset.people),
            "Genre": len({genre for _, genre in dataset.has_genre}),
            "Meta": 1,
        },
        "relationships": {
            "ACTED_IN": len(dataset.acted_in),
            "DIRECTED": len(dataset.directed),
            "HAS_GENRE": len(dataset.has_genre),
            "SIMILAR_TO": len(dataset.similar_to),
        },
    }


def write_manifest(manifest: dict[str, object], path: Path = INGESTION_MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
