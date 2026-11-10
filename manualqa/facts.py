"""Deterministic fact checks on a claim against the source text its quote matched.

1. Every number and identifier in the claim must appear in that source text (numbers compare
   by value: "3,050" = "3050", "0.55" = ".55", "fifteen" = "15"). Two things count as context
   rather than a new fact: anything else in the same table row, a name in the headings the
   page sits under, and anything the question
   itself mentions that is also on the cited page. A subject the page never mentions still
   fails, so a figure borrowed from another aircraft's example is removed.
2. The same number must not have another unit or the opposite sign: "172 psi" fails on
   "172 kPa", and "-15" on "+15". A number printed with no unit takes the claim's.
3. For a table row: a column name in the claim applies to the facts nearest it. If those
   facts sit only in other columns of the row, the claim fails. This catches right row, wrong
   column, e.g. "the part number is 18265" when 18265 is the row's CAGE code (FSCM).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
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
_SPACED_HYPHEN = re.compile(r"(?<=\d)\s*-\s+(?=\d)")
_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty"
).split()
_NUMBER_WORDS = {w: float(i) for i, w in enumerate(_WORDS)}
_TENS = {"twenty": 20.0, "thirty": 30.0, "forty": 40.0, "fifty": 50.0, "sixty": 60.0}
_TENS.update({"seventy": 70.0, "eighty": 80.0, "ninety": 90.0})
_NUMBER_WORDS.update(_TENS)
_WORD = re.compile(r"[a-z]+(?:-[a-z]+)?")
_NOT_FACTS = {"zero", "one"}  # "one of the steps" is rarely a figure
_OCR_ZERO = re.compile(r"(?<=\d)o(?![a-z])|(?<![a-z0-9])o(?=\d)")
_UNITS = {
    "psi": ("psi",),
    "kpa": ("kpa", "kilopascal", "kilopascals"),
    "v": ("v", "volt", "volts", "vac", "vdc"),
    "a": ("a", "amp", "amps", "ampere", "amperes"),
    "hz": ("hz", "hertz"),
    "kw": ("kw", "kilowatt", "kilowatts"),
    "w": ("w", "watt", "watts"),
    "lb": ("lb", "lbs", "pound", "pounds"),
    "kg": ("kg", "kilogram", "kilograms"),
    "in": ("in", "inch", "inches"),
    "cm": ("cm", "centimeter", "centimeters"),
    "mm": ("mm", "millimeter", "millimeters"),
    "ft": ("ft", "foot", "feet"),
    "gal": ("gal", "gallon", "gallons"),
    "l": ("l", "liter", "liters", "litre", "litres"),
    "qt": ("qt", "quart", "quarts"),
    "rpm": ("rpm",),
    "s": ("s", "sec", "second", "seconds"),
    "min": ("min", "minute", "minutes"),
    "hr": ("hr", "hrs", "hour", "hours"),
}
_UNIT = {name: unit for unit, names in _UNITS.items() for name in names}
_JOINED_UNIT = re.compile(
    r"(?<![a-z0-9-])(\d[\d,.]*)-?("
    + "|".join(sorted(({n for n in _UNIT if len(n) > 1} | {"v", "degree", "degrees"})))
    + r")\b"
)
# OCR ran a measure into the next word: "800lblg". A code such as "2104c" is not a number.
_NUMBER_ON_WORD = re.compile(
    r"(?<![\w.,])(\d[\d,]*(?:\.\d+)?)(?="
    + "|".join(sorted(n for n in _UNIT if len(n) > 1))
    + r")[a-z]+\b"
)
_AFTER_NUMBER = re.compile(r"\s*([a-z]+)")
_MINUS_WORD = re.compile(r"(?:minus|negative)\s+$")
# How a table's column heading can be written in a claim, beyond the heading itself.
_LABEL_NAMES = {
    "qty": ("quantity", "qty"),
    "fscm": ("fscm", "cage"),
    "part number": ("part number", "part no", "p/n", "part #"),
}


@dataclass
class FactResult:
    ok: bool
    reason: str | None = None


def _word_value(word: str) -> float | None:
    if word in _NUMBER_WORDS:
        return _NUMBER_WORDS[word]
    tens, _, ones = word.partition("-")
    if tens in _TENS and _NUMBER_WORDS.get(ones, 10) < 10:
        return _TENS[tens] + _NUMBER_WORDS[ones]
    return None


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
    for m in _WORD.finditer(text):
        value = _word_value(m.group(0))
        if value is not None and m.group(0) not in _NOT_FACTS:
            found.append((m.start(), "num", f"{value:g}"))
    return sorted(found)


_SPACED_RUN = re.compile(r"(?<!\S)(?:\S )+\S(?!\S)")
_SPACED_LETTERS = re.compile(r"(?<!\S)[a-z](?: [a-z]){2,}(?!\S)")


def _despace(text: str) -> str:
    """Join letter-spaced OCR ("r a d i a t o r", "2 5") back into words, only on lines
    that are visibly letter-spaced, so a row of separate digits ("1 2") stays apart."""
    lines = []
    for line in text.split("\n"):
        if _SPACED_LETTERS.search(line):
            line = _SPACED_RUN.sub(lambda m: m.group(0).replace(" ", ""), line)
        lines.append(line)
    return "\n".join(lines)


def _clean(text: str) -> str:
    text = _despace(unicodedata.normalize("NFKC", text).casefold())
    text = _OCR_ZERO.sub("0", _SPACED_HYPHEN.sub("-", norm(text)))
    return _JOINED_UNIT.sub(r"\1 \2", text)


def _occurrences(text: str) -> list[tuple[float, int, int]]:
    """(value, start, end) of each number and number word."""
    out = []
    for m in _NUMBER.finditer(text):
        if any(ch.isdigit() for ch in m.group(0)):
            out.append((float(m.group(0).replace(",", "")), m.start(), m.end()))
    for m in _NUMBER_ON_WORD.finditer(text):
        out.append((float(m.group(1).replace(",", "")), m.start(), m.end()))
    for m in _WORD.finditer(text):
        value = _word_value(m.group(0))
        if value is not None:
            out.append((value, m.start(), m.end()))
    return out


def _numbers(text: str) -> set[float]:
    return {value for value, _, _ in _occurrences(text)}


def _identifiers(text: str) -> set[str]:
    return {m.group(0) for m in _IDENT.finditer(text)}


def _contains(text: str, kind: str, value: str) -> bool:
    text = _clean(text)
    if kind == "num":
        return float(value.replace(",", "")) in _numbers(text)
    if value in _identifiers(text):
        return True
    # a whole token only: "p14-89" must not pass on "p14-8969"
    return re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", text) is not None


_COMMON_WORDS = {"in", "a"}  # also English words: "15 in accordance", "1 a minute"


def _unit_at(text: str, end: int) -> str | None:
    m = _AFTER_NUMBER.match(text, end)
    if not m:
        return None
    if m.group(1) in _COMMON_WORDS and re.match(r"\s*[a-z]", text[m.end() :]):
        return None
    return _UNIT.get(m.group(1))


def _sign_at(text: str, start: int) -> str | None:
    before = text[:start]
    if _MINUS_WORD.search(before):
        return "-"
    sign = before[-1:]
    # after a digit or letter it is a range or an identifier, not a sign
    if sign in ("-", "+", "−") and not before[-2:-1].strip(" (:"):
        return "-" if sign != "+" else "+"
    return None


def _conflict(claim: str, start: int, end: int, value: float, sources) -> str | None:
    """Why this number in the claim cannot be the source's, if it says another unit or sign."""
    here = [
        (text, s, e) for text in sources for v, s, e in _occurrences(text) if v == value
    ]
    unit = _unit_at(claim, end)
    if unit and here:
        units = {_unit_at(text, e) for text, _, e in here}
        if None not in units and unit not in units:
            return f"{claim[start:end]} {unit}: source has {sorted(units)[0]}"
    sign = _sign_at(claim, start)
    if sign and here:
        signs = {_sign_at(text, s) for text, s, _ in here}
        if None not in signs and sign not in signs:
            return f"{sign}{claim[start:end]}: source has the opposite sign"
    return None


