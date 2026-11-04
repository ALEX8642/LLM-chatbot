"""Applies the gold-answer session's checks: evals/sessions/gold_checks.jsonl, exported from the
session page's database (one JSON object per line: id, verdict, edits, reason, at).

    python -m evals.sessions.gold_export        applies edits to evals/test.jsonl, prints the error rate
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from evals.items import dump_items, load_items

ROOT = Path(__file__).resolve().parents[2]
EDITABLE = ("question", "reference_answer", "key_facts")


def wilson(errors: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = errors / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4))


def apply_checks(items: list, checks: list[dict]) -> dict:
    by_id = {i.id: i for i in items}
    wrong, edited = [], []
    for c in checks:
        item = by_id[c["id"]]
        if c["verdict"] == "wrong":
            wrong.append(c["id"])
        elif c["verdict"] == "edited":
            for field in EDITABLE:
                if field in c:
                    setattr(item, field, c[field])
            item.provenance = {**item.provenance, "edited_by": "Alexander"}
            edited.append(c["id"])
    n, errors = len(checks), len(wrong) + len(edited)
    return {
        "checked": n,
        "wrong": wrong,
        "edited": edited,
        "gold_error_rate": round(errors / n, 4) if n else None,
        "ci95": wilson(errors, n),
    }


def main() -> int:
    path = ROOT / "evals" / "test.jsonl"
    items = load_items(path)
    lines = (ROOT / "evals/sessions/gold_checks.jsonl").read_text().splitlines()
    report = apply_checks(items, [json.loads(line) for line in lines if line])
    dump_items(items, path)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
