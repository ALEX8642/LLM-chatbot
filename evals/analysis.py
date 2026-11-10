"""The pre-registered analysis: paired comparison of two scored systems.

An item's score is the majority of its graded repeats. The primary test is an exact McNemar
test on the items where the systems differ, with a paired bootstrap interval that resamples
clusters of related items, since those can succeed or fail together.

    python -m evals.analysis --items evals/test.jsonl --a V2_SCORED --b V1_SCORED
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path

from evals.items import load_items

BOOTSTRAP, SEED = 10_000, 20261106
Z_ALPHA, Z_POWER = 1.96, 0.84  # two-sided 5%, 80% power
_PART_NUMBER = re.compile(r"\bpart numbers?\b", re.I)


def item_scores(scored: dict, field: str = "primary") -> dict[str, bool]:
    """Item id -> majority of its repeats. Ungraded repeats are left out; a tie is a fail."""
    votes: dict[str, list[bool]] = defaultdict(list)
    for repeat in scored["repeats"]:
        for row in repeat["items"]:
            if not row.get("judge_error"):
                votes[row["id"]].append(bool(row[field]))
    return {i: sum(v) * 2 > len(v) for i, v in votes.items() if v}


def clusters(items: list, mode: str = "primary") -> dict[str, str]:
    """Item id -> cluster. Primary: items joined by a shared gold page or by the part-number
    template. "page" drops the template, "section" uses whole manual sections."""
    parent = {it.id: it.id for it in items}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(key_items: dict[str, list[str]]) -> None:
        for ids in key_items.values():
            for other in ids[1:]:
                parent[find(other)] = find(ids[0])

    groups: dict[str, list[str]] = defaultdict(list)
    for it in items:
        if mode == "section":
            for section in it.sections:
                groups[f"{it.manual}:{section}"].append(it.id)
            continue
        for page in it.gold_pages:
            groups[f"{it.manual}:{page}"].append(it.id)
        if mode == "primary" and _PART_NUMBER.search(it.question):
            groups["part-number"].append(it.id)
    join(groups)
    return {it.id: find(it.id) for it in items}


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """Two-sided exact p from the discordant counts."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(a_only, b_only) + 1)) / 2**n
    return min(1.0, 2 * tail)


def bootstrap_interval(
    diffs: dict[str, int],
    cluster_of: dict[str, str],
    n: int = BOOTSTRAP,
    seed: int = SEED,
) -> dict:
    """95% interval for the mean paired difference, resampling clusters; and the variance
    relative to resampling single items, which gives the effective number of items."""
    members: dict[str, list[int]] = defaultdict(list)
    for i, d in diffs.items():
        members[cluster_of[i]].append(d)
    groups = [(sum(v), len(v)) for v in members.values()]
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        picked = rng.choices(groups, k=len(groups))
        means.append(sum(s for s, _ in picked) / sum(c for _, c in picked))
    means.sort()
    average = sum(means) / n
    variance = sum((m - average) ** 2 for m in means) / (n - 1)
    values = list(diffs.values())
    mean = sum(values) / len(values)
    item_variance = (
        sum((v - mean) ** 2 for v in values) / (len(values) - 1) / len(values)
    )
    return {
        "low": means[int(0.025 * n)],
        "high": means[int(0.975 * n)],
        "clusters": len(groups),
        "effective_n": len(values) * item_variance / variance if variance else None,
    }


def minimum_detectable(discordant_share: float, effective_n: float) -> float:
    """The smallest true difference this design finds 80% of the time."""
    return (Z_ALPHA + Z_POWER) * math.sqrt(discordant_share / effective_n)


def compare(a: dict[str, bool], b: dict[str, bool], cluster_of: dict[str, str]) -> dict:
    ids = sorted(set(a) & set(b) & set(cluster_of))
    a_only = sum(a[i] and not b[i] for i in ids)
    b_only = sum(b[i] and not a[i] for i in ids)
    diffs = {i: int(a[i]) - int(b[i]) for i in ids}
    interval = bootstrap_interval(diffs, cluster_of)
    share = (a_only + b_only) / len(ids)
    return {
        "n": len(ids),
        "ungraded": len(cluster_of) - len(ids),
        "a": sum(a[i] for i in ids) / len(ids),
        "b": sum(b[i] for i in ids) / len(ids),
        "difference": sum(diffs.values()) / len(ids),
        "a_only": a_only,
        "b_only": b_only,
        "mcnemar_p": mcnemar_exact(a_only, b_only),
        "interval": interval,
        "minimum_detectable": (
            minimum_detectable(share, interval["effective_n"])
            if interval["effective_n"]
            else None
        ),
    }


def holm(p_values: dict[str, float]) -> dict[str, float]:
    """Holm-adjusted p values."""
    adjusted, running = {}, 0.0
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    for rank, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p))
        adjusted[name] = running
    return adjusted


def taxonomy(row: dict, item, recorded: dict | None) -> str:
    """A first label for a failed item, from recorded facts. The rest are read by hand."""
    if item.category == "unanswerable":
        return "answered an unanswerable question"
    if row.get("abstained"):
        return "wrong abstention"
    if row.get("correct") and not row.get("primary"):
        return "bad citation"
    if recorded and not set(item.gold_pages) & set(recorded.get("ranked_pages", [])):
        return "not retrieved"
    return "wrong answer: read by hand"


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def holm_files(paths: list[Path], mode: str = "primary") -> dict[str, float]:
    """Holm-adjusted p values for the contrasts in analysis files written by ``main``."""
    return holm({str(p): _load(p)[mode]["mcnemar_p"] for p in paths})


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        import sys

        argv = sys.argv[1:]
    if argv[:1] == ["holm"]:  # python -m evals.analysis holm FILE...
        print(json.dumps(holm_files([Path(p) for p in argv[1:]]), indent=1))
        return 0
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--items", type=Path, required=True)
    ap.add_argument(
        "--a", type=Path, required=True, help="scored file of the system tested"
    )
    ap.add_argument(
        "--b", type=Path, required=True, help="scored file it is compared with"
    )
    ap.add_argument("--field", default="primary")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    items = load_items(args.items)
    a, b = (item_scores(_load(p), args.field) for p in (args.a, args.b))
    result = {
        mode: compare(a, b, clusters(items, mode))
        for mode in ("primary", "page", "section")
    }
    text = json.dumps(result, indent=1)
    print(text)
    if args.out:
        args.out.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