def _label_spans(claim: str, header: list[str]) -> list[tuple[int, int, int]]:
    """(start, end, column) of each column heading the claim mentions."""
    out = []
    for col, label in enumerate(header):
        core = norm(_COLUMN_NUMBER.sub("", label))
        if len(core) < 3:
            continue
        names = next((n for k, n in _LABEL_NAMES.items() if k in core), (core,))
        for name in names:
            found = fuzz.partial_ratio_alignment(name, claim, score_cutoff=LABEL_MIN)
            if found is not None:
                out.append((found.dest_start, found.dest_end, col))
                break
    return sorted(out)


# Words that decide what a sentence permits, requires or forbids. A quote is matched with some
# tolerance for extraction noise, but these, and its numbers, must be as printed.
_DECIDING = {
    "may", "might", "must", "shall", "should", "can", "could", "will", "would", "need",
    "required", "not", "never", "no", "unless", "except", "without", "only", "minimum",
    "maximum", "more", "less", "fewer", "above", "below", "exceed", "exceeds",
}  # fmt: skip
_WORDING_TOKEN = re.compile(r"\d+(?:[.,/]\d+)*|[a-z]+")
_NEGATED = re.compile(r"\b(?:not|never|cannot)\b|n['’]t\b", re.I)
_SENTENCE_END = re.compile(r"[.!?:;\n]")
_LIST_MARKER = re.compile(r"^\s*\(?\d+[.)]\s+")  # "7. Engine knocks": the list's number


