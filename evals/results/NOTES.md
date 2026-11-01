# v1 baseline (2026-11-01)

v1 at tag `v1`, unchanged, scored on the 42 questions in `evals/qa.jsonl`. Every number below is
generated from `evals/results/v1.json` and `evals/results/v1-strict.json`; the answers behind them
are in `evals/results/raw/`.

## Setup

- **Generator:** Command R7B (`command-r7b:latest`, Q4_K_M, digest `ff4e9696ef9f`) on Ollama 0.40.13,
  RTX 4090 Laptop GPU. v1 sets no sampling options, so Ollama's defaults apply (temperature 0.8,
  4,096-token context). Each mode was run 3 times; cells show the mean and, where runs differ, the
  (min–max) range across the 3 runs.
- **Retrieval:** v1 defaults: all-MiniLM-L6-v2 dense (Qdrant) + BM25 (OpenSearch), top 30 each,
  reciprocal rank fusion, ms-marco-MiniLM-L-6-v2 cross-encoder to 5, MMR over those 5, score gate 0.35.
  639 chunks (250 words, 50 overlap) from PyMuPDF text.
- **Modes:** `v1` is the UI default (guardrails off: if no excerpt passes the gate, the top one is used
  anyway). `v1-strict` is guardrails on (only excerpts above the gate; none means an empty context).
- **Judge:** `Qwen3.8-Flash-Next-NVFP4-Fast` through an OpenAI-compatible gateway, temperature 0, seed 0.

## Results

| Metric | v1 (default) | v1-strict |
|---|---|---|
| Recall@1 | 0.53 | 0.53 |
| Recall@5 | 0.89 | 0.89 |
| Recall@10 | 0.89 | 0.89 |
| MRR | 0.67 | 0.67 |
| Candidate recall (pre-rerank) | 0.94 | 0.94 |
| Citation hit | 0.69 | 0.61 |
| Citation precision | 0.47 | 0.38 |
| Correctness | 0.49 (0.47–0.53) | 0.40 (0.36–0.43) |
| Faithfulness | 0.48 (0.44–0.51) | 0.53 (0.50–0.56) |
| Abstention precision | 0.35 (0.27–0.40) | 0.25 (0.24–0.26) |
| Abstention recall | 0.56 (0.50–0.67) | 0.72 (0.67–0.83) |
| False abstentions (of 36) | 6.33 (5.00–8.00) | 13.00 (12.00–14.00) |
| Latency p50 (s) | 2.38 (2.27–2.44) | 2.13 (2.10–2.19) |
| Latency p95 (s) | 6.12 (5.91–6.48) | 6.85 (6.49–7.38) |

**v1 (default) by category**

| Category | n | Recall@5 | Correctness | Faithfulness |
|---|---|---|---|---|
| figure | 5 | 1.00 | 0.20 | 0.35 (0.17–0.50) |
| multi_page | 5 | 0.80 | 0.57 (0.50–0.60) | 0.43 (0.40–0.50) |
| single_page | 14 | 0.86 | 0.70 (0.64–0.75) | 0.73 (0.67–0.82) |
| table | 12 | 0.92 | 0.33 (0.25–0.42) | 0.35 (0.33–0.36) |
| unanswerable | 6 | — | — | 0.11 (0.00–0.17) |

**v1 (default) by manual**

| Manual | n | Recall@5 | Correctness | Faithfulness |
|---|---|---|---|---|
| Army_5kW_Generator_Operator_Manual | 17 | 0.80 | 0.49 (0.43–0.53) | 0.50 (0.42–0.54) |
| Army_5kW_Generator_Parts_Manual | 8 | 0.83 | 0.03 (0.00–0.08) | 0.06 (0.00–0.10) |
| FAA_Weight_and_Balance_Handbook | 17 | 1.00 | 0.68 (0.60–0.73) | 0.64 (0.57–0.71) |

Per-manual rows count all items for that manual (unanswerable included in n); recall is over
answerable items only.

## What the baseline shows

- **Retrieval is not the main problem; reading is.** A gold page is in the final 5 for 89% of
  answerable questions, yet only about half the answers are correct. On the parts manual, recall@5 is
  0.83 and correctness is 0.03: plain-text extraction flattens each parts table to one value per line,
  and the model mismatches columns (for example, it gave the CAGE code 18265 as the filter element's
  part number).
- **Figure questions retrieve well and fail anyway.** Recall@5 is 1.00 because captions and
  surrounding text are indexed, but correctness is 0.20: the values live in the image (the rating plate,
  the loading graph, the image-only equipment list page).
- **The relevance gate hurts more than it helps.** It discards correct pages that the reranker ranked
  first (for example, faa-03: page 26 ranked first, dropped by the 0.35 gate, answer "not in the
  excerpt"). Strict mode lowers correctness from 0.49 to 0.40 and doubles false abstentions (6.3 to 13),
  while catching more unanswerable items (abstention recall 0.56 to 0.72).
- **v1 confidently answers questions the manual does not cover.** For example, it gave a Cessna 172S
  useful load taken from an unrelated revision-record example, and an "engine oil viscosity grade" that
  is actually a diesel fuel specification.
- **MMR is a no-op as configured**, as the v1 review predicted: recall@5 equals recall@10 and the
  final list is never longer than the reranker's 5.

## Judge spot-check

Twelve gradings from the first `v1` run were checked by hand (faa-03, faa-07, faa-14, op-03, op-10,
op-14, parts-01, parts-02, parts-05, unans-02, unans-03, unans-05).

- **Correctness and abstention: 11 of 12 agree.** Disagreement: unans-05 (turbocharger part number).
  The answer says the excerpts do not list it and points to the manual's indexes; the judge marked it
  as not abstaining and incorrect. A human would count it as a correct decline.
- **Faithfulness: 5 of 8 judged items agree.** Disagreements: op-03 (a reasoning step, "divide capacity
  by consumption", was listed as an unsupported claim); parts-01 (the part number 105-269 is in the
  excerpt, but the judge could not match it in the flattened table and called it unsupported); unans-05
  (the statement that the excerpts lack the information was listed as a claim, contrary to the prompt).

The judge is therefore reliable for correctness and noisy for faithfulness, and it under-counts
faithfulness on flattened tables. These gradings are reported as is; the judge was not tuned on v1.
