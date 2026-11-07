"""Builds the blind grading session registered in docs/prereg.md: 50 test items, each with v1's
and v2's first-repeat answers shown as separate screens, system hidden, order shuffled.

The sample takes, in order: correct v1 answers the judge rejected on source support; items on
which the two judges disagree about v2; correct v2 answers rejected on source support; then a
seeded random fill. Run from the repo root:

    PYTHONPATH=. python evals/sessions/build_blind.py OUT_DIR KEY_FILE

Writes OUT_DIR/index.html and OUT_DIR/pages/. KEY_FILE says which system wrote each screen;
keep it away from the grader until the session is over.
"""

import json
import random
import secrets
import sys
from pathlib import Path

import pymupdf

from evals.items import load_items
from manualqa.geometry import render_page

SEED, ITEMS, MAX_PAGES = 20261107, 50, 4
SHORT = {"FAA": "FAA handbook", "Army_5kW_Generator_Operator": "Operator manual"}
RESULTS = Path("evals/results")


def first_repeat(path: Path) -> dict:
    return {r["id"]: r for r in json.loads(path.read_text())["repeats"][0]}


def graded(system: str, judge: str) -> dict:
    data = json.loads((RESULTS / "test" / f"{system}-test-{judge}.json").read_text())
    return {r["id"]: r for r in data["repeats"][0]["items"]}


def sample_ids(items: list) -> tuple[list[str], dict]:
    v1, v2 = graded("v1", "phi4"), graded("v2", "phi4")
    v2m = graded("v2", "mistral")
    groups = {
        "v1 correct, rejected on support": [
            i for i, r in v1.items() if r["correct"] and not r["primary"]
        ],
        "judges disagree on v2": [
            i
            for i in v2
            if v2[i]["primary"] != v2m[i]["primary"]
            or v2[i]["abstained"] != v2m[i]["abstained"]
        ],
        "v2 correct, rejected on support": [
            i for i, r in v2.items() if r["correct"] and not r["primary"]
        ],
    }
    chosen: list[str] = []
    for ids in groups.values():
        chosen += [i for i in sorted(ids) if i not in chosen]
    rng = random.Random(SEED)
    rest = sorted(it.id for it in items if it.id not in chosen)
    chosen += rng.sample(rest, max(0, ITEMS - len(chosen)))
    return chosen[: max(ITEMS, len(chosen))], groups


def main(out: Path, key_file: Path) -> None:
    items = {it.id: it for it in load_items(Path("evals/test.jsonl"))}
    answers = {
        "v1": first_repeat(RESULTS / "raw" / "v1-test.json"),
        "v2": first_repeat(RESULTS / "raw" / "v2-test.json"),
    }
    ids, groups = sample_ids(list(items.values()))
    rng = random.Random(SEED + 1)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    docs, rendered, screens, key = {}, set(), [], {}
    for item_id in ids:
        it = items[item_id]
        for system in ("v1", "v2"):
            out_ = answers[system][item_id]
            pages = []
            for n in list(dict.fromkeys(out_.get("cited_pages") or []))[:MAX_PAGES]:
                name = f"pages/{Path(it.manual).stem}-p{n:03d}.jpg"
                if name not in rendered:
                    doc = docs.setdefault(
                        it.manual, pymupdf.open(Path("manuals") / it.manual)
                    )
                    image = render_page(doc[n - 1])[0].convert("RGB")
                    image.save(out / name, quality=70)
                    rendered.add(name)
                pages.append({"page": n, "src": name})
            code = secrets.token_hex(4)
            key[code] = {"item": item_id, "system": system}
            screens.append(
                {
                    "code": code,
                    "item": item_id,
                    "question": it.question,
                    "unanswerable": it.category == "unanswerable",
                    "reference_answer": it.reference_answer,
                    "key_facts": it.key_facts,
                    "answer": out_["answer"].strip(),
                    "manual": next(
                        (v for k, v in SHORT.items() if it.manual.startswith(k)),
                        "Parts manual",
                    ),
                    "pages": pages,
                }
            )
    rng.shuffle(screens)
    key_file.write_text(
        json.dumps(
            {
                "seed": SEED,
                "items": ids,
                "groups": {k: sorted(v) for k, v in groups.items()},
                "screens": key,
            },
            indent=1,
        )
        + "\n"
    )
    html = Path("evals/sessions/blind/template.html").read_text()
    html = html.replace("/*SCREENS*/[]", json.dumps(screens, ensure_ascii=False))
    (out / "index.html").write_text(html)
    print(len(ids), "items,", len(screens), "screens,", len(rendered), "pages")
    print({k: len(v) for k, v in groups.items()})


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
