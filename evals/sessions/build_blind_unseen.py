"""Blind grading for the unseen-manual test (docs/prereg-unseen.md, step 3): the answers the
judges dispute, plus controls, one screen per answer, system hidden, order shuffled.

Selection, fixed before grading (first repeat; v2 is deterministic across repeats):
- v1 answers phi4 judged correct but unsupported while mistral passed them (the judge split);
- every v2 answer phi4 failed;
- controls: CONTROLS answers per system drawn at random from those both judges passed.

    PYTHONPATH=. python evals/sessions/build_blind_unseen.py RAW_DIR OUT_DIR KEY_FILE

RAW_DIR holds v1-fist.json, v2-fist.json and their -phi4/-mistral judged files.
"""

import json
import random
import secrets
import sys
from pathlib import Path

import pymupdf

from evals.items import load_items
from manualqa.geometry import render_page

SEED, CONTROLS, MAX_PAGES = 20261110, 8, 4
MANUALS = Path("evals/unseen/manuals")


def first(path: Path, key: str) -> dict:
    return {r["id"]: r for r in json.loads(path.read_text())["repeats"][0][key]}


def select(raw: Path) -> dict[str, list[tuple[str, str]]]:
    g = {
        (s, j): {
            r["id"]: r
            for r in json.loads((raw / f"{s}-fist-{j}.json").read_text())["repeats"][0][
                "items"
            ]
        }
        for s in ("v1", "v2")
        for j in ("phi4", "mistral")
    }
    split = sorted(
        i
        for i, r in g["v1", "phi4"].items()
        if r["correct"] and not r["primary"] and g["v1", "mistral"][i]["primary"]
    )
    v2_fail = sorted(i for i, r in g["v2", "phi4"].items() if not r["primary"])
    rng = random.Random(SEED)
    controls = []
    for s in ("v1", "v2"):
        passed = sorted(
            i
            for i, r in g[s, "phi4"].items()
            if r["primary"] and g[s, "mistral"][i]["primary"]
        )
        controls += [(s, i) for i in rng.sample(passed, CONTROLS)]
    return {
        "v1: correct, phi4 rejects support, mistral passes": [("v1", i) for i in split],
        "v2: failed by phi4": [("v2", i) for i in v2_fail],
        "controls: passed by both judges": controls,
    }


def main(raw: Path, out: Path, key_file: Path) -> None:
    items = {it.id: it for it in load_items(Path("evals/unseen/fist.jsonl"))}
    answers = {
        s: {
            r["id"]: r
            for r in json.loads((raw / f"{s}-fist.json").read_text())["repeats"][0]
        }
        for s in ("v1", "v2")
    }
    groups = select(raw)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    rendered, screens, key, docs = set(), [], {}, {}
    for system, item_id in [x for g in groups.values() for x in g]:
        it, ans = items[item_id], answers[system][item_id]
        pages = []
        for n in list(dict.fromkeys(ans.get("cited_pages") or []))[:MAX_PAGES]:
            name = f"pages/{Path(it.manual).stem}-p{n:03d}.jpg"
            if name not in rendered:
                doc = docs.setdefault(it.manual, pymupdf.open(MANUALS / it.manual))
                render_page(doc[n - 1])[0].convert("RGB").save(out / name, quality=70)
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
                "answer": ans["answer"].strip(),
                "manual": "FIST 3-30 Transformer Maintenance",
                "pages": pages,
            }
        )
    random.Random(SEED + 1).shuffle(screens)
    key_file.write_text(
        json.dumps(
            {"seed": SEED, "groups": {k: v for k, v in groups.items()}, "screens": key},
            indent=1,
        )
        + "\n"
    )
    html = Path("evals/sessions/blind/template.html").read_text()
    (out / "index.html").write_text(
        html.replace("/*SCREENS*/[]", json.dumps(screens, ensure_ascii=False))
    )
    print(
        len(screens),
        "screens,",
        len(rendered),
        "pages",
        {k: len(v) for k, v in groups.items()},
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
