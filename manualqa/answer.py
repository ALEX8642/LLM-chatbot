"""The answer path: retrieve, generate claims, check each claim, answer or abstain.

Per claim, in order: an unknown evidence id is dropped (and counted); a figure claim is
kept, labelled as read from the figure, only if the figure's text contains its numbers;
otherwise the quote must match the cited evidence (the claim is then shown with its
highlight boxes) and pass the deterministic fact checks (the claim is then settled as
verified). A claim that fails is removed, with the reason. If no claim survives, the
answer says so and lists the pages it looked at.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator, Literal

from manualqa.facts import check_facts
from manualqa.generate import ClaimParser, RawClaim, build_messages
from manualqa.geometry import Box
from manualqa.prompts import REWRITE
from manualqa.quotes import match_quote
from manualqa.retrieve import Evidence, IngestContext, RetrievalResult, retrieve

ABSTAIN = "I could not find the answer in the manual."


@dataclass
class CheckedClaim:
    claim: str
    block: str
    quote: str
    page: int | None
    boxes: list[Box]
    status: Literal["pending", "verified", "figure", "removed"]
    reason: str | None = None


@dataclass
class Answer:
    question: str
    text: str
    claims: list[CheckedClaim]
    removed: list[CheckedClaim]
    abstained: bool
    abstain_reason: str | None
    retrieval: RetrievalResult
    unknown_blocks: int = 0
    ignored_lines: list[str] = field(default_factory=list)
    timings: dict = field(default_factory=dict)


@dataclass
class AnswerEvent:
    kind: Literal["retrieved", "claim_shown", "claim_settled", "claim_removed", "done"]
    claim: CheckedClaim | None = None
    answer: Answer | None = None


def _figure_claim(raw: RawClaim, ev: Evidence) -> CheckedClaim:
    facts = check_facts(raw.claim, ev.text, ev)
    status, reason = ("figure", None) if facts.ok else ("removed", facts.reason)
    return CheckedClaim(
        raw.claim, raw.block, raw.quote, ev.page, ev.boxes, status, reason
    )


def _standalone(question: str, history: list[dict], gen) -> str:
    messages = [
        {"role": "system", "content": REWRITE},
        *history,
        {"role": "user", "content": question},
    ]
    rewritten = gen.complete(messages).strip()
    return rewritten or question


def answer_stream(
    question: str,
    manual: str,
    ctx: IngestContext,
    gen,
    history: list[dict] | None = None,
) -> Iterator[AnswerEvent]:
    start = time.perf_counter()
    history = history or []
    query = _standalone(question, history, gen) if history else question
    retrieval = retrieve(query, manual, ctx)
    timings = {"retrieval_s": time.perf_counter() - start}
    yield AnswerEvent("retrieved")

    by_id = {e.id: e for e in retrieval.evidence}
    parser = ClaimParser()
    kept: list[CheckedClaim] = []
    removed: list[CheckedClaim] = []
    unknown = 0

    def check(raw: RawClaim) -> Iterator[AnswerEvent]:
        nonlocal unknown
        ev = by_id.get(raw.block)
        if ev is None:
            unknown += 1
            return
        if ev.kind == "figure":
            c = _figure_claim(raw, ev)
            (kept if c.status == "figure" else removed).append(c)
            yield AnswerEvent(
                "claim_settled" if c.status == "figure" else "claim_removed", c
            )
            return
        match = match_quote(raw.quote, ev)
        if match is None:
            c = CheckedClaim(
                raw.claim,
                raw.block,
                raw.quote,
                ev.page,
                [],
                "removed",
                "quote not in cited block",
            )
            removed.append(c)
            yield AnswerEvent("claim_removed", c)
            return
        c = CheckedClaim(
            raw.claim, raw.block, raw.quote, ev.page, match.boxes, "pending"
        )
        timings.setdefault("first_claim_s", time.perf_counter() - start)
        yield AnswerEvent("claim_shown", c)
        facts = check_facts(raw.claim, raw.quote, ev)
        if facts.ok:
            c.status = "verified"
            kept.append(c)
            yield AnswerEvent("claim_settled", c)
        else:
            c.status, c.reason = "removed", facts.reason
            removed.append(c)
            yield AnswerEvent("claim_removed", c)

    messages = build_messages(query, history, retrieval.evidence, retrieval.page_images)
    for piece in gen.stream(messages):
        for raw in parser.feed(piece):
            yield from check(raw)
    for raw in parser.close():
        yield from check(raw)

    abstained = not kept
    if abstained:
        pages = ", ".join(str(p) for p in retrieval.ranked_pages[:5]) or "none"
        text = f"{ABSTAIN} I looked at pages {pages}."
    else:
        text = "\n".join(
            c.claim + (" (read from figure)" if c.status == "figure" else "")
            for c in kept
        )
    timings["total_s"] = time.perf_counter() - start
    result = Answer(
        question=question,
        text=text,
        claims=kept,
        removed=removed,
        abstained=abstained,
        abstain_reason=parser.abstain,
        retrieval=retrieval,
        unknown_blocks=unknown,
        ignored_lines=parser.ignored,
        timings=timings,
    )
    yield AnswerEvent("done", answer=result)


def answer(
    question: str,
    manual: str,
    ctx: IngestContext,
    gen,
    history: list[dict] | None = None,
) -> Answer:
    for event in answer_stream(question, manual, ctx, gen, history):
        if event.kind == "done":
            return event.answer
    raise RuntimeError("answer stream ended without a result")
