"""Helpers shared by parser adapters."""

from __future__ import annotations

from html.parser import HTMLParser

from manualqa.blocks import Block, Cell, Line


def _contains(block: Block, x: float, y: float) -> bool:
    b = block.box
    return b.x0 <= x <= b.x1 and b.y0 <= y <= b.y1


def assign_lines(blocks: list[Block], lines: list[Line]) -> list[Line]:
    """Append each line to the smallest block containing the line's centre.
    Returns the lines no block contains."""
    orphans = []
    for line in lines:
        x, y = line.box.center
        hits = [b for b in blocks if _contains(b, x, y)]
        if hits:
            min(hits, key=lambda b: b.box.area).lines.append(line)
        else:
            orphans.append(line)
    return orphans


class _TableHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, bool, int, int]]] = []
        self._cell: list[str] | None = None
        self._attrs: dict = {}
        self._in_thead = False
        self._header = False

    def handle_starttag(self, tag, attrs):
        if tag == "thead":
            self._in_thead = True
        elif tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            self._cell, self._attrs = [], dict(attrs)
            self._header = tag == "th" or self._in_thead
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag == "thead":
            self._in_thead = False
        elif tag in ("td", "th") and self._cell is not None:
            if not self.rows:
                self.rows.append([])
            text = " ".join("".join(self._cell).split())
            span = (
                int(self._attrs.get("rowspan") or 1),
                int(self._attrs.get("colspan") or 1),
            )
            self.rows[-1].append((text, self._header, *span))
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def html_table_cells(html: str) -> list[Cell]:
    """Cells of an HTML table with their grid position. Spanned cells are recorded
    once, at their top-left position; ``box`` is None."""
    parser = _TableHTML()
    parser.feed(html)
    taken: set[tuple[int, int]] = set()
    cells = []
    for r, row in enumerate(parser.rows):
        col = 0
        for text, header, rowspan, colspan in row:
            while (r, col) in taken:
                col += 1
            cells.append(Cell(r, col, text, None, header))
            for dr in range(rowspan):
                for dc in range(colspan):
                    taken.add((r + dr, col + dc))
            col += colspan
    return cells
