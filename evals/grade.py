"""Grades answers: exact match for short answers, a key-fact checklist otherwise, and whether
the judge finds the key facts in the cited source (the primary endpoint needs both).

A long cited source (v1 cites whole pages) is checked one key fact at a time, on the passages
of it nearest that fact and the answer, so the judge reads about as much for either system:
in blind grading the local judges missed support in long sources far more often than in short
ones (evals/unseen/RESULTS.md)."""

from __future__ import annotations

import random
import re
import unicodedata

from evals.items import Item
from evals.prompts import ABSTAINED, FACT_COUNT, KEY_FACTS, SOURCE_SUPPORT

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
_UNITS = {"lbs": "lb", "pound": "lb", "pounds": "lb"}
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_TRAILING_ZEROS = re.compile(r"(?<![\d.])(\d*\.\d*?)0+(?!\d)")
_MARKUP = re.compile(r"[*`%]")
BOOTSTRAP = 1000
SUPPORT_CHARS = 3000  # a cited source longer than this is checked fact by fact
PASSAGE_CHARS, PASSAGES = 800, 3
_VULGAR = re.compile(r"(?<=\d)(?=[\u00bc-\u00be\u2150-\u215e])")  # "7¾" -> "7 3/4"
_STOP = set("the and for with that this from are was were has have not but its".split())


def normalise(text: str) -> str:
    """Case, dashes, plus-minus, thousands separators, units, and numbers like 3.80."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES).casefold()
    text = text.replace("+/-", " ± ").replace("±", " ± ")
    text = _MARKUP.sub(" ", _THOUSANDS.sub("", text))
    text = _TRAILING_ZEROS.sub(lambda m: m.group(1).rstrip("."), text)
    tokens = []
    for raw in text.split():
        token = raw.strip(".,;:()[]\"'")
        if token:
            tokens.append(_UNITS.get(token, token))
    return " ".join(tokens)


def exact_match(answer: str, exact: str) -> bool:
    """The value occurs as a whole: a space or hyphen may separate its parts, but it may not
    be part of a longer code ("37" is not in "P15121-37", nor "88-21063" in "88-21063-1").
    """
    parts = re.split(r"[ -]+", normalise(exact))
    body = r"[ -]+".join(re.escape(p) for p in parts)
    return (
        re.search(rf"(?<![\w.-]){body}(?![\w]|-\d|\.\d)", normalise(answer)) is not None
    )


def cited_source(out: dict, manual: str, blocks: dict, pages: dict) -> str:
    """The text an answer cites: its claims' blocks (v2), or its cited pages (v1)."""
    if out.get("claims"):
        roots = dict.fromkeys(re.sub(r":r\d+$", "", c["block"]) for c in out["claims"])
        return "\n".join(blocks[r] for r in roots if r in blocks)
    return page_source(out, manual, pages)


def page_source(out: dict, manual: str, pages: dict) -> str:
    """The text of the cited pages, each once: v1's citation, and v2's as a sensitivity."""
    cited = dict.fromkeys(out.get("cited_pages", []))
    return "\n".join(pages.get((manual, p), "") for p in cited)


def _facts_list(item: Item) -> str:
    return "\n".join(f"- {f}" for f in item.key_facts)


def _terms(text: str) -> set[str]:
    text = unicodedata.normalize("NFKC", _VULGAR.sub(" ", text)).replace("\u2044", "/")
    return {
        t
        for t in normalise(text).split()
        if (len(t) >= 3 or any(c.isdigit() for c in t)) and t not in _STOP
    }


def passages(source: str, fact: str, answer: str) -> str:
    """The PASSAGES windows of the source (about PASSAGE_CHARS each, whole lines, in source
    order) that share the most terms with the fact; the answer's terms only break ties, so a
    long answer cannot outvote the fact."""
    lines = source.split("\n")
    want, also = _terms(fact), _terms(answer)
    windows = []  # (score, first line, last line + 1)
    for i in range(len(lines)):
        j, size = i, 0
        while j < len(lines) and (size < PASSAGE_CHARS or j == i):
            size += len(lines[j]) + 1
            j += 1
        have = _terms("\n".join(lines[i:j]))
        windows.append(((len(want & have), len(also & have)), i, j))
    chosen: list[tuple[int, int]] = []
    for _, i, j in sorted(windows, key=lambda w: (-w[0][0], -w[0][1], w[1])):
        if all(j <= a or i >= b for a, b in chosen):
            chosen.append((i, j))
        if len(chosen) == PASSAGES:
            break
    return "\n[...]\n".join("\n".join(lines[i:j]) for i, j in sorted(chosen))


def supported(item: Item, source: str, answer: str, judge) -> bool:
    if len(source) <= SUPPORT_CHARS:
        reply = judge.ask(SOURCE_SUPPORT.format(facts=_facts_list(item), source=source))
        return bool(reply["supported"])
    return all(
        bool(
            judge.ask(
                SOURCE_SUPPORT.format(
                    facts=f"- {fact}", source=passages(source, fact, answer)
                )
            )["supported"]
        )
        for fact in item.key_facts
    )


def _judged_abstention(item: Item, out: dict, judge) -> bool:
    reply = judge.ask(ABSTAINED.format(question=item.question, answer=out["answer"]))
    return bool(reply["abstained"])


def _judged_correct(item: Item, out: dict, judge) -> tuple[bool, bool, list[dict]]:
    """(correct, abstained, per-fact results) from the key-fact checklist."""
    prompt = KEY_FACTS.format(
        question=item.question, facts=_facts_list(item), answer=out["answer"]
    )
    n = len(item.key_facts)
    reply = judge.ask(prompt)
    facts = reply.get("facts")
    if not isinstance(facts, list) or len(facts) != n:
        reply = judge.ask(prompt + FACT_COUNT.format(n=n))
        facts = reply.get("facts")
    if not isinstance(facts, list) or len(facts) != n:
        raise ValueError(f"judge returned {facts!r} for {n} key facts")
    abstained = bool(reply.get("abstained"))
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
        "recorded_abstained": out.get("abstained"),
        "supported_in_pages": None,
        "facts": [],
        "supported_in_source": None,
        "primary": None,
        "judge_error": None,
    }
    try:
        if item.category == "unanswerable":
            g["abstained"] = _judged_abstention(item, out, judge)
            g["correct"] = g["primary"] = g["abstained"]
            return g
        if item.exact_answer:
            g["correct"] = exact_match(out["answer"], item.exact_answer)
            g["abstained"] = (
                False if g["correct"] else _judged_abstention(item, out, judge)
            )
        else:
            g["correct"], g["abstained"], g["facts"] = _judged_correct(item, out, judge)
        if not g["correct"]:
            g["primary"] = False
            return g
        answer = out["answer"]
        g["supported_in_source"] = supported(item, out["cited_source"], answer, judge)
        g["primary"] = g["supported_in_source"]
        g["supported_in_pages"] = g["supported_in_source"]
        if out.get("page_source"):
            g["supported_in_pages"] = supported(item, out["page_source"], answer, judge)
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
        "primary_pages": (
            round(
                sum(
                    (
                        bool(g["primary"] or g["supported_in_pages"])
                        if g["correct"]
                        else bool(g["primary"])
                    )
                    for g in done
                )
                / len(done),
                4,
            )
            if done
            else None
        ),
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
