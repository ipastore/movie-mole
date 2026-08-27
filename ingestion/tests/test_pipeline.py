from __future__ import annotations

import csv

import numpy as np
import pytest

from ingestion.pipeline import (
    build_genome_matrix,
    compute_similarities,
    extract_year,
    format_tconst,
    normalize_title,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Die, Mommie, Die (2003)", "Die, Mommie, Die"),
        ("Play It Again, Sam (1972)", "Play It Again, Sam"),
        ("Bye Bye, Love (1995)", "Bye Bye, Love"),
        ("American President, The (1995)", "The American President"),
        ("Walk in the Clouds, A (1995)", "A Walk in the Clouds"),
        ("Awfully Big Adventure, An (1995)", "An Awfully Big Adventure"),
        ("Miserables, Les (1995)", "Miserables, Les"),
        ("Bamba, La (1987)", "Bamba, La"),
        ("Example, Le (1995)", "Example, Le"),
        ("Example, El (1995)", "Example, El"),
        ("Example, L' (1995)", "Example, L'"),
        ("Example, Il (1995)", "Example, Il"),
        ("Example, Der (1995)", "Example, Der"),
        ("Example, Das (1995)", "Example, Das"),
        (
            "City of Lost Children, The (Cite des enfants perdus, La) (1995)",
            "The City of Lost Children (Cite des enfants perdus, La)",
        ),
    ],
)
def test_normalize_title(source: str, expected: str) -> None:
    assert normalize_title(source) == expected


def test_year_uses_last_four_digit_group() -> None:
    assert extract_year("Film 2001 (director's cut) (1995)") == 1995
    assert normalize_title("Film 2001 (director's cut) (1995)") == "Film 2001 (director's cut)"


def test_year_requires_parentheses() -> None:
    """A bare four-digit number in a title is not a year.

    movieId 171749 is 'Death Note: Desu noto (2006-2007)' - a year RANGE, which
    matches no `(\\d{4})` group. A regex without the parentheses picked up 2007
    and stripped it from inside the parenthetical, corrupting the title.
    """
    assert extract_year("Death Note: Desu noto (2006-2007)") is None
    assert normalize_title("Death Note: Desu noto (2006-2007)") == "Death Note: Desu noto (2006-2007)"
    assert extract_year("Blade Runner 2049") is None
    assert normalize_title("Blade Runner 2049") == "Blade Runner 2049"
    assert extract_year("Blade Runner 2049 (2017)") == 2017


def test_sparse_movie_ids_and_crlf_csv(tmp_path) -> None:
    scores = tmp_path / "genome-scores.csv"
    with scores.open("w", encoding="utf-8", newline="") as source:
        writer = csv.writer(source, lineterminator="\r\n")
        writer.writerow(["movieId", "tagId", "relevance"])
        writer.writerows([[2, 1, 3], [2, 2, 4], [1000, 1, 0], [1000, 2, 5]])

    matrix = build_genome_matrix(scores, [2, 1000], {1: 0, 2: 1})
    assert matrix.shape == (2, 2)
    np.testing.assert_array_equal(matrix, [[3, 4], [0, 5]])


def test_tt_prefix_zero_padding() -> None:
    assert format_tconst("114709") == "tt0114709"
    assert format_tconst(7) == "tt0000007"


def test_similarity_is_deduplicated_and_tie_broken_by_movie_id() -> None:
    edges = compute_similarities(np.ones((3, 2), dtype=np.float32), [10, 20, 30], k=1)
    assert [(edge.low_movie_id, edge.high_movie_id) for edge in edges] == [(10, 20), (10, 30)]


def test_similarity_rejects_zero_norm() -> None:
    with pytest.raises(AssertionError):
        compute_similarities(np.array([[1, 0], [0, 0]], dtype=np.float32), [1, 2], k=1)
