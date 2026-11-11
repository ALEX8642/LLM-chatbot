"""Match a claim's quote to its cited evidence and return the highlight boxes.

Text is compared without whitespace, case or extraction noise (ligatures, curly quotes,
soft and end-of-line hyphens, letter spacing, o/0 and l/i/1 OCR confusions), keeping a map
back to the original characters, so a match gives an exact span of the evidence text and
from it the line or cell boxes that cover it.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left
from dataclasses import dataclass

from rapidfuzz import fuzz
from rapidfuzz.distance import Indel

from manualqa.geometry import Box
from manualqa.retrieve import Evidence, layout_row

QUOTE_MIN = 90
SHORT = 8  # normalised quotes this short must appear exactly
_ELLIPSIS = re.compile(r"\.{3,}|…")
# Words a quote may not skip: without them the sentence means the opposite.
_NEGATION = re.compile(r"\b(?:not|never|no|unless|except|without|cannot)\b|n't", re.I)
_FOLD = str.maketrans(
    {"o": "0", "l": "1", "i": "1", "‘": "'", "’": "'", "“": '"', "”": '"', "­": ""}
)


@dataclass
class QuoteMatch:
    score: float
    span: tuple[int, int]
    boxes: list[Box]
    source: str = (
        ""  # the evidence text matched, which is what a claim is checked against
    )


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
    ranges, pos, boxes = [], 0, iter(ev.boxes)
    for line in ev.text.split("\n"):
        box = next(boxes, None) if line.strip() else None
        if box is not None:
            ranges.append((pos, pos + len(line), box))
        pos += len(line) + 1
    return ranges


def _glued(a: str, b: str) -> bool:
    """Two table cells the parse ran together: "72g|XL Case", "10%)|+9 to +56"."""
    return (a.islower() and b.isupper()) or (a in ")%]" and (b.isalnum() or b in "+-"))


def _whole_words(text: str, start: int, end: int) -> str:
    """The match widened to whole words, so a quote of "30" is checked as the "300" it sits in,
    but not into the next cell where the parse left no space between them."""
    while start > 0 and not text[start - 1].isspace():
        if _glued(text[start - 1], text[start]):
            break
        start -= 1
    while end < len(text) and not text[end].isspace():
        if _glued(text[end - 1], text[end]):
            break
        end += 1
    return text[start:end]


def match_quote(quote: str, ev: Evidence) -> QuoteMatch | None:
    parts = [p for p in _ELLIPSIS.split(quote) if p.strip(" ;,.")]
    if len(parts) <= 1:
        return _match_one(quote, ev)
    # the model skipped text: the fragments must come in order, skipping no negation
    found: list[QuoteMatch] = []
    for part in parts:
        after = found[-1].span[1] if found else 0
        m = _match_one(part.strip(" ;,"), ev, after)
        if m is None or (found and _NEGATION.search(ev.text[after : m.span[0]])):
            return None
        found.append(m)
    return QuoteMatch(
        score=min(m.score for m in found),
        span=(found[0].span[0], found[-1].span[1]),
        boxes=[b for m in found for b in m.boxes],
        source=" ".join(m.source for m in found),
    )


def _match_one(quote: str, ev: Evidence, after: int = 0) -> QuoteMatch | None:
    found = _match_text(quote, ev, ev.text, after)
    if found is None and ev.kind == "row" and ev.cells and len(_key(quote)[0]) > SHORT:
        # a row is shown as "column: value"; a quote can also be its values alone
        layout = layout_row(ev.header or [""] * len(ev.cells), ev.cells, ev.group)[1]
        values = _value_spans(ev)
        text = " ".join(c for c in ev.cells if c.strip())
        found = _match_text(quote, ev, text, _move(after, layout, values))
        if found is not None:  # callers read spans in the row's displayed text
            found.span = (
                _move(found.span[0], values, layout),
                _move(found.span[1], values, layout, end=True),
            )
    return found


def _move(pos: int, frm: list, to: list, end: bool = False) -> int:
    """A position in one rendering of a row, in the other: same cell, same offset."""
    target = {col: (s, e) for s, e, col in to}
    for s, e, col in frm:
        if (s < pos <= e) if end else (s <= pos < e):
            ts, te = target[col]
            return min(ts + (pos - s), te)
        if pos < s:
            return target[col][0]
    return to[-1][1] if to else pos


def _value_spans(ev: Evidence) -> list[tuple[int, int, int]]:
    spans, pos = [], 0
    for col, cell in enumerate(ev.cells or []):
        if cell.strip():
            spans.append((pos, pos + len(cell), col))
            pos += len(cell) + 1
    return spans


def _match_text(quote: str, ev: Evidence, text: str, after: int) -> QuoteMatch | None:
    q, _ = _key(quote)
    t, where = _key(text)
    skip = bisect_left(where, after)
    found = _align(q, t[skip:])
    if found is None:
        return None
    score, start, end = found
    start, end = start + skip, end + skip
    span = (where[start], where[end - 1] + 1)
    if ev.kind == "row" and ev.header is not None and ev.cells is not None:
        if text == ev.text:
            _, spans = layout_row(ev.header, ev.cells, ev.group)
        else:
            spans = _value_spans(ev)
        boxes = [
            ev.cell_boxes[col]
            for s, e, col in spans
            if s < span[1] and e > span[0] and ev.cell_boxes and ev.cell_boxes[col]
        ]
    else:
        boxes = [b for s, e, b in _line_ranges(ev) if s < span[1] and e > span[0]]
    source = _whole_words(text, *span)
    return QuoteMatch(score=score, span=span, boxes=boxes, source=source)
