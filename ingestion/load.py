from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Any, Iterable

from .pipeline import Dataset, build_dataset, manifest_for, verify_sources, write_manifest


BATCH_SIZE = 1_000
LOCK_KEY = "readiness"
INDEX_NAME = "movieSearch"

CONSTRAINT_QUERIES = (
    "CREATE CONSTRAINT movie_id IF NOT EXISTS FOR (m:Movie) REQUIRE m.movieId IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.nconst IS UNIQUE",
    "CREATE CONSTRAINT genre_nm IF NOT EXISTS FOR (g:Genre) REQUIRE g.name IS UNIQUE",
    "CREATE CONSTRAINT meta_key IF NOT EXISTS FOR (x:Meta) REQUIRE x.key IS UNIQUE",
)
INDEX_QUERIES = (
    "CREATE INDEX movie_year IF NOT EXISTS FOR (m:Movie) ON (m.year)",
    "CREATE FULLTEXT INDEX movieSearch IF NOT EXISTS FOR (m:Movie) ON EACH [m.title, m.searchAliases]",
)

NODE_COUNT_QUERIES = {
    "Movie": "MATCH (n:Movie) RETURN count(n) AS count",
    "Person": "MATCH (n:Person) RETURN count(n) AS count",
    "Genre": "MATCH (n:Genre) RETURN count(n) AS count",
    "Meta": "MATCH (n:Meta) RETURN count(n) AS count",
}
RELATIONSHIP_COUNT_QUERIES = {
    "ACTED_IN": "MATCH ()-[r:ACTED_IN]->() RETURN count(r) AS count",
    "DIRECTED": "MATCH ()-[r:DIRECTED]->() RETURN count(r) AS count",
    "HAS_GENRE": "MATCH ()-[r:HAS_GENRE]->() RETURN count(r) AS count",
    "SIMILAR_TO": "MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS count",
}
TOTAL_NODE_QUERY = "MATCH (n) RETURN count(n) AS count"
TOTAL_RELATIONSHIP_QUERY = "MATCH ()-[r]->() RETURN count(r) AS count"

DELETE_QUERIES = {
    "Movie": "MATCH (n:Movie) WITH n LIMIT $batch DETACH DELETE n RETURN count(*) AS deleted",
    "Person": "MATCH (n:Person) WITH n LIMIT $batch DETACH DELETE n RETURN count(*) AS deleted",
    "Genre": "MATCH (n:Genre) WITH n LIMIT $batch DETACH DELETE n RETURN count(*) AS deleted",
    "Meta": (
        "MATCH (n:Meta) WHERE n.key IS NULL OR n.key <> $readiness "
        "WITH n LIMIT $batch DETACH DELETE n RETURN count(*) AS deleted"
    ),
}

MOVIE_LOAD_QUERY = """
UNWIND $rows AS row
MERGE (m:Movie {movieId: row.movieId})
SET m.title = row.title,
    m.year = row.year,
    m.imdbId = row.imdbId,
    m.tmdbId = row.tmdbId,
    m.imdbRating = row.imdbRating,
    m.imdbVotes = row.imdbVotes,
    m.searchAliases = row.searchAliases
"""
GENRE_LOAD_QUERY = """
UNWIND $rows AS row
MERGE (g:Genre {name: row.name})
"""
HAS_GENRE_LOAD_QUERY = """
UNWIND $rows AS row
MATCH (m:Movie {movieId: row.movieId}), (g:Genre {name: row.name})
MERGE (m)-[:HAS_GENRE]->(g)
"""
PERSON_LOAD_QUERY = """
UNWIND $rows AS row
MERGE (p:Person {nconst: row.nconst})
SET p.name = row.name
"""
DIRECTED_LOAD_QUERY = """
UNWIND $rows AS row
MATCH (p:Person {nconst: row.nconst}), (m:Movie {movieId: row.movieId})
MERGE (p)-[:DIRECTED]->(m)
"""
ACTED_IN_LOAD_QUERY = """
UNWIND $rows AS row
MATCH (p:Person {nconst: row.nconst}), (m:Movie {movieId: row.movieId})
CREATE (p)-[:ACTED_IN]->(m)
"""
SIMILAR_LOAD_QUERY = """
UNWIND $rows AS row
MATCH (a:Movie {movieId: row.lowMovieId}), (b:Movie {movieId: row.highMovieId})
MERGE (a)-[r:SIMILAR_TO]->(b)
SET r.score = row.score
"""

