"""Rebuild a table from a trusted text layer's own grid.

A parser's table structure can be wrong: a row holding the next row's part number, a header
missing a column. On a text-layer page the printed lines have exact positions, so when the
header line's columns line up with the data, rows and columns are read from the page itself.
Only numbered item lists are rebuilt; any other table is left to the parser, which reads
stacked headers and tables of numbers better than this does.
"""

from __future__ import annotations

import re

from manualqa.blocks import Block, Cell, Line
from manualqa.geometry import Box
from manualqa.table_geometry import _union, _visual_rows

MIN_COLUMNS = 3
MIN_ROWS = 3
HEADER_SEARCH = 8  # the header line is among this many leading visual rows
ALIGN = (
    0.025  # a data line belongs to a column whose left edge is this near (page widths)
)
MIN_ALIGNED = 0.9  # share of data lines that must fit the grid
# "B1821 .SCREW": a code with no spaces, run into a description that starts with leader dots
_MERGED = re.compile(r"^(\S*[A-Za-z0-9]\S*)\s+((?:\.\s*)+[A-Za-z].*)$")
_ITEM_NUMBER = re.compile(r"^\d+[A-Za-z']?$")
MIN_NUMBERED = 0.8  # share of rows that must start with an item number
MIN_WORDY = 0.5  # share of rows that must hold words, not only numbers
_TRAILING_QTY = re.compile(r"^(.*\S)\s+(\d+|V)$")
_FOOTER = {"END OF FIGURE"}


def _header_row(visual: list[list[Line]]) -> int | None:
    """The leading row with the most columns, the last of equals: the one over the data."""
    best, width = None, MIN_COLUMNS - 1
    for i, row in enumerate(visual[:HEADER_SEARCH]):
        if len(row) >= width and not any(
            ln.text.strip()[:1].isdigit() for ln in row[:1]
        ):
            best, width = i, len(row)
    return best


def _nearest(x: float, columns: list[float]) -> tuple[int, float]:
    col = min(range(len(columns)), key=lambda i: abs(columns[i] - x))
    return col, abs(columns[col] - x)


def _labels(
    visual: list[list[Line]], header: int, columns: list[float]
) -> dict[int, Cell]:
    """Each column's label, stacked from the header rows above it."""
    parts: dict[int, list[Line]] = {}
    edges = [*columns[1:], 1.01]
    for row in visual[: header + 1]:
        for ln in row:
            mid = ln.box.center[0]
            col = next(i for i, e in enumerate(edges) if mid < e - ALIGN)
            parts.setdefault(col, []).append(ln)
    return {
        c: Cell(
            0,
            c,
            " ".join(ln.text.strip() for ln in lns),
            _union([x.box for x in lns]),
            header=True,
        )
        for c, lns in parts.items()
    }


def _split_merged(ln: Line, col: int, columns: list[float], row: dict) -> list[tuple]:
    """A line that ran two or three cells together, as (column, text) pairs."""
    text = ln.text.strip()
    merged = _MERGED.match(text)
    if not merged or col + 1 >= len(columns):
        return [(col, text)]
    out = [(col, merged.group(1)), (col + 1, merged.group(2))]
    qty = _TRAILING_QTY.match(merged.group(2))
    if qty and col + 2 < len(columns):
        out[1:] = [(col + 1, qty.group(1)), (col + 2, qty.group(2))]
    return out


def _is_item_list(starts: list[list[Line]]) -> bool:
    """A numbered first column with words in the rows."""
    numbered = sum(bool(_ITEM_NUMBER.match(r[0].text.strip())) for r in starts)
    wordy = sum(any(re.search(r"[A-Za-z]{3}", ln.text) for ln in r[1:]) for r in starts)
    return numbered >= MIN_NUMBERED * len(starts) and wordy >= MIN_WORDY * len(starts)


def rebuild_from_grid(block: Block, lines: list[Line]) -> bool:
    """Replace the block's cells from its lines; False, unchanged, if there is no clear grid."""
    visual = _visual_rows(lines)
    header = _header_row(visual)
    if header is None:
        return False
    columns = sorted(ln.box.x0 for ln in visual[header])
    data = visual[header + 1 :]
    flat = [ln for row in data for ln in row]
    if not flat:
        return False
    aligned = sum(_nearest(ln.box.x0, columns)[1] <= ALIGN for ln in flat)
    if aligned / len(flat) < MIN_ALIGNED:
        return False
    starts = [r for r in data if _nearest(r[0].box.x0, columns)[0] == 0]
    if len(starts) < MIN_ROWS or not _is_item_list(starts):
        return False

    built: list[dict[int, list]] = []
    current: dict[int, list] | None = None
    heading: dict[int, list] | None = None
    for row in data:
        begins = _nearest(row[0].box.x0, columns)[0] == 0
        if begins:
            current = {}
            built.append(current)
        elif current is None:
            if heading is None:
                heading = {}
                built.append(heading)
        target = current if current is not None else heading
        for ln in row:
            if ln.text.strip() in _FOOTER:
                continue
            col, _ = _nearest(ln.box.x0, columns)
            for c, text in _split_merged(ln, col, columns, target):
                target.setdefault(c, []).append((text, ln.box))

    labels = _labels(visual, header, columns)
    cells = [labels[c] for c in sorted(labels)]
    for r, row in enumerate(built, 1):
        for c, pieces in sorted(row.items()):
            boxes: list[Box] = [b for _, b in pieces]
            text = " ".join(t for t, _ in pieces)
            cells.append(Cell(r, c, text, _union(boxes)))
    block.cells = cells
    return True
