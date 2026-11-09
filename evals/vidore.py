"""v2's retrieval on ViDoRe V3's industrial manuals (decision 005): NDCG@10 over pages.

Uses the corpus's own page markdown, not v2's parser, so it measures retrieval alone: the
registered embedder, BM25, fusion and reranker, unchanged. English queries only.

    python -m evals.vidore --out DIR
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path

REPO = "vidore/vidore_v3_industrial"
K, POOL, CHUNK_CHARS = 10, 50, 1500
CORPUS = "vidore-industrial"


def page_chunks(corpus_id: int, markdown: str) -> list[tuple[str, str]]:
    """(chunk id, text) pieces of one page, split at paragraphs to at most CHUNK_CHARS."""
    pieces, current = [], ""
    for para in markdown.split("\n\n"):
        if current and len(current) + len(para) + 2 > CHUNK_CHARS:
            pieces.append(current)
            current = ""
        current = f"{current}\n\n{para}" if current else para
        while len(current) > CHUNK_CHARS:
            pieces.append(current[:CHUNK_CHARS])
            current = current[CHUNK_CHARS:]
    if current.strip():
        pieces.append(current)
    return [(f"{corpus_id}:{n}", text) for n, text in enumerate(pieces)]


def ranked_pages(scored: list[tuple[float, int]]) -> list[int]:
    """Pages ordered by their best chunk score."""
    best: dict[int, float] = {}
    for score, page in scored:
        best[page] = max(best.get(page, -math.inf), score)
    return sorted(best, key=lambda p: -best[p])


def ndcg(ranked: list[int], gains: dict[int, int], k: int = K) -> float:
    """NDCG@k with linear gains, as trec_eval and MTEB compute it."""
    dcg = sum(gains.get(p, 0) / math.log2(i + 2) for i, p in enumerate(ranked[:k]))
    ideal = sorted(gains.values(), reverse=True)[:k]
    best = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / best if best else 0.0


def recall(ranked: list[int], gains: dict[int, int], k: int = K) -> float:
    relevant = {p for p, g in gains.items() if g > 0}
    return len(relevant & set(ranked[:k])) / len(relevant) if relevant else 0.0


def main(argv: list[str] | None = None) -> int:
    import pandas as pd
    from huggingface_hub import snapshot_download

    from manualqa.chunks import Chunk
    from manualqa.index import build_index, make_embedder, search
    from manualqa.retrieve import make_reranker

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--embedder", default="st:Qwen/Qwen3-Embedding-0.6B")
    ap.add_argument("--reranker", default="qwen:Qwen/Qwen3-Reranker-4B")
    ap.add_argument(
        "--limit", type=int, help="first N English queries, for a smoke run"
    )
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    root = Path(snapshot_download(REPO, repo_type="dataset"))
    corpus = pd.concat(
        pd.read_parquet(f, columns=["corpus_id", "doc_id", "markdown"])
        for f in sorted(root.glob("corpus/*.parquet"))
    )
    queries = pd.read_parquet(next(root.glob("queries/*.parquet")))
    qrels = pd.read_parquet(next(root.glob("qrels/*.parquet")))
    queries = queries[queries["language"] == "english"]
    if args.limit:
        queries = queries.head(args.limit)
    gains: dict[int, dict[int, int]] = defaultdict(dict)
    for r in qrels.itertuples():
        gains[r.query_id][r.corpus_id] = int(r.score)

    chunks = [
        Chunk(cid, CORPUS, [int(r.corpus_id)], "text", str(r.doc_id), text)
        for r in corpus.itertuples()
        for cid, text in page_chunks(int(r.corpus_id), r.markdown or "")
    ]
    embedder = make_embedder(args.embedder)
    start = time.perf_counter()
    build_index(chunks, args.out / "qdrant", embedder)
    index_s = time.perf_counter() - start
    reranker = make_reranker(args.reranker, batch_size=2)

    rows = []
    for q in queries.itertuples():
        g = gains.get(q.query_id, {})
        if not g:
            continue
        start = time.perf_counter()
        found = [c for c, _ in search(q.query, args.out / "qdrant", embedder, k=POOL)]
        first = ranked_pages([(-i, c.pages[0]) for i, c in enumerate(found)])
        scores = reranker.score(q.query, [c.text for c in found]) if found else []
        final = ranked_pages([(s, c.pages[0]) for s, c in zip(scores, found)])
        rows.append(
            {
                "query_id": int(q.query_id),
                "ndcg10": ndcg(final, g),
                "recall10": recall(final, g),
                "first_stage_ndcg10": ndcg(first, g),
                "seconds": round(time.perf_counter() - start, 2),
            }
        )
    n = len(rows)
    summary = {
        "corpus": REPO,
        "queries": n,
        "pages": int(corpus["corpus_id"].nunique()),
        "chunks": len(chunks),
        "embedder": args.embedder,
        "reranker": args.reranker,
        "ndcg10": sum(r["ndcg10"] for r in rows) / n,
        "recall10": sum(r["recall10"] for r in rows) / n,
        "first_stage_ndcg10": sum(r["first_stage_ndcg10"] for r in rows) / n,
        "index_s": round(index_s, 1),
        "seconds_per_query": sum(r["seconds"] for r in rows) / n,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    (args.out / "per_query.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