CLAIM_LOCK_QUERY = """
MERGE (x:Meta {key: $key})
ON CREATE SET x.ready = false
WITH x
WHERE x.lockedBy IS NULL
SET x.lockedBy = $lockedBy, x.lockedAt = datetime(), x.ready = false
RETURN x.lockedBy AS lockedBy
"""
RELEASE_LOCK_QUERY = """
MATCH (x:Meta {key: $key})
WHERE x.lockedBy = $lockedBy
SET x.ready = $ready,
    x.sourceManifestHash = CASE WHEN $ready THEN $sourceManifestHash ELSE x.sourceManifestHash END,
    x.builtAt = CASE WHEN $ready THEN datetime() ELSE x.builtAt END,
    x.lockedBy = NULL
RETURN count(x) AS released
"""

UNRESOLVED_PERSON_QUERY = (
    "MATCH (p:Person) WHERE p.name IS NULL OR trim(p.name) = '' RETURN count(p) AS count"
)
UNRESOLVED_RELATIONSHIP_QUERY = """
MATCH (a)-[r]->(b)
WHERE type(r) IN ['ACTED_IN', 'DIRECTED', 'HAS_GENRE', 'SIMILAR_TO']
  AND (
    (type(r) IN ['ACTED_IN', 'DIRECTED'] AND (NOT a:Person OR NOT b:Movie)) OR
    (type(r) = 'HAS_GENRE' AND (NOT a:Movie OR NOT b:Genre)) OR
    (type(r) = 'SIMILAR_TO' AND (NOT a:Movie OR NOT b:Movie))
  )
RETURN count(r) AS count
"""
DUPLICATE_SIMILAR_QUERY = (
    "MATCH (a)-[:SIMILAR_TO]->(b) WHERE a.movieId > b.movieId RETURN count(*) AS count"
)
FULLTEXT_STATE_QUERY = (
    "SHOW FULLTEXT INDEXES YIELD name, state "
    "WHERE name = $name RETURN state"
)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def _single_value(session: Any, query: str, **parameters: Any) -> Any:
    record = session.run(query, **parameters).single()
    if record is None:
        raise RuntimeError("Neo4j query returned no record")
    return record["count"] if "count" in record.keys() else record[0]


def _chunks(values: Iterable[Any], size: int = BATCH_SIZE) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for value in values:
        batch.append(value)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _run_batches(session: Any, query: str, rows: Iterable[dict[str, Any]]) -> None:
    for batch in _chunks(rows):
        session.run(query, rows=batch).consume()


def counts(session: Any) -> tuple[dict[str, int], dict[str, int]]:
    nodes = {
        label: int(_single_value(session, query))
        for label, query in NODE_COUNT_QUERIES.items()
    }
    relationships = {
        relationship: int(_single_value(session, query))
        for relationship, query in RELATIONSHIP_COUNT_QUERIES.items()
    }
    return nodes, relationships


def assert_ownership(session: Any) -> None:
    nodes, relationships = counts(session)
    total_nodes = int(_single_value(session, TOTAL_NODE_QUERY))
    total_relationships = int(_single_value(session, TOTAL_RELATIONSHIP_QUERY))
    if total_nodes != sum(nodes.values()):
        raise RuntimeError(
            f"database is not dedicated: total nodes {total_nodes} != owned labels {sum(nodes.values())}"
        )
    if total_relationships != sum(relationships.values()):
        raise RuntimeError(
            "database is not dedicated: "
            f"total relationships {total_relationships} != owned types {sum(relationships.values())}"
        )


def clear_owned_data(session: Any) -> None:
    for label, query in DELETE_QUERIES.items():
        while True:
            deleted = int(_single_value(session, query, batch=BATCH_SIZE, readiness=LOCK_KEY))
            if deleted == 0:
                break


