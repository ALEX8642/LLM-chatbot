"""Page images: 150 dpi for display (highlights are drawn on these), and a downscaled copy
(about 1,000 px on the long edge) for the vision generator. Both are renders of the same
page frame, so page-normalised boxes apply to either."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image

from manualqa.geometry import render_page

DISPLAY_DPI = 150
GEN_LONG_EDGE = 1000


def render_manual(
    pdf: Path, out_dir: Path, pages: list[int] | None = None
) -> dict[int, tuple[Path, Path]]:
    """Write ``out_dir/<stem>/pNNN.jpg`` and ``pNNN-gen.jpg``; existing files are kept."""
    pdf = Path(pdf)
    target = Path(out_dir) / pdf.stem
    target.mkdir(parents=True, exist_ok=True)
    out = {}
    with pymupdf.open(pdf) as doc:
        for n in pages or range(1, len(doc) + 1):
            display, gen = target / f"p{n:03d}.jpg", target / f"p{n:03d}-gen.jpg"
            if not (display.exists() and gen.exists()):
                img, _ = render_page(doc[n - 1], dpi=DISPLAY_DPI)
                img.save(display, quality=85)
                scale = GEN_LONG_EDGE / max(img.size)
                size = (round(img.width * scale), round(img.height * scale))
                img.resize(size, Image.LANCZOS).save(gen, quality=90)
            out[n] = (display, gen)
    return out
