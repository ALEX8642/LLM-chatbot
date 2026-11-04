"""Builds the gold-answer session: a seeded, stratified sample of 60 test items, page renders,
and the page. Run from the repo root:

    PYTHONPATH=. python evals/sessions/build_gold.py OUT_DIR

Writes evals/sessions/gold_sample.json (the ids) and OUT_DIR/index.html + OUT_DIR/pages/.
"""

import json
import random
import sys
from pathlib import Path

import pymupdf

from evals.items import _squash, load_items, load_sections
from manualqa.blocks import load_pages
from manualqa.geometry import render_page

SEED = 20261104
QUOTA = {
    "table": 20,
    "single_page": 19,
    "unanswerable": 12,
    "multi_page": 5,
    "figure": 4,
}
SECTION_PAGES = 4  # unanswerables show this many pages of their on-topic section
SHORT = {"FAA": "FAA handbook", "Army_5kW_Generator_Operator": "Operator manual"}


def main(out: Path) -> None:
    items = load_items(Path("evals/test.jsonl"))
    rng = random.Random(SEED)
    sample = []
    for cat, n in QUOTA.items():
        pool = sorted((i for i in items if i.category == cat), key=lambda i: i.id)
        sample += rng.sample(pool, min(n, len(pool)))
    rng.shuffle(sample)
    Path("evals/sessions/gold_sample.json").write_text(
        json.dumps(
            {"seed": SEED, "quota": QUOTA, "ids": [i.id for i in sample]}, indent=1
        )
        + "\n"
    )
    composed = {
        (p.manual, p.page): p for p in load_pages(Path("data/ingest/composed.jsonl"))
    }
    sections = load_sections()
    (out / "pages").mkdir(parents=True, exist_ok=True)
    docs, rows, rendered = {}, [], set()
    for it in sample:
        if it.category == "unanswerable":
            s = next(x for x in sections[it.manual] if x["id"] == it.sections[0])
            numbers = list(range(s["first"], s["last"] + 1))[:SECTION_PAGES]
        else:
            numbers = it.gold_pages
        pages = []
        for n in numbers:
            stem = Path(it.manual).stem
            name = f"pages/{stem}-p{n:03d}.jpg"
            if name not in rendered:
                doc = docs.setdefault(
                    it.manual, pymupdf.open(Path("manuals") / it.manual)
                )
                render_page(doc[n - 1])[0].convert("RGB").save(out / name, quality=72)
                rendered.add(name)
            boxes = []
            if it.category != "unanswerable":
                wanted = [_squash(a) for a in it.anchors]
                for b in composed[(it.manual, n)].blocks:
                    for piece in [*b.lines, *b.cells]:
                        text = _squash(piece.text)
                        if piece.box and text and any(w in text for w in wanted):
                            x = piece.box
                            boxes.append(
                                [round(v, 4) for v in (x.x0, x.y0, x.x1, x.y1)]
                            )
            pages.append({"page": n, "src": name, "boxes": boxes[:40]})
        short = next(
            (v for k, v in SHORT.items() if it.manual.startswith(k)), "Parts manual"
        )
        rows.append(
            {
                "id": it.id,
                "category": it.category,
                "near_miss": it.near_miss,
                "question": it.question,
                "reference_answer": it.reference_answer,
                "key_facts": it.key_facts,
                "anchors": it.anchors,
                "short_manual": short,
                "pages": pages,
            }
        )
    tpl = Path("evals/sessions/gold/template.html").read_text()
    html = tpl.replace("/*ITEMS*/[]", json.dumps(rows, ensure_ascii=False))
    (out / "index.html").write_text(html)
    print(len(rows), "items,", len(rendered), "pages")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
