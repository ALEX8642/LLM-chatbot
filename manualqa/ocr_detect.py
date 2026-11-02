"""Decide per page whether the PDF text layer can be trusted or the page must be OCR'd.

Thresholds come from a profile of the three bundled manuals (2026-11-02): normal pages
have a letter-spaced ratio of at most 0.26, except 17 borderline operator-manual pages
between 0.3 and 0.8; 42 operator-manual pages are at 0.8 or above.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

LETTER_SPACED_MIN = 0.5  # share of whitespace-separated tokens that are one character
IMAGE_COVER_MIN = 0.3  # share of the page area covered by raster images
VECTOR_TEXT_DRAWINGS_MIN = 500  # text drawn as vector paths ...
VECTOR_TEXT_CHARS_MAX = 200  # ... with almost no text layer
NO_TEXT_CHARS_MAX = 20


@dataclass(frozen=True)
class OcrDecision:
    ocr: bool
    reason: str | None  # "letter_spaced" | "image_cover" | "vector_text" | "no_text"
    letter_spaced: float
    image_cover: float
    text_chars: int
    drawings: int


def _image_cover(page: pymupdf.Page) -> float:
    area = page.rect.width * page.rect.height
    covered = sum(
        abs(pymupdf.Rect(info["bbox"]) & page.rect) for info in page.get_image_info()
    )
    return min(1.0, covered / area) if area else 0.0


def needs_ocr(page: pymupdf.Page) -> OcrDecision:
    text = page.get_text()
    tokens = text.split()
    letter_spaced = sum(len(t) == 1 for t in tokens) / len(tokens) if tokens else 0.0
    image_cover = _image_cover(page)
    text_chars = len(text.strip())
    drawings = len(page.get_drawings())

    if letter_spaced >= LETTER_SPACED_MIN:
        reason = "letter_spaced"
    elif image_cover >= IMAGE_COVER_MIN:
        reason = "image_cover"
    elif drawings >= VECTOR_TEXT_DRAWINGS_MIN and text_chars <= VECTOR_TEXT_CHARS_MAX:
        reason = "vector_text"
    elif text_chars <= NO_TEXT_CHARS_MAX:
        reason = "no_text"
    else:
        reason = None
    return OcrDecision(
        reason is not None, reason, letter_spaced, image_cover, text_chars, drawings
    )
