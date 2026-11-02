"""Run one parser over the spike pages: parses, overlays and metrics.

    uv run python -m evals.spike.run_spike --parser docling

Writes spike-out/<parser>/parses.jsonl (not committed), and
docs/spike/<parser>/<stem>-pNNN.jpg plus docs/spike/<parser>/metrics.json.
"""

from __future__ import annotations

import argparse
import json
import time
from importlib import metadata
from pathlib import Path

import pymupdf

from evals.spike.metrics import cell_checks, coord_agreement, ocr_cer
from manualqa.blocks import PageParse, dump_pages, validate
from manualqa.geometry import render_page
from manualqa.ocr_detect import needs_ocr
from manualqa.overlay import draw_overlay
from manualqa.parsers import get_parser

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGES = ["pymupdf", "docling", "docling-core", "paddleocr", "paddlepaddle-gpu"]


def _versions() -> dict[str, str]:
    found = {}
    for name in PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    return found


def _parse_one(parser, pdf: Path, n: int, decision, page) -> PageParse:
    start = time.perf_counter()
    try:
        (pp,) = parser.parse(pdf, [n], {n: decision})
        return pp
    except Exception as e:  # one page's failure must not lose the others
        img, frame = render_page(page)
        return PageParse(
            manual=pdf.name,
            page=n,
            parser=parser.name,
            width_px=img.width,
            height_px=img.height,
            dpi=frame.dpi,
            ocr=decision.ocr,
            ocr_reason=decision.reason,
            blocks=[],
            seconds=time.perf_counter() - start,
            error=f"{type(e).__name__}: {e}",
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parser", required=True)
    ap.add_argument("--pages", type=Path, default=HERE / "pages.json")
    ap.add_argument("--expectations", type=Path, default=HERE / "expectations.json")
    ap.add_argument("--manuals", type=Path, default=ROOT / "manuals")
    ap.add_argument("--out", type=Path, default=ROOT / "spike-out")
    ap.add_argument("--docs", type=Path, default=ROOT / "docs" / "spike")
    args = ap.parse_args(argv)

    parser = get_parser(args.parser)
    reference = get_parser("textlayer")
    expectations = (
        json.loads(args.expectations.read_text()) if args.expectations.exists() else []
    )
    docs = args.docs / parser.name
    docs.mkdir(parents=True, exist_ok=True)

    parses, page_metrics, checks = [], [], []
    for manual, pages in json.loads(args.pages.read_text()).items():
        pdf = args.manuals / manual
        with pymupdf.open(pdf) as doc:
            for n in pages:
                page = doc[n - 1]
                decision = needs_ocr(page)
                pp = _parse_one(parser, pdf, n, decision, page)
                parses.append(pp)

                img, _ = render_page(page)
                draw_overlay(img, pp).save(
                    docs / f"{pdf.stem}-p{n:03d}.jpg", quality=70
                )

                agreement = cer = None
                if not decision.ocr:
                    (ref,) = reference.parse(pdf, [n], {n: decision})
                    agreement = coord_agreement(
                        pp, [ln for b in ref.blocks for ln in b.lines]
                    )
                elif decision.reason == "letter_spaced":
                    cer = ocr_cer(pp, page.get_text())

                cells = [c for b in pp.blocks for c in b.cells]
                page_metrics.append(
                    {
                        "manual": manual,
                        "page": n,
                        "ocr": pp.ocr,
                        "ocr_reason": pp.ocr_reason,
                        "seconds": round(pp.seconds, 3),
                        "error": pp.error,
                        "blocks": len(pp.blocks),
                        "lines": sum(len(b.lines) for b in pp.blocks),
                        "cells": len(cells),
                        "cells_with_boxes": sum(c.box is not None for c in cells),
                        "problems": validate(pp),
                        "coord_agreement": agreement,
                        "cer": cer,
                    }
                )
                checks += cell_checks(pp, expectations)

    dump_pages(parses, args.out / parser.name / "parses.jsonl")
    metrics = {
        "parser": parser.name,
        "versions": _versions(),
        "pages": page_metrics,
        "cell_checks": checks,
    }
    (docs / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    errors = sum(p["error"] is not None for p in page_metrics)
    print(f"{parser.name}: {len(page_metrics)} pages, {errors} errors -> {docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
