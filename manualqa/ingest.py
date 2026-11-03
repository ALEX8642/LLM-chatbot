"""Ingest raw parses into everything the answer path reads.

    uv run python -m manualqa.ingest --raw data/raw/paddle/parses.jsonl \\
        --manuals manuals --out data/ingest [--embedder st:Qwen/Qwen3-Embedding-0.6B]

Writes ``composed.jsonl``, ``tables.sqlite``, ``chunks.jsonl``, ``pages/`` and ``qdrant/``
under ``--out``, and ``summary.json`` with counts and timings. Every step is CPU-only except
the embeddings.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import pymupdf

from manualqa.blocks import dump_pages, load_pages
from manualqa.chunks import chunk_manual, dump_chunks
from manualqa.compose import compose_page
from manualqa.render import render_manual
from manualqa.tables import TableStore


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--manuals", type=Path, default=Path("manuals"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--embedder", default="st:Qwen/Qwen3-Embedding-0.6B")
    ap.add_argument("--skip-index", action="store_true")
    args = ap.parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    t = time.perf_counter()
    raw = sorted(load_pages(args.raw), key=lambda p: (p.manual, p.page))
    composed = []
    for manual in sorted({p.manual for p in raw}):
        with pymupdf.open(args.manuals / manual) as doc:
            for p in raw:
                if p.manual == manual:
                    composed.append(p if p.error else compose_page(p, doc[p.page - 1]))
    dump_pages(composed, out / "composed.jsonl")
    timings["compose"] = time.perf_counter() - t

    t = time.perf_counter()
    db = out / "tables.sqlite"
    db.unlink(missing_ok=True)
    store = TableStore(db)
    for pp in composed:
        store.add_page(pp)
    rows = store.db.execute("SELECT COUNT(*), COUNT(row_box) FROM rows").fetchone()
    n_tables = store.db.execute("SELECT COUNT(*) FROM tables").fetchone()[0]
    timings["tables"] = time.perf_counter() - t

    t = time.perf_counter()
    chunks = []
    for manual in sorted({p.manual for p in composed}):
        chunks += chunk_manual([p for p in composed if p.manual == manual])
    dump_chunks(chunks, out / "chunks.jsonl")
    timings["chunks"] = time.perf_counter() - t

    t = time.perf_counter()
    for manual in sorted({p.manual for p in composed}):
        pages = [p.page for p in composed if p.manual == manual]
        render_manual(args.manuals / manual, out / "pages", pages=pages)
    timings["renders"] = time.perf_counter() - t

    if not args.skip_index:
        from manualqa.index import build_index, make_embedder

        t = time.perf_counter()
        embedder = make_embedder(args.embedder)
        build_index(chunks, out / "qdrant", embedder)
        timings["index"] = time.perf_counter() - t

    cells = [
        c for p in composed for b in p.blocks if b.kind == "table" for c in b.cells
    ]
    filled = [c for c in cells if c.text.strip()]
    summary = {
        "pages": len(composed),
        "errors": sum(p.error is not None for p in composed),
        "text_source": dict(Counter(p.text_source for p in composed if not p.error)),
        "blocks": dict(Counter(b.kind for p in composed for b in p.blocks)),
        "chunks": len(chunks),
        "chunks_by_kind": dict(Counter(c.kind for c in chunks)),
        "tables": n_tables,
        "rows": rows[0],
        "row_boxes": rows[1],
        "cells_nonempty": len(filled),
        "cells_with_boxes": sum(c.box is not None for c in filled),
        "embedder": None if args.skip_index else args.embedder,
        "seconds": {k: round(v, 1) for k, v in timings.items()},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
