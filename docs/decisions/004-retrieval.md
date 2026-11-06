# 004: Embedder and reranker

**Decision (2026-11-05):** keep `Qwen/Qwen3-Embedding-0.6B`; replace the reranker with `Qwen/Qwen3-Reranker-4B`, at
half precision. Everything runs on a 16 GB GPU. Checked on a 32 GB RTX 5090: full precision changes nothing that
matters and the 8B models are no better, so the larger GPU is not needed.

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
just inside the margin, so the rule keeps the smaller embedder.

**End to end on the 172 dev items, against the old reranker:** primary 0.79 / 0.80 to 0.84 / 0.87 (phi4 / mistral),
false declines 7 to 3, unanswerable questions answered 7 to 3. p50 10 s to 13 s, p95 18 s to 42 s; see "Running it". See `evals/results/NOTES-v2-dev.md`.

Licences: Apache-2.0, except BGE-M3 (MIT).

## A bug that nearly decided this

An earlier version of this record kept the defaults, on figures that showed Qwen3-Reranker-4B no better and the 0.6B
far worse. The wrapper cut whole prompts at 1,024 tokens, so long chunks lost the prompt's end, and with it the point
where the model answers. Checking it against the model card found this. The Qwen rows above are from after the fix.

## On 32 GB

Alex prefers his 5090 over a downgraded model unless the difference does not matter, so the reduced setups were
rerun there. Same rule, same items, same chunks; `evals/results/selection/retrieval-32gb.json`.

| Embedder | Reranker | Gold page in top 8 | All gold pages in top 8 | MRR | Rerank s |
|---|---|---|---|---|---|
| Qwen3 0.6B | Qwen3-Reranker-4B, full | 0.986 | 0.957 | 0.855 | 4.5 |
| BGE-M3 | Qwen3-Reranker-4B, full | 1.000 | 0.971 | 0.861 | 4.7 |
| Qwen3 4B, full | Qwen3-Reranker-4B, full | 0.993 | 0.964 | 0.859 | 4.6 |
| Qwen3 8B, half | Qwen3-Reranker-4B, full | 0.993 | 0.964 | 0.859 | 4.7 |
| Qwen3 0.6B | Qwen3-Reranker-8B, half | 0.978 | 0.942 | 0.841 | 2.6 |
| BGE-M3 | Qwen3-Reranker-8B, half | 0.986 | 0.957 | 0.842 | 2.7 |
| Qwen3 4B, full | Qwen3-Reranker-8B, half | 0.971 | 0.935 | 0.840 | 2.7 |
| Qwen3 8B, half | Qwen3-Reranker-8B, half | 0.978 | 0.942 | 0.841 | 2.7 |

- **Full precision:** the reranker's item counts are identical to half precision on all three embedders run on both
  machines, and MRR rises by at most 0.003.
- **8B:** the 8B reranker is worse than the 4B on every embedder, and the 8B embedder matches the 4B. 8B at full
  precision would need about 32 GB for its weights alone, so it ran at half; full-precision 8B remains unrun.
- **BGE-M3, run end to end because it found a gold page for all 139 items and is faster:** primary 0.82 / 0.85 against
  0.84 / 0.87, with both judges agreeing on 2 items better and 3 worse. No gain, so it was not adopted.

## Running it

`manualqa` sets `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, which took the dev run's p95 from 42 s to 21 s on
16 GB (one run; `evals/results/NOTES-v2-dev.md`). The reranker's prompt limit stays at the model card's 8,192 tokens.

## Limits

- On 16 GB the Qwen3 rerankers and 4B embedder ran at half precision; the 4B reranker in batches of 2.
- Retrieval figures and the end-to-end run are dev only, and the same items tuned the checks.
