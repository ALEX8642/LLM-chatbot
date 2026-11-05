"""Compare meaning checkers on the labelled claim set.

Thresholds are chosen on half the items (the false-flag budget in the spec is below 5% of
supported claims) and reported on the other half.

    python -m evals.checker_select evals/claims/labelled.jsonl --checker llm|nli:<model>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

FALSE_FLAG_BUDGET = 0.05


def split(item: str) -> str:
    return "tune" if hashlib.sha256(item.encode()).digest()[0] % 2 == 0 else "report"


def pick_threshold(rows: list[dict]) -> float:
    """The highest threshold whose false flags on supported claims stay within budget."""
    supported = [r["score"] for r in rows if r["supported"]]
    best = 0.0
    for t in sorted({0.0, *(r["score"] for r in rows)}):
        flagged = sum(s < t for s in supported)
        if flagged <= FALSE_FLAG_BUDGET * len(supported):
            best = t
    return best


def metrics(rows: list[dict], threshold: float) -> dict:
    sup = [r for r in rows if r["supported"]]
    uns = [r for r in rows if not r["supported"]]
    caught = sum(r["score"] < threshold for r in uns)
    false_flags = sum(r["score"] < threshold for r in sup)
    flagged = caught + false_flags
    return {
        "supported": len(sup),
        "unsupported": len(uns),
        "unsupported_caught": caught,
        "false_flags": false_flags,
        "recall": caught / len(uns) if uns else None,
        "precision": caught / flagged if flagged else None,
        "false_flag_rate": false_flags / len(sup) if sup else None,
    }


def make_checker(spec: str):
    from manualqa.claimcheck import LLMChecker, NLIChecker

    if spec == "llm":
        from manualqa.generate import Generator

        return LLMChecker(Generator.from_env())
    kind, _, model = spec.partition(":")
    if kind != "nli" or not model:
        raise SystemExit(f"unknown checker {spec}")
    return NLIChecker(model)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("claims", type=Path)
    ap.add_argument("--checker", required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    rows = [json.loads(x) for x in args.claims.read_text().splitlines() if x.strip()]
    checker = make_checker(args.checker)
    times = []
    for r in rows:
        start = time.perf_counter()
        r["score"] = checker.supported(r["claim"], r["premise"])
        times.append(time.perf_counter() - start)
    tune = [r for r in rows if split(r["item"]) == "tune"]
    report = [r for r in rows if split(r["item"]) == "report"]
    threshold = pick_threshold(tune)
    times.sort()
    result = {
        "checker": args.checker,
        "threshold": threshold,
        "tune": metrics(tune, threshold),
        "report": metrics(report, threshold),
        "all": metrics(rows, threshold),
        "seconds_p50": times[len(times) // 2],
        "seconds_p95": times[int(0.95 * len(times))],
    }
    print(json.dumps(result, indent=1))
    if args.out:
        args.out.write_text(json.dumps({**result, "rows": rows}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
