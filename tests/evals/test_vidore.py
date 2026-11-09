import math

import pytest

from evals.vidore import CHUNK_CHARS, ndcg, page_chunks, ranked_pages, recall


def test_ndcg_perfect_and_known_value():
    assert ndcg([1, 2], {1: 2, 2: 1}) == 1.0
    got = ndcg([2, 1], {1: 2, 2: 1})
    want = (1 + 2 / math.log2(3)) / (2 + 1 / math.log2(3))
    assert got == pytest.approx(want)


def test_ndcg_counts_only_the_top_k_and_handles_no_relevant_page():
    assert ndcg(list(range(20)) + [99], {99: 1}) == 0.0
    assert ndcg([1], {}) == 0.0


def test_recall_at_k():
    assert recall([1, 2, 3], {1: 1, 9: 2}) == 0.5


def test_pages_ranked_by_their_best_chunk():
    assert ranked_pages([(0.2, 5), (0.9, 7), (0.95, 5)]) == [5, 7]


def test_page_chunks_split_long_pages_and_keep_every_character():
    text = "\n\n".join("x" * 700 for _ in range(5))
    chunks = page_chunks(3, text)
    assert all(len(t) <= CHUNK_CHARS for _, t in chunks)
    assert [cid for cid, _ in chunks][:2] == ["3:0", "3:1"]
    assert sum(t.count("x") for _, t in chunks) == 3500


def test_an_empty_page_gives_no_chunk():
    assert page_chunks(1, "  ") == []