def load_dataset(session: Any, dataset: Dataset) -> None:
    _run_batches(
        session,
        MOVIE_LOAD_QUERY,
        (
            {
                "movieId": movie.movie_id,
                "title": movie.title,
                "year": movie.year,
                "imdbId": movie.imdb_id,
                "tmdbId": movie.tmdb_id,
                "imdbRating": movie.imdb_rating,
                "imdbVotes": movie.imdb_votes,
                "searchAliases": movie.search_aliases,
            }
            for movie in dataset.movies
        ),
    )
    _run_batches(
        session,
        GENRE_LOAD_QUERY,
        ({"name": name} for name in sorted({name for _, name in dataset.has_genre})),
    )
    _run_batches(
        session,
        HAS_GENRE_LOAD_QUERY,
        ({"movieId": movie_id, "name": name} for movie_id, name in dataset.has_genre),
    )
    _run_batches(
        session,
        PERSON_LOAD_QUERY,
        ({"nconst": person.nconst, "name": person.name} for person in dataset.people),
    )
    _run_batches(
        session,
        DIRECTED_LOAD_QUERY,
        ({"nconst": nconst, "movieId": movie_id} for nconst, movie_id in dataset.directed),
    )
    _run_batches(
        session,
        ACTED_IN_LOAD_QUERY,
        ({"nconst": nconst, "movieId": movie_id} for nconst, movie_id in dataset.acted_in),
    )
    _run_batches(
        session,
        SIMILAR_LOAD_QUERY,
        (
            {
                "lowMovieId": edge.low_movie_id,
                "highMovieId": edge.high_movie_id,
                "score": edge.score,
            }
            for edge in dataset.similar_to
        ),
    )


def verify_loaded_graph(session: Any, expected: dict[str, object], timeout_seconds: int = 600) -> None:
    actual_nodes, actual_relationships = counts(session)
    if actual_nodes != expected["nodes"]:
        raise RuntimeError(f"node counts differ: expected {expected['nodes']}, got {actual_nodes}")
    if actual_relationships != expected["relationships"]:
        raise RuntimeError(
            f"relationship counts differ: expected {expected['relationships']}, got {actual_relationships}"
        )
    assert_ownership(session)
    unresolved_people = int(_single_value(session, UNRESOLVED_PERSON_QUERY))
    unresolved_relationships = int(_single_value(session, UNRESOLVED_RELATIONSHIP_QUERY))
    duplicate_similar = int(_single_value(session, DUPLICATE_SIMILAR_QUERY))
    if unresolved_people or unresolved_relationships:
        raise RuntimeError(
            f"unresolved joins: people={unresolved_people}, relationships={unresolved_relationships}"
        )
    if duplicate_similar != 0:
        raise RuntimeError(f"SIMILAR_TO edges written high-to-low: {duplicate_similar}")

    deadline = time.monotonic() + timeout_seconds
    while True:
        states = [record["state"] for record in session.run(FULLTEXT_STATE_QUERY, name=INDEX_NAME)]
        if states == ["ONLINE"]:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"{INDEX_NAME} is not ONLINE: {states}")
        time.sleep(2)


def run_load(session: Any, dataset: Dataset, source_hash: str, similarity_k: int = 10) -> None:
    expected = manifest_for(dataset, source_hash, similarity_k)
    for query in CONSTRAINT_QUERIES + INDEX_QUERIES:
        session.run(query).consume()
    assert_ownership(session)

    locked_by = secrets.token_hex(16)
    claim = session.run(CLAIM_LOCK_QUERY, key=LOCK_KEY, lockedBy=locked_by).single()
    if claim is None or claim["lockedBy"] != locked_by:
        raise RuntimeError("readiness lock is already held")

    try:
        clear_owned_data(session)
        load_dataset(session, dataset)
        verify_loaded_graph(session, expected)
        released = int(
            _single_value(
                session,
                RELEASE_LOCK_QUERY,
                key=LOCK_KEY,
                lockedBy=locked_by,
                ready=True,
                sourceManifestHash=source_hash,
            )
        )
        if released != 1:
            raise RuntimeError("readiness lock was lost before publishing")
    except Exception:
        session.run(
            RELEASE_LOCK_QUERY,
            key=LOCK_KEY,
            lockedBy=locked_by,
            ready=False,
            sourceManifestHash=source_hash,
        ).consume()
        raise


def main() -> None:
    source_hash = verify_sources()
    dataset = build_dataset()
    manifest = manifest_for(dataset, source_hash)
    write_manifest(manifest)

    load_dotenv(Path(__file__).with_name(".env"))
    uri = os.environ.get("NEO4J_URI")
    username = os.environ.get("NEO4J_USERNAME")
    password = os.environ.get("NEO4J_PASSWORD")
    if not all((uri, username, password)):
        raise RuntimeError("NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD are required")

    try:
        from neo4j import GraphDatabase
    except ImportError as error:
        raise RuntimeError("install ingestion/requirements.txt before loading") from error

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            run_load(session, dataset, source_hash)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
