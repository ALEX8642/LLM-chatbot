"""Compose a raw parse into the page the rest of the pipeline uses.

The parser decides the layout (blocks, tables); the text and its boxes come from lines:
the PDF text layer on trusted pages (exact text and boxes) and the parser's OCR lines,
cleaned, on pages the OCR detector flags. Non-table block text is its lines joined by
newlines, so a span of block text maps to line boxes without fuzzy alignment. The
parser's own text is kept in ``alt_text``.

    uv run python -m manualqa.compose RAW.jsonl --manuals manuals --out COMPOSED.jsonl
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pymupdf

from manualqa.blocks import Block, Line, PageParse, dump_pages, load_pages
from manualqa.geometry import render_page
from manualqa.ocr_detect import needs_ocr
from manualqa.parsers.common import assign_lines
from manualqa.parsers.textlayer import text_layer_lines
from manualqa.textclean import clean_ocr_text

TABLE_CELL_SEP = " | "


def _place_cells(block: Block) -> None:
    """Hook for table cell placement (manualqa.table_geometry)."""
    try:
        from manualqa.table_geometry import place_cells
    except ImportError:  # until table geometry exists, cells keep the parser's boxes
        return
    place_cells(block, block.lines)


def compose_page(raw: PageParse, page: pymupdf.Page) -> PageParse:
    decision = needs_ocr(page)
    if decision.ocr:
        source = "ocr"
        lines = [
            Line(clean_ocr_text(ln.text), ln.box) for b in raw.blocks for ln in b.lines
        ]
        lines = [ln for ln in lines if ln.text]
    else:
        source = "text_layer"
        _, frame = render_page(page)
        lines = text_layer_lines(page, frame)

    stem = Path(raw.manual).stem
    blocks = [
        Block(
            id="",
            kind=b.kind,
            text="",
            box=b.box,
            cells=[replace(c, text=clean_ocr_text(c.text)) for c in b.cells],
            alt_text=clean_ocr_text(b.text),
        )
        for b in raw.blocks
    ]
    for line in assign_lines(blocks, lines):
        blocks.append(Block("", "other", "", line.box, lines=[line]))

    for i, b in enumerate(blocks):
        b.id = f"{stem}:p{raw.page}:b{i}"
        if b.kind == "table":
            _place_cells(b)
            rows: dict[int, list] = {}
            for c in sorted(b.cells, key=lambda c: (c.row, c.col)):
                rows.setdefault(c.row, []).append(c.text)
            b.text = "\n".join(TABLE_CELL_SEP.join(r) for r in rows.values())
        else:
            b.text = "\n".join(ln.text for ln in b.lines)

    return replace(
        raw,
        blocks=blocks,
        text_source=source,
        ocr=decision.ocr,
        ocr_reason=decision.reason,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("raw", type=Path)
    ap.add_argument("--manuals", type=Path, default=Path("manuals"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    docs: dict[str, pymupdf.Document] = {}
    out = []
    for raw in load_pages(args.raw):
        if raw.error:
            out.append(raw)
            continue
        doc = docs.setdefault(raw.manual, pymupdf.open(args.manuals / raw.manual))
        out.append(compose_page(raw, doc[raw.page - 1]))
    dump_pages(out, args.out)
    print(f"composed {len(out)} pages -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
