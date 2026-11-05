"""Place a table's cells on the page from its text lines.

The parser gives a table's structure (rows and columns, as HTML) and the page gives text
lines with exact boxes. Lines are grouped into visual rows, HTML rows are aligned to visual
rows in order, and each line goes to a cell of its own aligned row. A line is never given
to a cell in another row: a missing box is better than another row's box (a CAGE code
repeated on every parts row must highlight its own row).
"""

from __future__ import annotations

import re
import statistics

from rapidfuzz import fuzz

from manualqa.blocks import Block, Cell, Line
from manualqa.geometry import Box
from manualqa.textnorm import norm

ROW_GAP = 0.6  # new visual row when a centre is this many line heights below the row
MATCH_MIN = 85  # partial_ratio for a line to belong to a cell
SHORT = 4  # lines this short must be a whole word of the cell ("5" is not in "68505")
MIN_COVER = 0.6  # share of a line a fuzzy match must explain
_DIGITS = re.compile(r"\d+")
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


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _words(text: str) -> list[str]:
    return [w.strip(".,;:()") for w in text.split()]


def _match(line: str, cell: str) -> float:
    """How well a line fits a cell's unused text. Short lines must be whole words of the
    cell ("208" in "208 volts", not "5" in "68505"); longer ones may be fuzzy only if every
    digit agrees, since one digit is the difference between neighbouring rows."""
    if not line or not cell:
        return 0.0
    bare = _squash(line)
    if len(bare) <= SHORT:
        return 100.0 if bare.strip(".,;:()") in _words(cell) else 0.0
    if bare in _squash(cell):
        return 100.0
    score = fuzz.partial_ratio_alignment(bare, _squash(cell))
    if score is None or score.score < MATCH_MIN:
        return 0.0
    # the two aligned stretches: a line may run on into the next cell ("... RECE 1")
    in_line = bare[score.src_start : score.src_end]
    in_cell = _squash(cell)[score.dest_start : score.dest_end]
    if len(in_line) < MIN_COVER * len(bare):  # a fragment of the line proves nothing
        return 0.0
    return score.score if _DIGITS.findall(in_line) == _DIGITS.findall(in_cell) else 0.0


def _consume(cell: str, line: str) -> str:
    """The cell's text left after a line has taken its part."""
    words = cell.split()
    bare = _squash(line).strip(".,;:()")
    for i, w in enumerate(words):
        if w.strip(".,;:()") == bare:
            return " ".join(words[:i] + words[i + 1 :])
    squashed = _squash(cell)
    at = squashed.find(_squash(line))
    if at >= 0:
        return squashed[:at] + " " + squashed[at + len(_squash(line)) :]
    aligned = fuzz.partial_ratio_alignment(_squash(line), squashed)
    return (
        squashed[: aligned.dest_start] + " " + squashed[aligned.dest_end :]
        if aligned
        else cell
    ).strip()


def _take(line: str, left: list[str], order: int) -> int | None:
    """The unused cell a line belongs to, nearest its position among ties; None if none."""
    scored = [
        (_match(line, text), -abs(i - order), i) for i, text in enumerate(left) if text
    ]
    scored = [s for s in scored if s[0] >= MATCH_MIN]
    return max(scored)[2] if scored else None


def _span_score(texts: list[str], vrows: list[list[str]]) -> float:
    """+1 per line that takes unused text of this row, -1 per line that finds none."""
    left = list(texts)
    total = 0
    for vrow in vrows:
        for pos, t in enumerate(vrow):
            i = _take(t, left, pos)
            if i is None:
                total -= 1
            else:
                left[i] = _consume(left[i], t)
                total += 1
    return total


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

    n, m = len(html_rows), len(visual)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    choice: dict[tuple[int, int], tuple[str, int]] = {}
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            options = [
                (best[i + 1][j], ("skip_html", 0)),
                (best[i][j + 1], ("skip_vis", 0)),
            ]
            before = 0.0
            for k in range(1, MAX_SPAN + 1):
                if j + k > m:
                    break
                total = _span_score(cell_text[i], line_text[j : j + k])
                if total <= before:  # this visual row adds nothing to the row: stop
                    break
                before = total
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
    filled = [(c, t) for c, t in zip(cells, texts) if t]
    left = [t for _, t in filled]
    owned: dict[int, list[Box]] = {}
    for vrow in vrows:
        for pos, ln in enumerate(sorted(vrow, key=lambda ln: ln.box.x0)):
            t = norm(ln.text)
            i = _take(t, left, pos)
            if i is not None:
                left[i] = _consume(left[i], t)
                owned.setdefault(i, []).append(ln.box)
    for i, boxes in owned.items():
        filled[i][0].box = _union(boxes)


def row_boxes(block: Block) -> dict[int, Box]:
    """Union of each row's boxed cells; rows without a boxed cell are absent."""
    rows: dict[int, list[Box]] = {}
    for c in block.cells:
        if c.box is not None:
            rows.setdefault(c.row, []).append(c.box)
    return {r: _union(b) for r, b in rows.items()}
