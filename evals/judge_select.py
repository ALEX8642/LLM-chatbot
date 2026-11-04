"""Scores judge candidates against the calibration labels (evals/calibration).

    python -m evals.judge_select --base-url URL --models a,b,c --out FILE

Rule, fixed before any result: highest kappa on item correctness; within 0.05 the higher kappa
on source support; if that also ties within 0.05, the faster. Over 5% JSON failures is out.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from evals.grade import cited_source, length_bias
from evals.items import _squash, load_items
from evals.prompts import ABSTAINED, KEY_FACTS, SOURCE_SUPPORT

ROOT = Path(__file__).resolve().parents[1]
TIE = 0.05
MAX_JSON_FAILURES = 0.05


def cohen_kappa(a: list, b: list) -> float | None:
    if not a:
        return None
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    chance = sum(a.count(v) / n * b.count(v) / n for v in set(a) | set(b))
    return 1.0 if chance == 1 else round((observed - chance) / (1 - chance), 4)


def evaluate(
    judge, rows: list[dict], items: dict, source_of, wrong_source_of=None
) -> dict:
    facts_l, facts_j, correct_l, correct_j = [], [], [], []
    source_l, source_j, abst_l, abst_j, lengths = [], [], [], [], []
    failures = 0
    start = time.time()
    for r in rows:
        item, labels = items[r["item"]], r["labels"]
        try:
            if item.category == "unanswerable":
                reply = judge.ask(
                    ABSTAINED.format(question=item.question, answer=r["answer"])
                )
                abst_j.append(bool(reply["abstained"]))
                abst_l.append(labels["abstained"])
                continue
            facts_text = "\n".join(f"- {f}" for f in item.key_facts)
            reply = judge.ask(
                KEY_FACTS.format(
                    question=item.question, facts=facts_text, answer=r["answer"]
                )
            )
            got = reply.get("facts")
            if not isinstance(got, list) or len(got) != len(item.key_facts):
                raise ValueError("wrong number of facts")
            present = [bool(f.get("present")) for f in got]
            abstained = bool(reply.get("abstained"))
            supported = wrong = None
            if labels["supported"] is not None:
                supported = judge.ask(
                    SOURCE_SUPPORT.format(facts=facts_text, source=source_of(r, item))
                )["supported"]
                if wrong_source_of and labels["supported"]:
                    wrong = judge.ask(
                        SOURCE_SUPPORT.format(
                            facts=facts_text, source=wrong_source_of(r, item)
                        )
                    )["supported"]
        except (ValueError, KeyError):
            failures += 1
            continue
        facts_l += labels["facts"]
        facts_j += present
        correct_l.append(all(labels["facts"]) and not labels["abstained"])
        correct_j.append(all(present) and not abstained)
        abst_l.append(labels["abstained"])
        abst_j.append(abstained)
        lengths.append({"correct": correct_j[-1], "answer_chars": len(r["answer"])})
        if supported is not None:
            source_l.append(labels["supported"])
            source_j.append(bool(supported))
        if wrong is not None:
            source_l.append(False)
            source_j.append(bool(wrong))
    return {
        "model": judge.model,
        "n": len(rows),
        "kappa_correct": cohen_kappa(correct_l, correct_j),
        "kappa_facts": cohen_kappa(facts_l, facts_j),
        "kappa_source": cohen_kappa(source_l, source_j),
        "source_agreement": (
            round(sum(a == b for a, b in zip(source_l, source_j)) / len(source_l), 4)
            if source_l
            else None
        ),
        "kappa_abstained": cohen_kappa(abst_l, abst_j),
        "json_failures": failures,
        "json_failure_rate": round(failures / len(rows), 4),
        "seconds_per_row": round((time.time() - start) / len(rows), 1),
        "length_bias": length_bias(lengths),
    }


def wrong_page(item, pages: dict, min_chars: int = 0) -> str:
    """A page of the same manual holding none of the item's anchors, chosen repeatably."""
    candidates = sorted(
        p
        for (m, p), text in pages.items()
        if m == item.manual
        and len(text) >= min_chars
        and not any(_squash(a) in _squash(text) for a in item.anchors)
    )
    return pages[(item.manual, random.Random(item.id).choice(candidates))]


def pick(results: list[dict]) -> dict | None:
    ok = [r for r in results if r["json_failure_rate"] <= MAX_JSON_FAILURES]
    if not ok:
        return None
    best = max(r["kappa_correct"] for r in ok)
    near = [r for r in ok if r["kappa_correct"] >= best - TIE]
    best = max(r["kappa_source"] or 0 for r in near)
    near = [r for r in near if (r["kappa_source"] or 0) >= best - TIE]
    return min(near, key=lambda r: r["seconds_per_row"])


def main(argv: list[str] | None = None) -> int:
    from evals.run_eval import Judge
    from manualqa.blocks import load_pages

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument(
        "--calib", type=Path, default=ROOT / "evals/calibration/calib.jsonl"
    )
    ap.add_argument(
        "--composed", type=Path, default=ROOT / "data/ingest/composed.jsonl"
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    rows = [json.loads(line) for line in args.calib.read_text().splitlines() if line]
    items = {i.id: i for i in load_items(ROOT / "evals/pool/legacy.jsonl")}
    blocks, pages = {}, {}
    for pp in load_pages(args.composed):
        pages[(pp.manual, pp.page)] = "\n".join(b.text for b in pp.blocks)
        blocks.update({b.id: b.text for b in pp.blocks})

    def source_of(row: dict, item) -> str:
        return cited_source(row, item.manual, blocks, pages)

    results = []
    for model in args.models.split(","):
        judge = Judge(args.base_url, "", model)
        judge.max_tokens = 1500
        results.append(
            evaluate(
                judge,
                rows,
                items,
                source_of,
                lambda r, i: wrong_page(i, pages, min_chars=200),
            )
        )
        print(json.dumps(results[-1]), flush=True)
        args.out.write_text(json.dumps(results, indent=1))
    winner = pick(results)
    print("winner:", winner and winner["model"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
