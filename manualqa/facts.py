"""Deterministic fact checks on a claim against its quote and evidence.

1. Every number and identifier in the claim must appear in the quote (numbers compare by
   value: "3,050" = "3050", "0.55" = ".55").
2. For a table row: a column name in the claim applies to the first fact after it. If that
   fact sits in another column of the row, the claim fails. This catches right row, wrong
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
    return out


def _identifiers(text: str) -> set[str]:
    return {m.group(0) for m in _IDENT.finditer(text)}


def _contains(text: str, kind: str, value: str) -> bool:
    text = norm(text)
    if kind == "num":
        return float(value.replace(",", "")) in _numbers(text)
    return value in _identifiers(text) or value in text


def check_facts(claim: str, quote: str, ev: Evidence) -> FactResult:
    claim_n = norm(claim)
    facts = _facts(claim_n)
    for _, kind, value in facts:
        if not _contains(quote, kind, value):
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
    for end, col in labels:
        after = [f for f in facts if f[0] >= end]
        if not after:
            continue
        _, kind, value = after[0]
        holders = [c for c, cell in enumerate(ev.cells) if _contains(cell, kind, value)]
        if holders and col not in holders:
            return FactResult(
                False,
                f"value {value} in column {ev.header[holders[0]]}, "
                f"claim names {ev.header[col]}",
            )
    return FactResult(True)
