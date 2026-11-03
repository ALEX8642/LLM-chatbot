"""Builds evals/sections.json from the manuals' PDF outlines (run from the repo root).

FAA chapters, operator chapter sections and parts figure groups (each group starting at
its first figure page, so a figure and its parts list share a section). FAA and operator
sections longer than 6 pages are cut at bookmark pages into pieces of at least 3 pages.
"""

import json
import re

import pymupdf


def ranges(starts, last):
    out = []
    for i, (sid, title, first) in enumerate(starts):
        end = starts[i + 1][2] - 1 if i + 1 < len(starts) else last
        out.append({"id": sid, "title": title, "first": first, "last": end})
    return out


faa = (
    [("faa-fm", "Front matter", 1)]
    + [
        (f"faa-ch{n}", t, p)
        for n, t, p in [
            (1, "Weight and Balance Control", 15),
            (2, "Weight and Balance Theory", 21),
            (3, "Weighing the Aircraft and Determining the Empty Weight CG", 33),
            (4, "Light Sport Aircraft Weight and Balance Control", 43),
            (5, "Single-Engine Aircraft Weight and Balance Computations", 49),
            (6, "Multiengine Aircraft Weight and Balance Computations", 55),
            (7, "Center of Gravity Change After a Repair or Alteration", 61),
            (8, "Weight and Balance Control—Helicopter", 69),
            (9, "Weight and Balance Control—Commuter Category and Large Aircraft", 73),
            (10, "Use of Computer for Weight and Balance Computations", 93),
        ]
    ]
    + [
        ("faa-app", "Appendices A and B", 101),
        ("faa-gloss", "Glossary", 105),
        ("faa-index", "Index", 111),
    ]
)

op = [
    ("op-fm", "Front matter", 1),
    ("op-1-1", "Chapter 1 Section I", 15),
    ("op-1-2", "Chapter 1 Section II", 18),
    ("op-1-3", "Chapter 1 Section III", 25),
    ("op-2-1", "Chapter 2 Section I", 31),
    ("op-2-2", "Chapter 2 Section II", 38),
    ("op-2-3a", "Chapter 2 Section III (to para 2-9)", 46),
    (
        "op-2-3b",
        "Chapter 2 Section III (para 2-10 on)",
        50,
    ),
    ("op-2-4", "Chapter 2 Section IV", 62),
    ("op-3-12", "Chapter 3 Sections I-II", 68),
    ("op-3-3", "Chapter 3 Section III", 77),
    ("op-app", "Appendices A-D", 83),
    ("op-index", "Index", 90),
]

d = pymupdf.open("manuals/Army_5kW_Generator_Parts_Manual.pdf")
toc = d.get_toc()
fig = {int(m.group(1)): p for _, t, p in toc if (m := re.fullmatch(r"FIGURE (\d+)", t))}
lst = {int(m.group(1)): p for _, t, p in toc if (m := re.fullmatch(r"PAGE (\d+)-1", t))}
groups = [(int(t.split()[1]), p) for _, t, p in toc if re.fullmatch(r"GROUP \d+", t)]
parts = [("parts-fm", "Front matter", 1), ("parts-intro", "Section I", 5)]
for g, p in groups:
    first_fig = min((n for n, lp in lst.items() if lp == p), default=None)
    start = fig[first_fig] if first_fig and fig[first_fig] < p else p
    parts.append((f"parts-g{g:02d}", f"Group {g:02d}", start))
parts.append(("parts-index", "Section IV (index)", 93))

MAX, MIN = (
    6,
    3,
)  # sections longer than MAX pages are cut at bookmark pages into pieces >= MIN


def refine(secs, pdf, keep=("fm", "index", "gloss", "app")):
    marks = sorted({p for _, _, p in pymupdf.open(pdf).get_toc() if p > 0})
    out = []
    for s in secs:
        n = s["last"] - s["first"] + 1
        if n <= MAX or s["id"].split("-")[-1] in keep:
            out.append(s)
            continue
        cuts, start = [], s["first"]
        for m in marks:
            if start + MIN <= m <= s["last"] - MIN + 1:
                cuts.append(m)
                start = m
        bounds = [s["first"], *cuts, s["last"] + 1]
        for i in range(len(bounds) - 1):
            out.append(
                {
                    "id": f"{s['id']}.{i + 1}",
                    "title": f"{s['title']} (part {i + 1})",
                    "first": bounds[i],
                    "last": bounds[i + 1] - 1,
                }
            )
    return out


out = {
    "FAA_Weight_and_Balance_Handbook.pdf": refine(
        ranges(faa, 114), "manuals/FAA_Weight_and_Balance_Handbook.pdf"
    ),
    "Army_5kW_Generator_Operator_Manual.pdf": refine(
        ranges(op, 101), "manuals/Army_5kW_Generator_Operator_Manual.pdf"
    ),
    "Army_5kW_Generator_Parts_Manual.pdf": ranges(parts, 148),
}
with open("evals/sections.json", "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
    f.write("\n")
for m, ss in out.items():
    print(m)
    [print("  ", s["id"], s["first"], s["last"], s["title"][:50]) for s in ss]
