"""Helpers shared by parser adapters."""

from __future__ import annotations

from manualqa.blocks import Block, Line


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
