"""Grades answers: exact match for short answers, a key-fact checklist otherwise, and whether
the judge finds the key facts in the cited source (the primary endpoint needs both)."""

from __future__ import annotations

import random
import re
import unicodedata

from evals.items import Item
from evals.prompts import ABSTAINED, KEY_FACTS, SOURCE_SUPPORT

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
_UNITS = {"lbs": "lb", "pound": "lb", "pounds": "lb"}
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_DECIMAL = re.compile(r"^\d*\.\d+$")
BOOTSTRAP = 1000


def normalise(text: str) -> str:
    """Case, dashes, plus-minus, thousands separators, units, and numbers like 3.80."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES).casefold()
    text = text.replace("+/-", " ± ").replace("±", " ± ")
    text = _THOUSANDS.sub("", text)
    tokens = []
    for raw in text.split():
        token = raw.strip(".,;:()[]\"'")
        if _DECIMAL.match(token):
            token = token.rstrip("0").rstrip(".")
        if token:
            tokens.append(_UNITS.get(token, token))
    return " ".join(tokens)


def _tokens(text: str) -> list[str]:
    return normalise(text).replace("-", " ").split()


def exact_match(answer: str, exact: str) -> bool:
    """The normalised value occurs in the answer as a whole token sequence."""
    a, e = _tokens(answer), _tokens(exact)
    return any(a[i : i + len(e)] == e for i in range(len(a) - len(e) + 1))


def cited_source(out: dict, manual: str, blocks: dict, pages: dict) -> str:
    """The text an answer cites: its claims' blocks (v2), or its cited pages (v1)."""
    if out.get("claims"):
        roots = dict.fromkeys(re.sub(r":r\d+$", "", c["block"]) for c in out["claims"])
        return "\n".join(blocks[r] for r in roots if r in blocks)
    return "\n".join(pages.get((manual, p), "") for p in out.get("cited_pages", []))


def _facts_list(item: Item) -> str:
    return "\n".join(f"- {f}" for f in item.key_facts)


def _recorded_abstention(item: Item, out: dict, judge) -> bool:
    if "abstained" in out:
        return bool(out["abstained"])
    reply = judge.ask(ABSTAINED.format(question=item.question, answer=out["answer"]))
    return bool(reply["abstained"])


def _judged_correct(item: Item, out: dict, judge) -> tuple[bool, bool, list[dict]]:
    """(correct, abstained, per-fact results) from the key-fact checklist."""
    reply = judge.ask(
        KEY_FACTS.format(
            question=item.question, facts=_facts_list(item), answer=out["answer"]
        )
    )
    facts = reply.get("facts")
    if not isinstance(facts, list) or len(facts) != len(item.key_facts):
        raise ValueError(
            f"judge returned {facts!r} for {len(item.key_facts)} key facts"
        )
    abstained = bool(out.get("abstained", reply.get("abstained")))
    correct = not abstained and all(bool(f.get("present")) for f in facts)
    return correct, abstained, facts


def grade_item(item: Item, out: dict, judge) -> dict:
    g = {
        "id": item.id,
        "category": item.category,
        "manual": item.manual,
        "answer_chars": len(out.get("answer", "")),
        "correct": None,
        "abstained": None,
        "facts": [],
        "supported_in_source": None,
        "primary": None,
        "judge_error": None,
    }
    try:
        if item.category == "unanswerable":
            g["abstained"] = _recorded_abstention(item, out, judge)
            g["correct"] = g["primary"] = g["abstained"]
            return g
        if item.exact_answer:
            g["correct"] = exact_match(out["answer"], item.exact_answer)
            g["abstained"] = bool(out.get("abstained", False))
            g["correct"] = g["correct"] and not g["abstained"]
        else:
            g["correct"], g["abstained"], g["facts"] = _judged_correct(item, out, judge)
        if not g["correct"]:
            g["primary"] = False
            return g
        reply = judge.ask(
            SOURCE_SUPPORT.format(facts=_facts_list(item), source=out["cited_source"])
        )
        g["supported_in_source"] = bool(reply["supported"])
        g["primary"] = g["supported_in_source"]
    except (ValueError, KeyError) as e:  # unjudged, never scored as wrong
        g.update(correct=None, primary=None, judge_error=str(e)[:300])
    return g


def summarize_grades(grades: list[dict]) -> dict:
    done = [g for g in grades if not g["judge_error"]]
    rate = lambda k: (  # noqa: E731
        round(sum(bool(g[k]) for g in done) / len(done), 4) if done else None
    )
    return {
        "n": len(grades),
        "n_graded": len(done),
        "judge_errors": len(grades) - len(done),
        "correct": rate("correct"),
        "primary": rate("primary"),
        "abstained": rate("abstained"),
    }


def _slope(points: list[tuple[float, float]]) -> float:
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    spread = sum((x - mx) ** 2 for x, _ in points)
    if not spread:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in points) / spread


def length_bias(grades: list[dict], seed: int = 0) -> dict:
    """Least-squares slope of correctness on answer length, with a bootstrap interval."""
    points = [
        (g["answer_chars"] / 100, float(bool(g["correct"])))
        for g in grades
        if g.get("correct") is not None
    ]
    if len(points) < 2:
        return {"slope_per_100_chars": None, "ci95": None}
    rng = random.Random(seed)
    slopes = sorted(
        _slope(rng.choices(points, k=len(points))) for _ in range(BOOTSTRAP)
    )
    return {
        "slope_per_100_chars": round(_slope(points), 4),
        "ci95": [
            round(slopes[int(0.025 * BOOTSTRAP)], 4),
            round(slopes[int(0.975 * BOOTSTRAP)], 4),
        ],
    }
