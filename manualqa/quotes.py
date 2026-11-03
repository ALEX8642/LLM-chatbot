"""Match a claim's quote to its cited evidence and return the highlight boxes.

Text is compared without whitespace, case or extraction noise (ligatures, curly quotes,
soft and end-of-line hyphens, letter spacing, o/0 and l/i/1 OCR confusions), keeping a map
back to the original characters, so a match gives an exact span of the evidence text and
from it the line or cell boxes that cover it.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz
from rapidfuzz.distance import Indel

from manualqa.geometry import Box
from manualqa.retrieve import Evidence, layout_row

QUOTE_MIN = 90
SHORT = 8  # normalised quotes this short must appear exactly
_FOLD = str.maketrans(
    {"o": "0", "l": "1", "i": "1", "‘": "'", "’": "'", "“": '"', "”": '"', "­": ""}
)


@dataclass
class QuoteMatch:
    score: float
    span: tuple[int, int]
    boxes: list[Box]


def _key(text: str) -> tuple[str, list[int]]:
    """Comparison string and, for each of its characters, the source index."""
    out, where = [], []
    for i, ch in enumerate(text):
        if ch == "-" and text[i + 1 : i + 2] == "\n":  # end-of-line hyphenation
            continue
        for c in unicodedata.normalize("NFKC", ch).casefold().translate(_FOLD):
            if c.isspace() or c in "\"'":
                continue
            out.append(c)
            where.append(i)
    return "".join(out), where


def _align(quote: str, text: str) -> tuple[float, int, int] | None:
    if not quote or not text:
        return None
    if len(quote) <= SHORT:
        start = text.find(quote)
        return (100.0, start, start + len(quote)) if start >= 0 else None
    if len(quote) > len(text):
        score = fuzz.ratio(quote, text)
        return (score, 0, len(text)) if score >= QUOTE_MIN else None
    found = fuzz.partial_ratio_alignment(quote, text, score_cutoff=QUOTE_MIN)
    if found is None:
        return None
    # trust the alignment only if the aligned text itself is close to the quote
    if (
        Indel.normalized_similarity(quote, text[found.dest_start : found.dest_end])
        * 100
        < QUOTE_MIN
    ):
        return None
    return found.score, found.dest_start, found.dest_end


def _line_ranges(ev: Evidence) -> list[tuple[int, int, Box]]:
    ranges, pos = [], 0
    for line, box in zip(ev.text.split("\n"), ev.boxes):
        ranges.append((pos, pos + len(line), box))
        pos += len(line) + 1
    return ranges


def match_quote(quote: str, ev: Evidence) -> QuoteMatch | None:
    q, _ = _key(quote)
    t, where = _key(ev.text)
    found = _align(q, t)
    if found is None:
        return None
    score, start, end = found
    span = (where[start], where[end - 1] + 1)
    if ev.kind == "row" and ev.header is not None and ev.cells is not None:
        _, spans = layout_row(ev.header, ev.cells, ev.group)
        boxes = [
            ev.cell_boxes[col]
            for s, e, col in spans
            if s < span[1] and e > span[0] and ev.cell_boxes and ev.cell_boxes[col]
        ]
    else:
        boxes = [b for s, e, b in _line_ranges(ev) if s < span[1] and e > span[0]]
    return QuoteMatch(score=score, span=span, boxes=boxes)
