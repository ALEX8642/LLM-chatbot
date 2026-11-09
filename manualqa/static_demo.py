"""A static copy of the replay demo, for GitHub Pages: the recorded answers, the manuals
they come from, and every page they point to, rendered from the manuals in the repo.

    uv run --no-project --with pymupdf --with pillow \
        python -m manualqa.static_demo docs/demo/replay.jsonl frontend/dist/demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf

from manualqa.catalogue import read_manuals
from manualqa.geometry import render_page
from manualqa.render import DISPLAY_DPI


def pages_used(events: list[dict]) -> set[int]:
    """Every page an answer shows: its claims' pages and the pages it lists."""
    out: set[int] = set()
    for e in events:
        data = e.get("data") or {}
        if data.get("page"):
            out.add(data["page"])
        out.update(data.get("pages") or [])
    return out


def build(replay: Path, out: Path, manuals: Path = Path("manuals")) -> dict:
    """Write answers.json, manuals.json and pages/<stem>/pNNN.jpg under ``out``."""
    answers = [
        {"question": r["question"], "manual": r["manual"], "events": r["events"]}
        for r in map(json.loads, Path(replay).read_text().splitlines())
        if not r["history"]  # the static page asks each question on its own
    ]
    files = {a["manual"] for a in answers}
    catalogue = [m for m in read_manuals(manuals) if m["file"] in files]
    missing = files - {m["file"] for m in catalogue}
    if missing:
        raise ValueError(f"not in {manuals}/SOURCES.md: {sorted(missing)}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "answers.json").write_text(json.dumps(answers, ensure_ascii=False))
    (out / "manuals.json").write_text(json.dumps(catalogue, ensure_ascii=False))
    rendered = {}
    for m in catalogue:
        pdf = Path(manuals) / m["file"]
        pages = sorted(
            {
                p
                for a in answers
                if a["manual"] == m["file"]
                for p in pages_used(a["events"])
            }
        )
        target = out / "pages" / pdf.stem
        target.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(pdf) as doc:
            for n in pages:
                img, _ = render_page(doc[n - 1], dpi=DISPLAY_DPI)
                img.save(target / f"p{n:03d}.jpg", quality=80)
        rendered[m["file"]] = pages
    return rendered


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("replay", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--manuals", type=Path, default=Path("manuals"))
    args = ap.parse_args()
    for manual, pages in build(args.replay, args.out, args.manuals).items():
        print(f"{manual}: {len(pages)} pages")


if __name__ == "__main__":
    main()
