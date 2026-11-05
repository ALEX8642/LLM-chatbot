"""Choose the embedder and reranker on dev, by retrieval alone (no generation, no judges).

Each embedder gets its own index of the same chunks; each reranker then orders that index's
candidates for every answerable dev item. The selection rule is fixed here, before the runs:

    Highest recall of a gold page in the top 8 chunks, the number the answer path uses. A
    larger model must beat the smaller one by more than MIN_GAIN, about two of the 139
    answerable dev items; otherwise the smaller one stays, since it costs less to run.

    python -m evals.retrieval_select --ingest data/ingest --qa evals/qa.jsonl --out DIR
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from evals.items import load_items

K_CHUNKS, POOL, MIN_GAIN = 8, 50, 0.015
LARGE = 4.0  # models this size run at half precision and in small batches, to fit 16 GB
EMBEDDERS = {
    "st:Qwen/Qwen3-Embedding-0.6B": 0.6,
    "st:BAAI/bge-m3": 1.0,
    "st:Qwen/Qwen3-Embedding-4B": 4.0,
}
RERANKERS = {
    "st:BAAI/bge-reranker-v2-m3": 0.6,
    "qwen:Qwen/Qwen3-Reranker-0.6B": 0.6,
    "qwen:Qwen/Qwen3-Reranker-4B": 4.0,
}


def _free_gpu() -> None:
    import gc

    import torch

    gc.collect()
    torch.cuda.empty_cache()


def page_metrics(pages: list[int], gold: list[int]) -> dict:
    gold_set = set(gold)
    first = next((i for i, p in enumerate(pages, 1) if p in gold_set), None)
    return {
        "hit": float(first is not None),
        "rr": 1.0 / first if first else 0.0,
        "all": float(gold_set <= set(pages)),
    }


def ordered_pages(chunks: list) -> list[int]:
    return list(dict.fromkeys(p for c in chunks for p in c.pages))


def summarize(rows: list[dict]) -> dict:
    n = len(rows) or 1
    return {
        key: sum(r[key] for r in rows) / n
        for key in ("hit", "rr", "all", "candidate_hit")
    }


def choose(results: dict[tuple[str, str], dict]) -> tuple[str, str]:
    """Walk from the smallest pair; a larger pair replaces it only with more than MIN_GAIN."""
    size = lambda pair: EMBEDDERS[pair[0]] + RERANKERS[pair[1]]  # noqa: E731
    best = None
    for pair in sorted(results, key=lambda p: (size(p), p)):
        if best is None or results[pair]["hit"] > results[best]["hit"] + MIN_GAIN:
            best = pair
    return best


def main(argv: list[str] | None = None) -> int:
    from manualqa.chunks import load_chunks
    from manualqa.index import build_index, make_embedder, search
    from manualqa.retrieve import make_reranker

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ingest", type=Path, required=True)
    ap.add_argument("--qa", type=Path, default=Path("evals/qa.jsonl"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    items = [i for i in load_items(args.qa) if i.category != "unanswerable"]
    chunks = load_chunks(args.ingest / "chunks.jsonl")

    pools: dict[str, dict[str, list]] = {}
    costs: dict[str, dict] = {}
    failed: dict[str, str] = {}
    for spec, size in EMBEDDERS.items():
        where = args.out / spec.replace("/", "_").replace(":", "_")
        try:
            embedder = make_embedder(
                spec, half=size >= LARGE, batch_size=2 if size >= LARGE else 16
            )
            start = time.perf_counter()
            build_index(chunks, where, embedder)
            built = time.perf_counter() - start
            start = time.perf_counter()
            pools[spec] = {
                it.id: [
                    c
                    for c, _ in search(
                        it.question, where, embedder, k=POOL, manual=it.manual
                    )
                ]
                for it in items
            }
            costs[spec] = {
                "index_s": built,
                "query_s": (time.perf_counter() - start) / len(items),
            }
            print(f"embedded {spec} {costs[spec]}", flush=True)
        except RuntimeError as e:  # out of GPU memory: report it, keep the others
            failed[spec] = str(e)[:200]
            print(f"failed {spec} {failed[spec]}", flush=True)
        embedder = None
        _free_gpu()

    results: dict[tuple[str, str], dict] = {}
    for spec, size in RERANKERS.items():
        try:
            reranker = make_reranker(spec, batch_size=2 if size >= LARGE else 8)
            for emb, pool in pools.items():
                rows = []
                start = time.perf_counter()
                for it in items:
                    cands = pool[it.id]
                    got = (
                        reranker.score(it.question, [c.text for c in cands])
                        if cands
                        else []
                    )
                    ranked = [
                        c for _, c in sorted(zip(got, cands), key=lambda p: -p[0])
                    ][:K_CHUNKS]
                    row = page_metrics(ordered_pages(ranked), it.gold_pages)
                    row["candidate_hit"] = page_metrics(
                        ordered_pages(cands), it.gold_pages
                    )["hit"]
                    row["id"], row["category"] = it.id, it.category
                    rows.append(row)
                summary = summarize(rows)
                summary["rerank_s"] = (time.perf_counter() - start) / len(items)
                results[(emb, spec)] = summary
                with (args.out / "per_item.jsonl").open("a") as f:
                    f.write(
                        json.dumps({"embedder": emb, "reranker": spec, "rows": rows})
                        + "\n"
                    )
                print(emb, spec, json.dumps(summary), flush=True)
        except RuntimeError as e:
            failed[spec] = str(e)[:200]
            print(f"failed {spec} {failed[spec]}", flush=True)
        reranker = None
        _free_gpu()

    chosen = choose(results)
    report = {
        "items": len(items),
        "chosen": chosen,
        "failed": failed,
        "costs": costs,
        "results": [
            {"embedder": e, "reranker": r, **m} for (e, r), m in sorted(results.items())
        ],
    }
    (args.out / "summary.json").write_text(json.dumps(report, indent=1))
    print("chosen", chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
