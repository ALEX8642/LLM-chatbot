"""Deterministic fact checks on a claim against its quote and evidence.

1. Every number and identifier in the claim must appear in the quote (numbers compare by
   value: "3,050" = "3050", "0.55" = ".55", "fifteen" = "15"). Two things count as context
   rather than a new fact: anything else in the same table row, and anything the question
   itself mentions that is also on the cited page. A subject the page never mentions still
   fails, so a figure borrowed from another aircraft's example is removed.
2. For a table row: a column name in the claim applies to the facts up to the next column
   name. If those facts sit only in other columns of the row, the claim fails. This catches right row, wrong
   column, e.g. "the part number is 18265" when 18265 is the row's CAGE code (FSCM).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from manualqa.retrieve import Evidence
from manualqa.textnorm import norm

LABEL_MIN = 85
_IDENT = re.compile(
    r"(?<![\w-])(?:[a-z0-9]*\d[a-z0-9]*(?:-[a-z0-9]+)+|[a-z0-9]+-[a-z0-9]*\d[a-z0-9]*"
    r"|(?=[a-z0-9]*[a-z])(?=[a-z0-9]*\d)[a-z0-9]{3,})(?![\w-])"
)
_NUMBER = re.compile(r"(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?![\w])")
_COLUMN_NUMBER = re.compile(r"^\(\d+\)\s*")
_SPACED_HYPHEN = re.compile(r"(?<=\d)\s+-\s+(?=\d)")
_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty"
).split()
_NUMBER_WORDS = {w: float(i) for i, w in enumerate(_WORDS)}
_NUMBER_WORDS.update({"thirty": 30.0, "forty": 40.0, "fifty": 50.0, "sixty": 60.0})
_WORD = re.compile(r"[a-z]+")


@dataclass
class FactResult:
    ok: bool
    reason: str | None = None


def _facts(text: str) -> list[tuple[int, str, str]]:
    """(position, kind, value) for identifiers and numbers, in order."""
    found, taken = [], []
    for m in _IDENT.finditer(text):
        found.append((m.start(), "id", m.group(0)))
        taken.append((m.start(), m.end()))
    for m in _NUMBER.finditer(text):
        if not any(ch.isdigit() for ch in m.group(0)):
            continue
        if any(s <= m.start() < e for s, e in taken):
            continue
        found.append((m.start(), "num", m.group(0)))
    return sorted(found)


def _numbers(text: str) -> set[float]:
    out = set()
    for m in _NUMBER.finditer(text):
        if any(ch.isdigit() for ch in m.group(0)):
            out.add(float(m.group(0).replace(",", "")))
    out.update(_NUMBER_WORDS[w] for w in _WORD.findall(text) if w in _NUMBER_WORDS)
    return out


def _identifiers(text: str) -> set[str]:
    return {m.group(0) for m in _IDENT.finditer(text)}


def _contains(text: str, kind: str, value: str) -> bool:
    text = _SPACED_HYPHEN.sub("-", norm(text))
    if kind == "num":
        return float(value.replace(",", "")) in _numbers(text)
    return value in _identifiers(text) or value in text


def check_facts(
    claim: str, quote: str, ev: Evidence, question: str = "", page_text: str = ""
) -> FactResult:
    claim_n = norm(claim)
    facts = _facts(claim_n)
    row_context = [*(ev.cells or []), ev.group or ""] if ev.kind == "row" else []
    for _, kind, value in facts:
        if _contains(quote, kind, value):
            continue
        if any(_contains(cell, kind, value) for cell in row_context):
            continue
        if _contains(question, kind, value) and _contains(page_text, kind, value):
            continue
        return FactResult(False, f"{value} not in quote")
    if ev.kind != "row" or not ev.header or not ev.cells:
        return FactResult(True)

    labels = []
    for col, label in enumerate(ev.header):
        core = norm(_COLUMN_NUMBER.sub("", label))
        if len(core) < 3:
            continue
        found = fuzz.partial_ratio_alignment(core, claim_n, score_cutoff=LABEL_MIN)
        if found is not None:
            labels.append((found.dest_end, col))
    labels.sort()
    for i, (end, col) in enumerate(labels):
        stop = labels[i + 1][0] if i + 1 < len(labels) else len(claim_n)
        held = []  # (fact value, the columns of this row that hold it)
        for pos, kind, value in facts:
            if end <= pos < stop:
                cols = [
                    c for c, cell in enumerate(ev.cells) if _contains(cell, kind, value)
                ]
                if cols:
                    held.append((value, cols))
        if held and not any(col in cols for _, cols in held):
            value, cols = held[0]
            return FactResult(
                False,
                f"value {value} in column {ev.header[cols[0]]}, "
                f"claim names {ev.header[col]}",
            )
    return FactResult(True)
