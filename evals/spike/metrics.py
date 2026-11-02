"""Spike metrics: coordinate agreement, OCR character error rate, table-cell checks."""

from __future__ import annotations

import statistics

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from manualqa.blocks import Line, PageParse
from manualqa.textnorm import norm

LINE_MATCH_MIN = 90  # fuzz.ratio for a parser line to count as the same line


def _centre_distance(a: Line, b: Line) -> float:
    (ax, ay), (bx, by) = a.box.center, b.box.center
    return max(abs(ax - bx), abs(ay - by))


def _matched_pairs(pp: PageParse, ref: list[Line]) -> list[tuple[Line, Line]]:
    """One-to-one (reference line, parser line) pairs with the same text. Among lines
    whose text matches, the nearest centres pair first, so repeated texts (a CAGE
    code on every parts row) pair with their own row, and each line is used once."""
    lines = [(norm(ln.text), ln) for b in pp.blocks for ln in b.lines]
    candidates = []
    for ri, r in enumerate(ref):
        target = norm(r.text)
        if not target:
            continue
        for pi, (text, ln) in enumerate(lines):
            if fuzz.ratio(target, text) >= LINE_MATCH_MIN:
                candidates.append((_centre_distance(r, ln), ri, pi))
    pairs, used_ref, used_parser = [], set(), set()
    for _dist, ri, pi in sorted(candidates):
        if ri in used_ref or pi in used_parser:
            continue
        pairs.append((ref[ri], lines[pi][1]))
        used_ref.add(ri)
        used_parser.add(pi)
    return pairs


def coord_agreement(pp: PageParse, ref: list[Line]) -> float | None:
    """Median IoU between reference lines and the parser lines with the same text.
    Correct boxes can score ~0.65 here: PyMuPDF's line boxes include the font's
    ascent and descent, glyph-tight boxes do not (see ``coord_offset``)."""
    ious = [r.box.iou(p.box) for r, p in _matched_pairs(pp, ref)]
    return statistics.median(ious) if ious else None


def coord_offset(pp: PageParse, ref: list[Line]) -> float | None:
    """Median distance between centres of matched lines (the larger of the x and y
    differences, in page units). Separates misplaced boxes from box conventions."""
    offsets = [
        max(
            abs(r.box.center[0] - p.box.center[0]),
            abs(r.box.center[1] - p.box.center[1]),
        )
        for r, p in _matched_pairs(pp, ref)
    ]
    return statistics.median(offsets) if offsets else None


def _squash(text: str) -> str:
    return "".join(norm(text).split())


def ocr_cer(pp: PageParse, ref_text: str) -> float | None:
    """Character error rate of all block text against the reference, ignoring
    whitespace and case. Reading-order differences count as errors."""
    hyp = _squash(" ".join(b.text for b in pp.blocks))
    ref = _squash(ref_text)
    if not hyp or not ref:
        return None
    return Levenshtein.normalized_distance(hyp, ref)


def cell_checks(pp: PageParse, checks: list[dict]) -> list[dict]:
    """Checks for this page: the value is in one cell (exactly, or contained), and
    ``row_has`` is in another cell of the same table row."""
    results = []
    for chk in checks:
        if (chk["manual"], chk["page"]) != (pp.manual, pp.page):
            continue
        value, row_has = norm(chk["value"]), chk.get("row_has")
        passed = has_box = False
        for b in pp.blocks:
            for c in b.cells:
                text = norm(c.text)
                hit = text == value if chk["match"] == "exact" else value in text
                if not hit:
                    continue
                row_ok = row_has is None or any(
                    o is not c and o.row == c.row and norm(row_has) in norm(o.text)
                    for o in b.cells
                )
                if row_ok:
                    passed, has_box = True, c.box is not None
                    break
            if passed:
                break
        results.append({**chk, "passed": passed, "cell_has_box": has_box})
    return results
