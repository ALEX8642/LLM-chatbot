"""Structure-aware chunks for retrieval.

Blocks are read in order across a manual's pages. A heading starts a text chunk; text
blocks accumulate under it up to ``MAX_CHARS`` (a continuation repeats the heading line).
Each table is its own chunk, split every ``TABLE_ROWS_PER_CHUNK`` rows with the header
repeated. A figure becomes a chunk only when it has text (labels, data plates), with its
caption. Running headers, footers and page numbers (short ``other`` blocks in the top 12%
or bottom 15% of the page) are skipped.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from manualqa.blocks import Block, PageParse
from manualqa.tables import derive_table

MAX_CHARS = 1500
TABLE_ROWS_PER_CHUNK = 25
TOP_MARGIN, BOTTOM_MARGIN = (
    0.12,
    0.15,
)  # where running headers, footers, page numbers sit
RUNNING_MAX_CHARS = 60
CAPTION_GAP = 0.05  # a caption this close to a figure or table belongs to it

ChunkKind = Literal["text", "table", "figure"]


@dataclass
class Chunk:
    id: str
    manual: str
    pages: list[int]
    kind: ChunkKind
    heading: str
    text: str
    block_ids: list[str] = field(default_factory=list)


def _in_margin(b: Block) -> bool:
    """A short unlabelled block at the top or bottom of the page: a running header,
    footer or page number."""
    return (
        b.kind == "other"
        and len(b.text) <= RUNNING_MAX_CHARS
        and (b.box.y1 <= TOP_MARGIN or b.box.y0 >= 1 - BOTTOM_MARGIN)
    )


def _near(a: Block, b: Block) -> bool:
    gap = max(a.box.y0 - b.box.y1, b.box.y0 - a.box.y1)
    return gap < CAPTION_GAP


def _row_text(cells: list[str]) -> str:
    return " | ".join(c.strip() for c in cells if c.strip())


def _table_chunks(block: Block, caption: Block | None) -> list[list[str]]:
    info = derive_table(block)
    rows: dict[int, dict[int, str]] = {}
    for c in block.cells:
        rows.setdefault(c.row, {})[c.col] = c.text
    width = len(info.header)
    body = [
        _row_text([rows[r].get(col, "") for col in range(width)])
        for r in sorted(rows)[info.header_rows :]
    ]
    body = [line for line in body if line]
    head = ([caption.text] if caption else []) + [_row_text(info.header)]
    parts = [
        body[i : i + TABLE_ROWS_PER_CHUNK]
        for i in range(0, len(body), TABLE_ROWS_PER_CHUNK)
    ] or [[]]
    return [head + part for part in parts]


def chunk_manual(pages: list[PageParse]) -> list[Chunk]:
    if not pages:
        return []
    manual = pages[0].manual
    stem = Path(manual).stem
    chunks: list[Chunk] = []
    heading = ""
    current: dict | None = None

    def add(kind: ChunkKind, text: str, ids: list[str], page_nos: set[int]) -> None:
        chunks.append(
            Chunk(
                f"{stem}:c{len(chunks)}",
                manual,
                sorted(page_nos),
                kind,
                heading,
                text,
                ids,
            )
        )

    def flush() -> None:
        nonlocal current
        if current and current["lines"] and current["has_body"]:
            add("text", "\n".join(current["lines"]), current["ids"], current["pages"])
        current = None

    def start(first_ids: list[str], page_no: int) -> None:
        nonlocal current
        current = {
            "lines": [heading] if heading else [],
            "ids": list(first_ids),
            "pages": {page_no},
            "has_body": False,
        }

    for pp in pages:
        blocks = [b for b in pp.blocks if not _in_margin(b)]
        captions = [b for b in blocks if b.kind == "caption"]
        used: set[str] = set()
        for b in blocks:
            if b.kind in ("table", "figure"):
                cap = next(
                    (c for c in captions if c.id not in used and _near(b, c)), None
                )
                if b.kind == "table" and b.cells:
                    if cap:
                        used.add(cap.id)
                    ids = [b.id] + ([cap.id] if cap else [])
                    for lines in _table_chunks(b, cap):
                        add("table", "\n".join(lines), ids, {pp.page})
                elif b.kind == "figure" and b.text.strip():
                    if cap:
                        used.add(cap.id)
                    text = b.text + (f"\n{cap.text}" if cap else "")
                    add("figure", text, [b.id] + ([cap.id] if cap else []), {pp.page})
        for b in blocks:
            if b.kind in ("table", "figure") or b.id in used or not b.text.strip():
                continue
            if b.kind == "heading":
                flush()
                heading = " ".join(b.text.split())
                start([b.id], pp.page)
                continue
            if current is None:
                start([], pp.page)
            joined = len("\n".join(current["lines"])) + 1 + len(b.text)
            if current["has_body"] and joined > MAX_CHARS:
                flush()
                start([], pp.page)
            current["lines"].append(b.text)
            current["ids"].append(b.id)
            current["pages"].add(pp.page)
            current["has_body"] = True
    flush()
    return chunks


def dump_chunks(chunks: list[Chunk], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")


def load_chunks(path: Path) -> list[Chunk]:
    with Path(path).open(encoding="utf-8") as f:
        return [Chunk(**json.loads(line)) for line in f if line.strip()]
