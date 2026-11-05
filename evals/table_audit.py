"""Measures where table cell boxes land, not only how many exist.

    python -m evals.table_audit [data/ingest/composed.jsonl]

For each non-empty cell: does it have a box; does the page text under the box belong to the
cell (a box on another row fails this); and do rows run down the page in order. Text under a
box is read from the table's own lines.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz

from manualqa.blocks import load_pages
from manualqa.textnorm import norm


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", norm(text))


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def box_text(box, lines) -> str:
    """The lines whose centres fall inside the box, top to bottom."""
    inside = [
        ln
        for ln in lines
        if box.x0 <= ln.box.center[0] <= box.x1 and box.y0 <= ln.box.center[1] <= box.y1
    ]
    return " ".join(ln.text for ln in sorted(inside, key=lambda ln: ln.box.y0))


def cell_fits(cell_text: str, under_box: str) -> bool:
    """The text under the box reads as this cell: same digits, and a close match."""
    a, b = _squash(cell_text), _squash(under_box)
    if not b:
        return False
    if _digits(a) != _digits(b) and _digits(b) not in _digits(a):
        return False
    return a == b or b in a or a in b or fuzz.partial_ratio(a, b) >= 85


def audit_table(block) -> Counter:
    out = Counter(tables=1)
    rows: dict[int, list] = {}
    for c in block.cells:
        if not c.text.strip():
            continue
        out["cells"] += 1
        if c.box is None:
            out["no_box"] += 1
            continue
        out["boxed"] += 1
        rows.setdefault(c.row, []).append(c.box.center[1])
        if not cell_fits(c.text, box_text(c.box, block.lines)):
            out["wrong_text"] += 1
    order = [statistics.fmean(rows[r]) for r in sorted(rows)]
    out["rows"] = len(order)
    out["rows_out_of_order"] = sum(a > b for a, b in zip(order, order[1:]))
    return out


def audit(composed: Path) -> dict:
    totals: dict[str, Counter] = {}
    for pp in load_pages(composed):
        for b in pp.blocks:
            if b.kind == "table" and b.cells:
                totals.setdefault(pp.text_source, Counter()).update(audit_table(b))
    return {k: dict(v) for k, v in totals.items()}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else Path("data/ingest/composed.jsonl")
    print(json.dumps(audit(path), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
