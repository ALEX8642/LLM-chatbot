import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest

MANUALS = Path(__file__).resolve().parents[2] / "manuals"

# v1's tests/conftest.py replaces `requests` with a mock; the parser libraries need the
# real one. Restore it only for GPU parser runs, which never run v1's tests.
if os.environ.get("MANUALQA_PARSERS") == "1" and isinstance(
    sys.modules.get("requests"), MagicMock
):
    del sys.modules["requests"]


def pytest_collection_modifyitems(config, items):
    if os.environ.get("MANUALQA_PARSERS") == "1":
        return
    skip = pytest.mark.skip(reason="needs a GPU parser extra; set MANUALQA_PARSERS=1")
    for item in items:
        if "parsers" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def manual():
    """Open a bundled manual by file name (cached per session)."""
    docs = {}

    def _open(name: str) -> pymupdf.Document:
        if name not in docs:
            docs[name] = pymupdf.open(MANUALS / name)
        return docs[name]

    return _open


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="session")
def raw_pages():
    """Raw PaddleOCR parses of six spike pages, keyed by (manual, page)."""
    from manualqa.blocks import load_pages

    return {
        (pp.manual, pp.page): pp for pp in load_pages(FIXTURES / "paddle-raw.jsonl")
    }


@pytest.fixture(scope="session")
def ctx(tmp_path_factory):
    """Ingest the six fixture pages (no GPU) and index them with the fake embedder."""
    from fakes import FakeEmbedder, FakeReranker

    from manualqa import ingest
    from manualqa.chunks import load_chunks
    from manualqa.index import build_index
    from manualqa.retrieve import IngestContext

    out = tmp_path_factory.mktemp("ingest")
    root = Path(__file__).resolve().parents[2]
    ingest.main(
        [
            "--raw",
            str(FIXTURES / "paddle-raw.jsonl"),
            "--manuals",
            str(root / "manuals"),
            "--out",
            str(out),
            "--skip-index",
        ]
    )
    build_index(load_chunks(out / "chunks.jsonl"), out / "qdrant", FakeEmbedder())
    return IngestContext.load(out, FakeEmbedder(), FakeReranker())
