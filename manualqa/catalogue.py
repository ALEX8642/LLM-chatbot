"""The manuals on offer, from the table in manuals/SOURCES.md."""

from __future__ import annotations

import re
from pathlib import Path


def read_manuals(manuals: Path) -> list[dict]:
    """Manuals from the table in manuals/SOURCES.md: file, title, pages."""
    out = []
    sources = Path(manuals) / "SOURCES.md"
    for line in sources.read_text().splitlines() if sources.exists() else []:
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 3 and cols[0].startswith("`") and cols[0].endswith(".pdf`"):
            title = re.sub(r"[*_]", "", cols[1])
            out.append(
                {"file": cols[0].strip("`"), "title": title, "pages": int(cols[2])}
            )
    return out