def _wording(text: str) -> Counter:
    text = re.sub(r"n['’]t\b", " not", text, flags=re.I)
    text = re.sub(r"\bcannot\b", "can not", text, flags=re.I)
    return Counter(
        t
        for t in _WORDING_TOKEN.findall(_clean(text))
        if t in _DECIDING or t[0].isdigit()
    )


def check_wording(quote: str, source: str, before: str = "") -> FactResult:
    """The quote keeps the source's numbers and deciding words, and does not start just after
    a negation it leaves out ("Do not | crank the engine for more than 30 seconds")."""
    q, s = _wording(_LIST_MARKER.sub("", quote)), _wording(_LIST_MARKER.sub("", source))
    changed = sorted((q - s) + (s - q))
    if changed:
        return FactResult(False, f"the quote changes the source's {', '.join(changed)}")
    sentence = _SENTENCE_END.split(before)[-1]
    if _NEGATED.search(" ".join(sentence.split()[-3:])) and not q["not"] + q["never"]:
        return FactResult(False, "the quote leaves out a negation just before it")
    return FactResult(True)


def check_facts(
    claim: str, source: str, ev: Evidence, question: str = "", page_text: str = ""
) -> FactResult:
    claim_n = _clean(claim)
    facts = _facts(claim_n)
    row_context = [*ev.cells, ev.group or ""] if ev.kind == "row" and ev.cells else []
    # names a heading can lend a claim; a bare number there ("Table 3-1") is no evidence
    titles = [*(ev.header or []), ev.under] if ev.under or ev.header else []
    for _, kind, value in facts:
        if _contains(source, kind, value):
            continue
        if any(_contains(cell, kind, value) for cell in row_context):
            continue
        if kind == "id" and any(_contains(t, kind, value) for t in titles):
            continue
        if _contains(question, kind, value) and _contains(page_text, kind, value):
            continue
        return FactResult(False, f"{value} not in source")
    sources = [_clean(t) for t in (source, *row_context)]
    for value, start, end in _occurrences(claim_n):
        reason = _conflict(claim_n, start, end, value, sources)
        if reason:
            return FactResult(False, reason)
    if ev.kind != "row" or not ev.header or not ev.cells:
        return FactResult(True)

    labels = _label_spans(claim_n, ev.header)
    if not labels:
        return FactResult(True)
    held: dict[int, list[tuple[str, list[int]]]] = {}  # label index -> facts nearest it
    for pos, kind, value in facts:
        if any(s <= pos < e for s, e, _ in labels):
            continue
        cols = [c for c, cell in enumerate(ev.cells) if _contains(cell, kind, value)]
        if cols:
            nearest = min(
                range(len(labels)),
                key=lambda i: min(abs(pos - labels[i][0]), abs(pos - labels[i][1])),
            )
            held.setdefault(nearest, []).append((value, cols))
    for i, facts_here in held.items():
        col = labels[i][2]
        if not any(col in cols for _, cols in facts_here):
            value, cols = facts_here[0]
            return FactResult(
                False,
                f"value {value} in column {ev.header[cols[0]]}, "
                f"claim names {ev.header[col]}",
            )
    return FactResult(True)
