"""Re-run v2's deterministic claim checks (quote match, wording, facts) on every claim a recorded
run made, against the ingest it ran on, and list each claim whose verdict differs from the
recorded one. The meaning check needs a model, so a claim it removed keeps its recorded verdict,
and a claim that now passes would still go to it. Used to see what a change to the checks
rescues and what it breaks before any run.

    python -m evals.check_audit INGEST_DIR ITEMS RAW [RAW ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from manualqa.answer import _figure_claim, _page_text, _relocate
from manualqa.facts import check_facts, check_wording
from manualqa.generate import RawClaim
from manualqa.quotes import match_quote
from manualqa.retrieve import Evidence, IngestContext, _block_evidence, row_evidence

MEANING = {"the source does not say this", "the page does not say this"}


def evidence(ctx: IngestContext, block: str) -> Evidence | None:
    base, _, row = block.rpartition(":r")
    if base and row.isdigit() and base in ctx.blocks:
        under = ctx.under.get(ctx.block_page[base], "")
        for hit in ctx.tables.lookup_table(block_id=base, limit=1000):
            if hit.row == int(row):
                return row_evidence(hit, under)
        return None
    return _block_evidence(ctx, block)


def verdict(ctx: IngestContext, claim: dict, question: str) -> str | None:
    """None when the deterministic checks pass, else the reason they remove the claim."""
    ev = evidence(ctx, claim["block"])
    if ev is None:
        return "unknown block"
    raw = RawClaim(claim["claim"], claim["block"], claim["quote"], "")
    if ev.kind == "figure":
        c = _figure_claim(raw, ev, question, _page_text(ctx, ev))
        return c.reason
    match = match_quote(raw.quote, ev)
    if match is None:
        moved = _relocate(raw.quote, ev, ctx)
        if moved:
            ev, match = moved
    if match is None:
        return "quote not in cited block"
    result = check_wording(raw.quote, match.source, ev.text[: match.span[0]])
    if result.ok:
        result = check_facts(raw.claim, match.source, ev, question, _page_text(ctx, ev))
    return None if result.ok else result.reason


def audit(ctx: IngestContext, questions: dict[str, str], path: Path) -> list[dict]:
    """Claims whose verdict differs from the recorded one, first repeat only (v2 is
    deterministic across repeats)."""
    changed = []
    for record in json.loads(path.read_text())["repeats"][0]:
        question = questions.get(record["id"], "")
        for c in [*(record.get("claims") or []), *(record.get("removed") or [])]:
            recorded = None if c["status"] in ("verified", "figure") else c["reason"]
            if recorded in MEANING:
                continue
            now = verdict(ctx, c, question)
            if (now is None) != (recorded is None):
                changed.append(
                    {"id": record["id"], "claim": c["claim"], "quote": c["quote"],
                     "recorded": recorded, "now": now}
                )  # fmt: skip
    return changed


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ctx = IngestContext.load(Path(argv[0]), None, None)
    questions = {
        json.loads(line)["id"]: json.loads(line)["question"]
        for line in Path(argv[1]).read_text().splitlines()
        if line.strip()
    }
    for path in argv[2:]:
        changed = audit(ctx, questions, Path(path))
        rescued = sum(c["now"] is None for c in changed)
        print(
            f"{path}: {rescued} removed claims now pass, {len(changed) - rescued} verified now fail"
        )
        for c in changed:
            print(
                f"  {c['id']}: {c['recorded'] or 'verified'} -> {c['now'] or 'pass'}: {c['claim'][:110]!r}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
