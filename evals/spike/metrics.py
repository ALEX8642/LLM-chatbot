"""Spike metrics: coordinate agreement, OCR character error rate, table-cell checks."""

from __future__ import annotations

import statistics

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from manualqa.blocks import Line, PageParse
from manualqa.textnorm import norm

LINE_MATCH_MIN = 90  # fuzz.ratio for a parser line to count as the same line


def coord_agreement(pp: PageParse, ref: list[Line]) -> float | None:
    """Median IoU between reference lines and the parser lines with the same text."""
    lines = [(norm(ln.text), ln) for b in pp.blocks for ln in b.lines]
    ious = []
    for r in ref:
        target = norm(r.text)
        if not target or not lines:
            continue
        score, best = max(
            ((fuzz.ratio(target, text), ln) for text, ln in lines),
            key=lambda pair: pair[0],
        )
        if score >= LINE_MATCH_MIN:
            ious.append(r.box.iou(best.box))
    return statistics.median(ious) if ious else None


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
