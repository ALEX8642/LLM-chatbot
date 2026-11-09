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

from evals.spike.metrics import cell_checks, coord_agreement, coord_offset, ocr_cer
from manualqa.blocks import (
    PageParse,
    append_page,
    dump_pages,
    load_pages,
    validate,
)
from manualqa.geometry import render_page
from manualqa.ocr_detect import needs_ocr
from manualqa.overlay import draw_overlay
from manualqa.parsers import get_parser

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGES = [
    "pymupdf",
    "docling",
    "docling-core",
    "rapidocr",
    "torch",
    "paddleocr",
    "paddlepaddle-gpu",
]


def _versions() -> dict[str, str]:
    found = {}
    for name in PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    return found


def _safe_error(e: Exception) -> str:
    """Exception type and message with local paths replaced (results are public)."""
    text = f"{type(e).__name__}: {e}"
    for path, label in ((str(ROOT), "<repo>"), (str(Path.home()), "~")):
        text = text.replace(path, label)
    return text


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
            error=_safe_error(e),
        )


def _page_list(pages: Path, manuals: Path) -> dict[str, list[int]]:
    if str(pages) != "all":
        return json.loads(pages.read_text())
    import pymupdf

    out = {}
    for pdf in sorted(manuals.glob("*.pdf")):
        with pymupdf.open(pdf) as doc:
            out[pdf.name] = list(range(1, doc.page_count + 1))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parser", required=True)
    ap.add_argument(
        "--pages",
        type=Path,
        default=HERE / "pages.json",
        help='JSON {manual: [pages]}, or "all" for every page of every manual',
    )
    ap.add_argument("--expectations", type=Path, default=HERE / "expectations.json")
    ap.add_argument("--manuals", type=Path, default=ROOT / "manuals")
    ap.add_argument("--out", type=Path, default=ROOT / "spike-out")
    ap.add_argument("--docs", type=Path, default=ROOT / "docs" / "spike")
    ap.add_argument(
        "--parses",
        type=Path,
        help="re-score saved parses (parses.jsonl) instead of running the parser",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="keep pages already in <out>/<parser>/parses.jsonl and parse the rest",
    )
    args = ap.parse_args(argv)

    saved = (
        {(pp.manual, pp.page): pp for pp in load_pages(args.parses)}
        if args.parses
        else None
    )
    parser = None if saved is not None else get_parser(args.parser)
    name = args.parser if parser is None else parser.name
    reference = get_parser("textlayer")
    expectations = (
        json.loads(args.expectations.read_text()) if args.expectations.exists() else []
    )
    docs = args.docs / name
    docs.mkdir(parents=True, exist_ok=True)
    previous = docs / "metrics.json"
    previous = json.loads(previous.read_text()) if previous.exists() else {}
    out_file = args.out / name / "parses.jsonl"
    done = {}
    if saved is None:  # parsing: every page is saved as soon as it is parsed
        if args.resume and out_file.exists():
            done = {(pp.manual, pp.page): pp for pp in load_pages(out_file)}
        else:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text("")

    parses, page_metrics, checks = [], [], []
    for manual, pages in _page_list(args.pages, args.manuals).items():
        pdf = args.manuals / manual
        with pymupdf.open(pdf) as doc:
            for n in pages:
                page = doc[n - 1]
                decision = needs_ocr(page)
                if saved is not None:
                    pp = saved[(manual, n)]
                elif (manual, n) in done:
                    pp = done[(manual, n)]
                else:
                    pp = _parse_one(parser, pdf, n, decision, page)
                    append_page(pp, out_file)
                parses.append(pp)
                status = pp.error or f"{len(pp.blocks)} blocks"
                print(f"{pdf.stem} p{n}: {pp.seconds:.1f}s, {status}", flush=True)

                img, _ = render_page(page)
                draw_overlay(img, pp).save(
                    docs / f"{pdf.stem}-p{n:03d}.jpg", quality=70
                )

                agreement = offset = cer = None
                if not decision.ocr:
                    (ref,) = reference.parse(pdf, [n], {n: decision})
                    ref_lines = [ln for b in ref.blocks for ln in b.lines]
                    agreement = coord_agreement(pp, ref_lines)
                    offset = coord_offset(pp, ref_lines)
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
                        "coord_offset": offset,
                        "cer": cer,
                    }
                )
                checks += cell_checks(pp, expectations)

    if saved is not None:
        dump_pages(parses, out_file)
    metrics = {
        "parser": name,
        # re-scoring keeps the versions and engine of the run that parsed
        "versions": previous.get("versions", {}) if saved is not None else _versions(),
        "ocr_engine": (
            previous.get("ocr_engine")
            if saved is not None
            else getattr(parser, "ocr_engine", None)
        ),
        "pages": page_metrics,
        "cell_checks": checks,
    }
    (docs / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    errors = sum(p["error"] is not None for p in page_metrics)
    print(f"{name}: {len(page_metrics)} pages, {errors} errors -> {docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
