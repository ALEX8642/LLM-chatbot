import json
from collections import Counter
from pathlib import Path

from evals.items import Item, load_items, load_sections, section_of
from evals.split import SEED, apply_split, near_duplicates, split

ROOT = Path(__file__).resolve().parents[2]
POOL = load_items(ROOT / "evals" / "pool")
SECTIONS = load_sections()
LEGACY = {s for i in load_items(ROOT / "evals/pool/legacy.jsonl") for s in i.sections}
ASSIGN = split(POOL, SECTIONS, SEED, LEGACY)
DEV, TEST = apply_split(POOL, ASSIGN)


def item(id, sections, question="q", category="single_page"):
    return Item(id, "m.pdf", sections, category, question, [1], "r", ["f"], ["a"])


def test_forced_sections_stay_dev():
    assert all(ASSIGN[s] == "dev" for s in LEGACY)


def test_targets_met():
    assert len(DEV) >= 80
    assert sum(i.category == "unanswerable" for i in DEV) >= 20
    assert len(TEST) >= 150  # tier 1 range: 150-200
    assert sum(i.near_miss for i in TEST) >= 30
    pool = Counter(i.category for i in POOL)
    test = Counter(i.category for i in TEST)
    for cat, n in pool.items():
        assert abs(test[cat] / len(TEST) - n / len(POOL)) <= 0.15, cat


def test_no_page_in_both_splits():
    dev_sections = {s for i in DEV for s in i.sections}
    for i in TEST:
        for p in i.gold_pages:
            assert section_of(SECTIONS, i.manual, p) not in dev_sections, i.id


def test_linked_sections_share_a_split():
    secs = {"m.pdf": [{"id": x, "first": 1, "last": 1} for x in "ABC"]}
    items = [item("a", ["A", "B"]), item("b", ["C"])]
    got = split(items, secs, 1, {"A"}, min_dev=1, min_unanswerable=0)
    assert got["A"] == got["B"] == "dev"


def test_near_duplicate_across_splits_flagged():
    dev = [item("a", ["A"], "What is the part number of the muffler?")]
    test = [
        item("b", ["B"], "The muffler: what is the part number of it?"),
        item("c", ["C"], "How deep must the ground rod be driven?"),
    ]
    assert near_duplicates(dev, test) == [("a", "b")]


def test_split_is_deterministic():
    assert split(POOL, SECTIONS, SEED, LEGACY) == ASSIGN


def test_committed_split_matches():
    saved = json.loads((ROOT / "evals" / "split.json").read_text())
    assert saved["sections"] == ASSIGN
    assert saved["dev"] == len(DEV) and saved["test"] == len(TEST)
