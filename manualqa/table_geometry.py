"""Place a table's cells on the page from its text lines.

The parser gives a table's structure (rows and columns, as HTML) and the page gives text
lines with exact boxes. Lines are grouped into visual rows, HTML rows are aligned to visual
rows in order, and each line goes to a cell of its own aligned row. A line is never given
to a cell in another row: a missing box is better than another row's box (a CAGE code
repeated on every parts row must highlight its own row).
"""

from __future__ import annotations

import statistics

from rapidfuzz import fuzz

from manualqa.blocks import Block, Cell, Line
from manualqa.geometry import Box
from manualqa.textnorm import norm

ROW_GAP = 0.6  # new visual row when a centre is this many line heights below the row
MATCH_MIN = 85  # partial_ratio for a line to belong to a cell
SHORT = 4  # texts this short must equal the cell exactly ("5" is not in "68505")
MAX_SPAN = 5  # visual rows one HTML row may cover (wrapped cells, group labels)


def _visual_rows(lines: list[Line]) -> list[list[Line]]:
    if not lines:
        return []
    height = statistics.median(ln.box.y1 - ln.box.y0 for ln in lines)
    rows: list[list[Line]] = []
    for ln in sorted(lines, key=lambda ln: ln.box.center[1]):
        if rows:
            mean = statistics.fmean(x.box.center[1] for x in rows[-1])
            if ln.box.center[1] - mean <= ROW_GAP * height:
                rows[-1].append(ln)
                continue
        rows.append([ln])
    return [sorted(r, key=lambda ln: ln.box.x0) for r in rows]


def _match(line: str, cell: str) -> float:
    if not line or not cell:
        return 0.0
    if len(line) <= SHORT or len(cell) <= SHORT:
        return 100.0 if line == cell else 0.0
    return fuzz.partial_ratio(line, cell)


def _union(boxes: list[Box]) -> Box:
    return Box(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


def place_cells(block: Block, lines: list[Line]) -> None:
    """Set each cell's box to the union of the lines that belong to it (or None)."""
    by_row: dict[int, list[Cell]] = {}
    for c in block.cells:
        c.box = None
        by_row.setdefault(c.row, []).append(c)
    html_rows = [sorted(by_row[r], key=lambda c: c.col) for r in sorted(by_row)]
    visual = _visual_rows(lines)
    if not html_rows or not visual:
        return

    cell_text = [[norm(c.text) for c in row] for row in html_rows]
    line_text = [[norm(ln.text) for ln in vrow] for vrow in visual]

    # score[i][j]: +1 per line of visual row j that fits a cell of HTML row i, -1 otherwise
    score = [
        [
            sum(
                1 if max((_match(t, c) for c in cells), default=0) >= MATCH_MIN else -1
                for t in vtexts
            )
            for vtexts in line_text
        ]
        for cells in cell_text
    ]

    n, m = len(html_rows), len(visual)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    choice: dict[tuple[int, int], tuple[str, int]] = {}
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            options = [
                (best[i + 1][j], ("skip_html", 0)),
                (best[i][j + 1], ("skip_vis", 0)),
            ]
            total = 0.0
            for k in range(1, MAX_SPAN + 1):
                if j + k > m or score[i][j + k - 1] <= 0:
                    break
                total += score[i][j + k - 1]
                options.append((total + best[i + 1][j + k], ("span", k)))
            best[i][j], choice[(i, j)] = max(options, key=lambda o: o[0])

    i = j = 0
    while i < n and j < m:
        kind, k = choice[(i, j)]
        if kind == "skip_html":
            i += 1
        elif kind == "skip_vis":
            j += 1
        else:
            _fill_row(html_rows[i], cell_text[i], visual[j : j + k])
            i, j = i + 1, j + k


def _fill_row(cells: list[Cell], texts: list[str], vrows: list[list[Line]]) -> None:
    lines = sorted((ln for vrow in vrows for ln in vrow), key=lambda ln: ln.box.x0)
    filled = [c for c, t in zip(cells, texts) if t]
    rank = {id(c): r for r, c in enumerate(filled)}
    owned: dict[int, list[Box]] = {}
    for pos, ln in enumerate(lines):
        t = norm(ln.text)
        scored = [
            (_match(t, ct), -abs(rank[id(c)] - pos), c)
            for c, ct in zip(cells, texts)
            if ct
        ]
        scored = [s for s in scored if s[0] >= MATCH_MIN]
        if scored:
            _, _, cell = max(scored, key=lambda s: (s[0], s[1]))
            owned.setdefault(id(cell), []).append(ln.box)
    for c in cells:
        if id(c) in owned:
            c.box = _union(owned[id(c)])


def row_boxes(block: Block) -> dict[int, Box]:
    """Union of each row's boxed cells; rows without a boxed cell are absent."""
    rows: dict[int, list[Box]] = {}
    for c in block.cells:
        if c.box is not None:
            rows.setdefault(c.row, []).append(c.box)
    return {r: _union(b) for r, b in rows.items()}
