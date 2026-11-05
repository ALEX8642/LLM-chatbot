# 004: Embedder and reranker

**Decision (2026-11-05):** keep `Qwen/Qwen3-Embedding-0.6B` and `BAAI/bge-reranker-v2-m3`, the existing defaults.
No larger model earned its cost on dev.

## How it was chosen

`evals/retrieval_select.py`, retrieval only, on the 139 answerable dev items. The rule was fixed in that file before
any run: the highest share of items with a gold page in the top 8 chunks; a larger model must beat a smaller one by
more than 1.5 points, about two items. Results: `evals/results/selection/retrieval.json`.

| Embedder | Reranker | Gold page in top 8 | All gold pages in top 8 | MRR | Candidate pool has gold | Rerank s |
|---|---|---|---|---|---|---|
| Qwen3 0.6B | bge-reranker-v2-m3 **(chosen)** | 0.957 | 0.914 | 0.819 | 0.993 | 1.9 |
| BGE-M3 | bge-reranker-v2-m3 | 0.964 | 0.921 | 0.823 | 1.000 | 3.7 |
| Qwen3 4B | bge-reranker-v2-m3 | 0.957 | 0.914 | 0.819 | 1.000 | 2.4 |
| Qwen3 0.6B | Qwen3-Reranker-4B | 0.957 | 0.928 | 0.812 | 0.993 | 5.3 |
| BGE-M3 | Qwen3-Reranker-4B | 0.950 | 0.921 | 0.813 | 1.000 | 5.6 |
| Qwen3 4B | Qwen3-Reranker-4B | 0.964 | 0.935 | 0.817 | 1.000 | 5.5 |
| Qwen3 0.6B | Qwen3-Reranker-0.6B | 0.921 | 0.885 | 0.718 | 0.993 | 2.9 |
| BGE-M3 | Qwen3-Reranker-0.6B | 0.921 | 0.878 | 0.720 | 1.000 | 2.5 |
| Qwen3 4B | Qwen3-Reranker-0.6B | 0.921 | 0.885 | 0.722 | 1.000 | 3.2 |

The best pair beats the choice by one item. Licences: Apache-2.0, except BGE-M3 (MIT).

## Limits

- **4B ran at half precision, in small batches, on the laptop's 16 GB.** Full precision and the 8B embedder were not
  run. The ceiling limits what they could add: the choice already finds a gold page for 133 of 139 items, and 4B's
  candidate pool already holds one for all 139, so a larger embedder can only help through the pool, which the
  reranker then decides. Not a measurement of those models.
- **Multi-page items lean the other way.** "All gold pages" favours Qwen3 4B + Qwen3-Reranker-4B by 3 items (0.935 vs
  0.914), at 3.6 s more reranking a question. The rule was on the first measure, so this does not change the choice.
  Multi-page is v2's weakest category (primary 0.45-0.55, 11 items), so it is worth one end-to-end test if that
  category becomes the priority.
- Retrieval only: no answer was generated or judged. Dev only; the same dev items also tuned the checks.
- The Qwen3 rerankers use the yes/no scoring written from memory of the model card, unverified against it. The 0.6B
  scoring much worse than the 4B is unexplained and could be a defect in that wrapper or in half precision on 4B.
