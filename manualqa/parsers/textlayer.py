"""Reference parser: the PDF's own text layer, no OCR. Not a candidate; it is what the
candidates' coordinates and OCR are compared against."""

from __future__ import annotations

import time
from pathlib import Path

import pymupdf

from manualqa.blocks import Block, Line, PageParse
from manualqa.geometry import render_page
from manualqa.ocr_detect import OcrDecision


class TextLayerParser:
    name = "textlayer"

    def parse(
        self, pdf: Path, pages: list[int], ocr: dict[int, OcrDecision]
    ) -> list[PageParse]:
        pdf = Path(pdf)
        out = []
        with pymupdf.open(pdf) as doc:
            for n in pages:
                start = time.perf_counter()
                page = doc[n - 1]
                img, frame = render_page(page)
                blocks = []
                for b in page.get_text("dict")["blocks"]:
                    if b["type"] != 0:  # 0 = text, 1 = image
                        continue
                    lines = [
                        Line(
                            "".join(s["text"] for s in ln["spans"]),
                            frame.from_pdf_topleft(*ln["bbox"]),
                        )
                        for ln in b["lines"]
                    ]
                    lines = [ln for ln in lines if ln.text.strip()]
                    if not lines:
                        continue
                    blocks.append(
                        Block(
                            id=f"{pdf.stem}:p{n}:b{len(blocks)}",
                            kind="text",
                            text="\n".join(ln.text for ln in lines),
                            box=frame.from_pdf_topleft(*b["bbox"]),
                            lines=lines,
                        )
                    )
                decision = ocr.get(n)
                out.append(
                    PageParse(
                        manual=pdf.name,
                        page=n,
                        parser=self.name,
                        width_px=img.width,
                        height_px=img.height,
                        dpi=frame.dpi,
                        ocr=bool(decision and decision.ocr),
                        ocr_reason=decision.reason if decision else None,
                        blocks=blocks,
                        seconds=time.perf_counter() - start,
                    )
                )
        return out
