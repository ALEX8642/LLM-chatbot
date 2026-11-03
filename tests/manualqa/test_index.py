from fakes import FakeEmbedder

from manualqa.chunks import Chunk
from manualqa.index import build_index, search, sparse_vector, tokens


def chunk(i, manual, text):
    return Chunk(f"c{i}", manual, [i + 1], "text", "", text, [f"b{i}"])


CHUNKS = [
    chunk(0, "parts.pdf", "17 | PAOZZ | 18265 | P14-8969 | FILTER ELEMENT,INTAKE AIR"),
    chunk(1, "parts.pdf", "16 | PAOZZ | 18265 | P10-1870 | NUT,PLAIN,WING"),
    chunk(2, "op.pdf", "Service the air cleaner element when the indicator shows red."),
]


def test_tokens_keep_identifiers():
    toks = set(tokens("Part P14-8969, CAGE 18265"))
    assert {"p14-8969", "p14", "8969", "18265", "part", "cage"} <= toks


def test_sparse_vector_stable():
    a = sparse_vector("air filter element")
    assert a == sparse_vector("air filter element")
    assert sorted(a[0]) == sorted(sparse_vector("element filter air")[0])


def test_hybrid_search_finds_part_number(tmp_path):
    build_index(CHUNKS, tmp_path / "q", FakeEmbedder())
    hits = search("P14-8969", tmp_path / "q", FakeEmbedder(), k=3)
    assert hits[0][0].id == "c0"


def test_search_filters_by_manual(tmp_path):
    build_index(CHUNKS, tmp_path / "q", FakeEmbedder())
    hits = search(
        "air cleaner element", tmp_path / "q", FakeEmbedder(), manual="op.pdf"
    )
    assert [c.manual for c, _ in hits] == ["op.pdf"]
