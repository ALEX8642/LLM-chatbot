"""Assigns whole manual sections to dev or test, and writes the two item files.

Sections that share an item are linked and stay together, so no gold page of a test item
lies in a dev section. Sections of the original 42 items are forced into dev; further
units join dev, in seeded order, only until dev reaches its targets.

    python -m evals.split [--seed N]    writes evals/qa.jsonl, evals/test.jsonl, evals/split.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz

from evals.items import Item, dump_items, load_items, load_sections
from manualqa.textnorm import norm

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261103
MIN_DEV = 80
MIN_UNANSWERABLE = 20
DUPLICATE_MIN = 90


def split(
    items: list[Item],
    sections: dict,
    seed: int,
    forced_dev: set[str],
    min_dev: int = MIN_DEV,
    min_unanswerable: int = MIN_UNANSWERABLE,
) -> dict[str, str]:
    """Section id -> "dev" or "test"."""
    parent = {s["id"]: s["id"] for secs in sections.values() for s in secs}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for it in items:
        for other in it.sections[1:]:
            parent[find(other)] = find(it.sections[0])

    units: dict[str, list[Item]] = {root: [] for root in map(find, parent)}
    for it in items:
        units[find(it.sections[0])].append(it)

    dev = {find(s) for s in forced_dev}
    count = lambda: sum(len(units[u]) for u in dev)  # noqa: E731
    unanswerable = lambda: sum(  # noqa: E731
        i.category == "unanswerable" for u in dev for i in units[u]
    )
    rest = sorted(u for u in units if u not in dev and units[u])
    random.Random(seed).shuffle(rest)
    for u in rest:
        if count() >= min_dev and unanswerable() >= min_unanswerable:
            break
        wants_any = count() < min_dev
        has_unanswerable = any(i.category == "unanswerable" for i in units[u])
        if wants_any or has_unanswerable:
            dev.add(u)
    return {s: ("dev" if find(s) in dev else "test") for s in parent}


def apply_split(items: list[Item], assign: dict[str, str]) -> tuple[list, list]:
    dev = [i for i in items if assign[i.sections[0]] == "dev"]
    test = [i for i in items if assign[i.sections[0]] == "test"]
    return dev, test


def near_duplicates(
    dev: list[Item], test: list[Item], threshold: int = DUPLICATE_MIN
) -> list[tuple[str, str]]:
    """Pairs of ids whose questions match across the splits, whatever the word order."""
    return [
        (d.id, t.id)
        for d in dev
        for t in test
        if fuzz.token_set_ratio(norm(d.question), norm(t.question)) >= threshold
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    items = load_items(ROOT / "evals" / "pool")
    legacy = load_items(ROOT / "evals" / "pool" / "legacy.jsonl")
    assign = split(
        items, load_sections(), args.seed, {s for i in legacy for s in i.sections}
    )
    dev, test = apply_split(items, assign)
    dump_items(dev, ROOT / "evals" / "qa.jsonl")
    dump_items(test, ROOT / "evals" / "test.jsonl")
    summary = {
        "seed": args.seed,
        "dev": len(dev),
        "test": len(test),
        "dev_categories": Counter(i.category for i in dev),
        "test_categories": Counter(i.category for i in test),
        "sections": assign,
    }
    (ROOT / "evals" / "split.json").write_text(json.dumps(summary, indent=1) + "\n")
    print({k: v for k, v in summary.items() if k != "sections"})
    for pair in near_duplicates(dev, test):
        print("near duplicate:", *pair)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
