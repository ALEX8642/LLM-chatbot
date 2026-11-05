# 004: Embedder and reranker

**Decision (2026-11-05):** keep `Qwen/Qwen3-Embedding-0.6B`; replace the reranker with `Qwen/Qwen3-Reranker-4B`, at
half precision on 16 GB. **Provisional:** full precision and the 8B models have not been run. They need the 32 GB 5090,
which Alex prefers to a downgraded model unless the difference does not matter.

## How it was chosen

`evals/retrieval_select.py`, retrieval only, on the 139 answerable dev items. The rule was fixed in that file before
any run: the highest share of items with a gold page in the top 8 chunks; a larger model must beat a smaller one by
more than 1.5 points, about two items. Results: `evals/results/selection/retrieval.json`.

| Embedder | Reranker | Gold page in top 8 | All gold pages in top 8 | MRR | Candidate pool has gold | Rerank s |
|---|---|---|---|---|---|---|
| Qwen3 0.6B | bge-reranker-v2-m3 | 0.957 | 0.914 | 0.819 | 0.993 | 1.9 |
| BGE-M3 | bge-reranker-v2-m3 | 0.964 | 0.921 | 0.823 | 1.000 | 3.7 |
| Qwen3 4B | bge-reranker-v2-m3 | 0.957 | 0.914 | 0.819 | 1.000 | 2.4 |
| Qwen3 0.6B | Qwen3-Reranker-0.6B | 0.964 | 0.928 | 0.762 | 0.993 | 12.6 |
| BGE-M3 | Qwen3-Reranker-0.6B | 0.964 | 0.928 | 0.765 | 1.000 | 11.2 |
| Qwen3 4B | Qwen3-Reranker-0.6B | 0.964 | 0.928 | 0.765 | 1.000 | 13.6 |
| Qwen3 0.6B | Qwen3-Reranker-4B **(chosen)** | 0.986 | 0.957 | 0.852 | 0.993 | 5.6 |
| BGE-M3 | Qwen3-Reranker-4B | 1.000 | 0.971 | 0.858 | 1.000 | 5.7 |
| Qwen3 4B | Qwen3-Reranker-4B | 0.993 | 0.964 | 0.855 | 1.000 | 5.5 |

BGE-M3 with the same reranker finds a gold page for all 139 items, two more than the choice. That is 1.44 points,
just inside the margin, so the rule keeps the smaller embedder. Close enough to retest with the 5090's results.

**End to end on the 172 dev items, against the old reranker:** primary 0.79 / 0.80 to 0.84 / 0.87 (phi4 / mistral),
false declines 7 to 3, unanswerable questions answered 7 to 3. p50 10 s to 13 s, p95 18 s to 42 s; the slowest items spend 31-57 s in retrieval, on
the parts manual. See `evals/results/NOTES-v2-dev.md`.

Licences: Apache-2.0, except BGE-M3 (MIT).

## A bug that nearly decided this

An earlier version of this record kept the defaults, on figures that showed Qwen3-Reranker-4B no better and the 0.6B
far worse. The wrapper cut whole prompts at 1,024 tokens, so long chunks lost the prompt's end, and with it the point
where the model answers. Checking it against the model card found this. The Qwen rows above are from after the fix.

## Limits

- All Qwen3 rerankers ran at half precision; the 4B ones in batches of 2. The 4B embedder also ran at half precision.
- Not run: full precision, the 8B embedder, the 8B reranker (not among the spec's candidates, but it exists).
- If a 5090-only model wins by a meaningful margin, the spec's aim that a stranger can reproduce the system on 16 GB
  needs the best 16 GB setup reported beside it.
- Retrieval figures and the end-to-end run are dev only, and the same items tuned the checks.
