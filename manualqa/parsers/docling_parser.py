"""Docling adapter.

Pages are converted one at a time so OCR can be chosen per page: pages the OCR detector
flags are converted with full-page OCR forced; the others use the PDF text layer only.
Docling reports document items with a bottom-left origin and table cells and text cells
with a top-left origin, so every box is converted according to its own ``coord_origin``.
"""

from __future__ import annotations

import time
from pathlib import Path

from manualqa.blocks import Block, Cell, Kind, Line, PageParse
from manualqa.geometry import Box, render_page
from manualqa.ocr_detect import OcrDecision
from manualqa.parsers.common import assign_lines

KINDS: dict[str, Kind] = {
    "title": "heading",
    "section_header": "heading",
    "table": "table",
    "picture": "figure",
    "chart": "figure",
    "caption": "caption",
    "text": "text",
    "paragraph": "text",
    "list_item": "text",
    "footnote": "text",
    "formula": "text",
    "code": "text",
}


def docling_box_to_norm(bbox, page_width_pt: float, page_height_pt: float) -> Box:
    """A Docling BoundingBox (l, t, r, b, coord_origin) to a page-normalised box."""
    if bbox.coord_origin.value == "BOTTOMLEFT":
        top, bottom = page_height_pt - bbox.t, page_height_pt - bbox.b
    else:
        top, bottom = bbox.t, bbox.b
    x0, x1 = sorted((bbox.l / page_width_pt, bbox.r / page_width_pt))
    y0, y1 = sorted((top / page_height_pt, bottom / page_height_pt))
    return Box(*(min(1.0, max(0.0, v)) for v in (x0, y0, x1, y1)))


class DoclingParser:
    name = "docling"

    def __init__(self) -> None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            OcrMode,
            PdfPipelineOptions,
            RapidOcrOptions,
            TableFormerMode,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        def converter(ocr: bool):
            opts = PdfPipelineOptions(
                do_ocr=ocr, do_table_structure=True, generate_parsed_pages=True
            )
            opts.table_structure_options.mode = TableFormerMode.ACCURATE
            if ocr:  # named, not auto-selected, so runs are reproducible
                opts.ocr_options = RapidOcrOptions(
                    backend="torch", mode=OcrMode.FULL_PAGE
                )
            fmt = PdfFormatOption(pipeline_options=opts)
            return DocumentConverter(format_options={InputFormat.PDF: fmt}), opts

        self._text, _ = converter(False)
        self._ocr, ocr_opts = converter(True)
        self.ocr_engine = f"rapidocr ({ocr_opts.ocr_options.backend})"

    def parse(
        self, pdf: Path, pages: list[int], ocr: dict[int, OcrDecision]
    ) -> list[PageParse]:
        import pymupdf

        pdf = Path(pdf)
        out = []
        with pymupdf.open(pdf) as doc:
            for n in pages:
                start = time.perf_counter()
                decision = ocr.get(n)
                use_ocr = bool(decision and decision.ocr)
                conv = self._ocr if use_ocr else self._text
                result = conv.convert(pdf, page_range=(n, n))
                img, frame = render_page(doc[n - 1])
                blocks = self._blocks(result, pdf.stem, n)
                out.append(
                    PageParse(
                        manual=pdf.name,
                        page=n,
                        parser=self.name,
                        width_px=img.width,
                        height_px=img.height,
                        dpi=frame.dpi,
                        ocr=use_ocr,
                        ocr_reason=decision.reason if decision else None,
                        blocks=blocks,
                        seconds=time.perf_counter() - start,
                    )
                )
        return out

    def _blocks(self, result, stem: str, n: int) -> list[Block]:
        page = result.pages[0]
        w, h = page.size.width, page.size.height
        blocks: list[Block] = []

        def new_id() -> str:
            return f"{stem}:p{n}:b{len(blocks)}"

        for item, _level in result.document.iterate_items():
            if not item.prov:
                continue
            label = getattr(item.label, "value", str(item.label))
            kind = KINDS.get(label, "other")
            box = docling_box_to_norm(item.prov[0].bbox, w, h)
            cells = []
            text = getattr(item, "text", "") or ""
            if kind == "table":
                for c in item.data.table_cells:
                    cells.append(
                        Cell(
                            row=c.start_row_offset_idx,
                            col=c.start_col_offset_idx,
                            text=c.text,
                            box=docling_box_to_norm(c.bbox, w, h) if c.bbox else None,
                            header=bool(c.column_header),
                        )
                    )
                text = "\n".join(c.text for c in cells)
            blocks.append(Block(new_id(), kind, text, box, cells=cells))

        lines = [
            Line(c.text, docling_box_to_norm(c.rect.to_bounding_box(), w, h))
            for c in page.cells
            if c.text.strip()
        ]
        for line in assign_lines(blocks, lines):
            blocks.append(Block(new_id(), "other", line.text, line.box, lines=[line]))
        return blocks
