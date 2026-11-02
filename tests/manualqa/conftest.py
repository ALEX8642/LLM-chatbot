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
