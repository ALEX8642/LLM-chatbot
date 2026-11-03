"""Evaluation items: schema, loading, and the anchor validator.

Every item is tied to its source mechanically. An answerable item's anchors are exact
strings that must appear on one of its gold pages; an unanswerable item's anchors are the
terms its question needs, which must appear nowhere in its manual.

    python -m evals.items validate evals/pool [--composed data/ingest/composed.jsonl]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from manualqa.textnorm import norm

CATEGORIES = {"single_page", "multi_page", "table", "figure", "unanswerable"}
ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Item:
    id: str
    manual: str
    sections: list[str]
    category: str
    question: str
    gold_pages: list[int]
    reference_answer: str
    key_facts: list[str] = field(default_factory=list)
    anchors: list[str] = field(default_factory=list)
    exact_answer: str | None = None
    near_miss: bool = False
    provenance: dict = field(default_factory=dict)


def load_items(path: Path) -> list[Item]:
    """Items from one .jsonl file, or from every .jsonl file in a directory."""
    path = Path(path)
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    return [
        Item(**json.loads(line))
        for f in files
        for line in f.read_text().splitlines()
        if line.strip()
    ]


def dump_items(items: list[Item], path: Path) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def load_sections(path: Path = ROOT / "evals" / "sections.json") -> dict:
    return json.loads(Path(path).read_text())


def section_of(sections: dict, manual: str, page: int) -> str:
    for s in sections[manual]:
        if s["first"] <= page <= s["last"]:
            return s["id"]
    raise KeyError(f"{manual} p{page} is in no section")


def pages_text(composed: Path) -> dict[tuple[str, int], str]:
    """(manual, page) -> the page's composed text, from plan 2's composed.jsonl."""
    from manualqa.blocks import load_pages

    return {
        (pp.manual, pp.page): "\n".join(b.text for b in pp.blocks)
        for pp in load_pages(Path(composed))
    }


def _squash(text: str) -> str:
    # spaces removed too, so letter-spaced OCR ("R a d i a t o r") still matches
    return norm(text).replace(" ", "")


def validate(items: list[Item], sections: dict, text: dict) -> list[str]:
    """Problems with the items, as readable lines; empty when all are valid."""
    problems = []
    seen = set()
    squashed: dict[str, list[tuple[int, str]]] = {}
    for (manual, page), t in text.items():
        squashed.setdefault(manual, []).append((page, _squash(t)))

    for it in items:
        where = f"{it.id}:"
        if it.id in seen:
            problems.append(f"{where} duplicate id")
        seen.add(it.id)
        if it.manual not in sections:
            problems.append(f"{where} unknown manual {it.manual}")
            continue
        if it.category not in CATEGORIES:
            problems.append(f"{where} unknown category {it.category}")
        known = {s["id"] for s in sections[it.manual]}
        if not it.anchors:
            problems.append(f"{where} no anchors")

        if it.category == "unanswerable":
            if len(it.sections) != 1 or it.sections[0] not in known:
                problems.append(
                    f"{where} an unanswerable item names one on-topic section"
                )
            if it.gold_pages or it.key_facts:
                problems.append(
                    f"{where} an unanswerable item has no gold pages or key facts"
                )
            for a in it.anchors:
                hits = [p for p, t in squashed.get(it.manual, []) if _squash(a) in t]
                if hits:
                    problems.append(f"{where} anchor {a!r} appears on pages {hits[:5]}")
            continue

        if not it.gold_pages:
            problems.append(f"{where} no gold pages")
            continue
        if not 1 <= len(it.key_facts) <= 4:
            problems.append(f"{where} needs 1-4 key facts, has {len(it.key_facts)}")
        try:
            expect = sorted({section_of(sections, it.manual, p) for p in it.gold_pages})
        except KeyError as e:
            problems.append(f"{where} {e}")
            continue
        if sorted(it.sections) != expect:
            problems.append(
                f"{where} sections {it.sections} != gold-page sections {expect}"
            )
        gold = [_squash(text.get((it.manual, p), "")) for p in it.gold_pages]
        for a in it.anchors:
            if not any(_squash(a) in t for t in gold):
                problems.append(
                    f"{where} anchor {a!r} not on gold pages {it.gold_pages}"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("items", type=Path)
    v.add_argument("--composed", type=Path, default=ROOT / "data/ingest/composed.jsonl")
    v.add_argument("--sections", type=Path, default=ROOT / "evals/sections.json")
    args = ap.parse_args(argv)
    items = load_items(args.items)
    problems = validate(items, load_sections(args.sections), pages_text(args.composed))
    for p in problems:
        print(p)
    print(f"{len(items)} items, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
