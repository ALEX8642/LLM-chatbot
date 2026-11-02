"""PaddleOCR adapter: PaddleOCR-VL for layout, block text and table HTML; PP-OCRv5 for
line boxes; the table-cell detection model for cell boxes.

Every page is OCR'd from a render (the text layer is never read). Pixel boxes are
converted with ``PageFrame.from_px`` using the size of that render.
"""

from __future__ import annotations

import time
from pathlib import Path

from rapidfuzz import fuzz

from manualqa.blocks import Block, Cell, Kind, Line, PageParse
from manualqa.geometry import Box, render_page
from manualqa.ocr_detect import OcrDecision
from manualqa.parsers.common import assign_lines, html_table_cells
from manualqa.textnorm import norm

OCR_DPI = 200
CELL_MATCH_MIN = 85  # fuzz.ratio between a detected cell's OCR text and an HTML cell

KINDS: dict[str, Kind] = {
    "doc_title": "heading",
    "paragraph_title": "heading",
    "table": "table",
    "image": "figure",
    "chart": "figure",
    "header_image": "figure",
    "footer_image": "figure",
    "seal": "figure",
    "figure_title": "caption",
    "vision_footnote": "caption",
    "text": "text",
    "content": "text",
    "abstract": "text",
    "reference": "text",
    "footnote": "text",
    "aside_text": "text",
    "algorithm": "text",
    "formula": "text",
    "display_formula": "text",
}


def _inside(box: Box, x: float, y: float) -> bool:
    return box.x0 <= x <= box.x1 and box.y0 <= y <= box.y1


def match_cell_boxes(cells: list[Cell], boxes: list[Box], lines: list[Line]) -> None:
    """Give each HTML cell the detected cell box whose OCR text matches it best.

    A box's text is the OCR lines whose centres fall inside it. Pairs are assigned
    best score first, each box and cell at most once; equal scores prefer pairs at the
    same position in reading order. Cells without a match keep ``box=None``."""
    box_text = [
        norm(" ".join(ln.text for ln in lines if _inside(b, *ln.box.center)))
        for b in boxes
    ]
    box_rank = {
        i: r
        for r, i in enumerate(
            sorted(range(len(boxes)), key=lambda i: (boxes[i].y0, boxes[i].x0))
        )
    }
    cell_rank = {
        i: r
        for r, i in enumerate(
            sorted(range(len(cells)), key=lambda i: (cells[i].row, cells[i].col))
        )
    }
    pairs = []
    for ci, cell in enumerate(cells):
        text = norm(cell.text)
        if not text:
            continue
        for bi, btext in enumerate(box_text):
            score = fuzz.ratio(text, btext) if btext else 0
            if score >= CELL_MATCH_MIN:
                pairs.append((score, -abs(box_rank[bi] - cell_rank[ci]), ci, bi))
    used_cells, used_boxes = set(), set()
    for _score, _closeness, ci, bi in sorted(pairs, reverse=True):
        if ci in used_cells or bi in used_boxes:
            continue
        cells[ci].box = boxes[bi]
        used_cells.add(ci)
        used_boxes.add(bi)


class PaddleParser:
    name = "paddle"
    ocr_engine = "PP-OCRv5 (paddleocr)"

    def __init__(self) -> None:
        from paddleocr import PaddleOCR, PaddleOCRVL, TableCellsDetection

        self._ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        self._cells = TableCellsDetection()
        # PaddleOCR-VL must be created last: creating any other Paddle model after
        # it makes its predict() hang with the GPU idle (paddleocr 3.7, paddle 3.3.1).
        self._vl = PaddleOCRVL()

    def parse(
        self, pdf: Path, pages: list[int], ocr: dict[int, OcrDecision]
    ) -> list[PageParse]:
        import numpy as np
        import pymupdf

        pdf = Path(pdf)
        out = []
        with pymupdf.open(pdf) as doc:
            for n in pages:
                start = time.perf_counter()
                page = doc[n - 1]
                display, frame = render_page(page)
                img, _ = render_page(page, dpi=OCR_DPI)
                arr = np.array(img)[:, :, ::-1].copy()  # RGB -> BGR

                def to_box(x0, y0, x1, y1) -> Box:
                    return frame.from_px(x0, y0, x1, y1, img.width, img.height)

                blocks = self._blocks(arr, to_box, pdf.stem, n)
                decision = ocr.get(n)
                out.append(
                    PageParse(
                        manual=pdf.name,
                        page=n,
                        parser=self.name,
                        width_px=display.width,
                        height_px=display.height,
                        dpi=frame.dpi,
                        ocr=bool(decision and decision.ocr),
                        ocr_reason=decision.reason if decision else None,
                        blocks=blocks,
                        seconds=time.perf_counter() - start,
                    )
                )
        return out

    def _blocks(self, arr, to_box, stem: str, n: int) -> list[Block]:
        (vl,) = self._vl.predict(arr)
        (ocr,) = self._ocr.predict(arr)
        (det,) = self._cells.predict(arr)
        lines = [
            Line(text, to_box(*box))
            for text, box in zip(
                ocr.json["res"]["rec_texts"], ocr.json["res"]["rec_boxes"]
            )
            if text.strip()
        ]
        cell_boxes = [to_box(*b["coordinate"]) for b in det.json["res"]["boxes"]]

        blocks: list[Block] = []
        for b in vl.json["res"]["parsing_res_list"]:
            kind = KINDS.get(b["block_label"], "other")
            box = to_box(*b["block_bbox"])
            text = b.get("block_content") or ""
            cells: list[Cell] = []
            if kind == "table":
                cells = html_table_cells(text)
                inside = [cb for cb in cell_boxes if _inside(box, *cb.center)]
                match_cell_boxes(cells, inside, lines)
                text = "\n".join(c.text for c in cells)
            blocks.append(
                Block(f"{stem}:p{n}:b{len(blocks)}", kind, text, box, cells=cells)
            )

        for line in assign_lines(blocks, lines):
            blocks.append(
                Block(
                    f"{stem}:p{n}:b{len(blocks)}",
                    "other",
                    line.text,
                    line.box,
                    lines=[line],
                )
            )
        return blocks
