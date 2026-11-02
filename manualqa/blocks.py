"""Block schema: the contract every parser adapter emits.

All boxes are page-normalised (see ``manualqa.geometry``). Block ids are
``f"{manual_stem}:p{page}:b{n}"`` with n 0-based in reading order.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

from manualqa.geometry import Box

Kind = Literal["text", "heading", "table", "figure", "caption", "other"]


@dataclass
class Line:
    text: str
    box: Box


@dataclass
class Cell:
    row: int
    col: int
    text: str
    box: Box | None
    header: bool = False


@dataclass
class Block:
    id: str
    kind: Kind
    text: str
    box: Box
    lines: list[Line] = field(default_factory=list)
    cells: list[Cell] = field(default_factory=list)


@dataclass
class PageParse:
    manual: str
    page: int
    parser: str
    width_px: int
    height_px: int
    dpi: int
    ocr: bool
    ocr_reason: str | None
    blocks: list[Block]
    seconds: float
    error: str | None = None


def _box(d: dict | None) -> Box | None:
    return None if d is None else Box(**d)


def _page_from_dict(d: dict) -> PageParse:
    blocks = [
        Block(
            id=b["id"],
            kind=b["kind"],
            text=b["text"],
            box=_box(b["box"]),
            lines=[Line(ln["text"], _box(ln["box"])) for ln in b["lines"]],
            cells=[
                Cell(c["row"], c["col"], c["text"], _box(c["box"]), c["header"])
                for c in b["cells"]
            ],
        )
        for b in d["blocks"]
    ]
    return PageParse(**{**d, "blocks": blocks})


def dump_pages(pages: Iterable[PageParse], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for pp in pages:
            f.write(json.dumps(asdict(pp), ensure_ascii=False) + "\n")


def load_pages(path: Path) -> list[PageParse]:
    with Path(path).open(encoding="utf-8") as f:
        return [_page_from_dict(json.loads(line)) for line in f if line.strip()]


def _box_problems(where: str, box: Box) -> list[str]:
    problems = []
    if any(v < 0 or v > 1 for v in (box.x0, box.y0, box.x1, box.y1)):
        problems.append(f"{where}: box outside [0,1]: {box}")
    elif box.x0 > box.x1:
        problems.append(f"{where}: x0 > x1: {box}")
    elif box.y0 > box.y1:
        problems.append(f"{where}: y0 > y1: {box}")
    return problems


def validate(pp: PageParse) -> list[str]:
    """Human-readable problems; an empty list means the page is valid."""
    problems: list[str] = []
    seen: set[str] = set()
    for b in pp.blocks:
        if b.id in seen:
            problems.append(f"{b.id}: duplicate id")
        seen.add(b.id)
        problems += _box_problems(b.id, b.box)
        for i, ln in enumerate(b.lines):
            problems += _box_problems(f"{b.id} line {i}", ln.box)
        for c in b.cells:
            if c.box is not None:
                problems += _box_problems(f"{b.id} cell {c.row},{c.col}", c.box)
        if b.kind == "table" and not b.cells:
            problems.append(f"{b.id}: table without cells")
    return problems
