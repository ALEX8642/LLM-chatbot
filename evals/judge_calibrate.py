"""Re-judge only the answers Alexander graded blind, with the current grader and prompts, and
report per system how often the judge fails an answer he passed or passes one he failed.

A pass, for him as for the judge: "correct" with the cited pages showing it, or a decline on
an unanswerable item. Grades are read as a list of {system, item, correct, support}: the
unseen-manual file has those fields, the main test's is joined to its key by screen code.

    LLM_BASE_URL=... LLM_JUDGE_MODEL=phi4:14b python -m evals.judge_calibrate \\
        --grades evals/sessions/blind_grades.jsonl --key evals/sessions/blind_key.json \\
        --qa evals/test.jsonl --composed data/ingest/composed.jsonl \\
        --raw v1=evals/results/raw/v1-test.json --raw v2=evals/results/raw/v2-test.json \\
        --out calibration-test-phi4.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from evals.grade import cited_source, grade_item, page_source
from evals.items import load_items
from evals.prompts import PROMPT_VERSION
from evals.run_eval import CachingJudge
from manualqa.blocks import load_pages


def human_grades(grades: Path, key: Path | None) -> list[dict]:
    rows = [
        json.loads(line) for line in grades.read_text().splitlines() if line.strip()
    ]
    if key is None:
        return [
            {"system": r["system"], "item": r["item"], **r["alexander"]} for r in rows
        ]
    screens = json.loads(key.read_text())["screens"]
    return [
        {**screens[r["code"]], "correct": r["correct"], "support": r["support"]}
        for r in rows
    ]


def human_pass(grade: dict, category: str) -> bool:
    if category == "unanswerable":
        return grade["correct"] == "declined"
    return grade["correct"] == "correct" and grade["support"] == "yes"


def tally(rows: list[dict]) -> dict:
    out = {}
    for system in sorted({r["system"] for r in rows}):
        rs = [r for r in rows if r["system"] == system and r["judge"] is not None]
        good = [r for r in rs if r["human"]]
        bad = [r for r in rs if not r["human"]]
        out[system] = {
            "graded": len(rs),
            "ungraded": sum(r["system"] == system and r["judge"] is None for r in rows),
            "agree": sum(r["judge"] == r["human"] for r in rs),
            "wrongly_fails": sum(not r["judge"] for r in good),
            "human_passes": len(good),
            "wrongly_passes": sum(r["judge"] for r in bad),
            "human_fails": len(bad),
        }
    rates = [
        v["wrongly_fails"] / v["human_passes"]
        for v in out.values()
        if v["human_passes"]
    ]
    out["wrong_fail_gap_points"] = (
        round(100 * (max(rates) - min(rates)), 1) if rates else None
    )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--grades", type=Path, required=True)
    ap.add_argument(
        "--key", type=Path, help="main test: screen code -> system and item"
    )
    ap.add_argument("--qa", type=Path, required=True)
    ap.add_argument("--composed", type=Path, required=True)
    ap.add_argument("--raw", action="append", required=True, help="SYSTEM=PATH")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    items = {i.id: i for i in load_items(args.qa)}
    blocks, pages = {}, {}
    for pp in load_pages(args.composed):
        pages[(pp.manual, pp.page)] = "\n".join(b.text for b in pp.blocks)
        blocks.update({b.id: b.text for b in pp.blocks})
    answers = {}
    for spec in args.raw:
        system, path = spec.split("=", 1)
        answers[system] = {
            r["id"]: r for r in json.loads(Path(path).read_text())["repeats"][0]
        }
    judge = CachingJudge(
        os.environ["LLM_BASE_URL"],
        os.environ.get("LLM_API_KEY", ""),
        os.environ["LLM_JUDGE_MODEL"],
    )
    rows = []
    for g in human_grades(args.grades, args.key):
        item, out = items[g["item"]], answers[g["system"]][g["item"]]
        source = cited_source(out, item.manual, blocks, pages)
        pages_only = page_source(out, item.manual, pages) if out.get("claims") else None
        graded = grade_item(
            item, {**out, "cited_source": source, "page_source": pages_only}, judge
        )
        rows.append(
            {
                "system": g["system"],
                "item": g["item"],
                "human": human_pass(g, item.category),
                "judge": graded["primary"],
                "grade": graded,
            }
        )
        print(
            f"{g['system']} {g['item']}: human {rows[-1]['human']} judge {graded['primary']}",
            flush=True,
        )
    summary = tally(rows)
    args.out.write_text(
        json.dumps(
            {
                "judge": {"model": judge.model, "prompt_version": PROMPT_VERSION},
                "summary": summary,
                "rows": rows,
            },
            indent=1,
        )
    )
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
