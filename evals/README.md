# Evaluation

Every number in the project README comes from a results file in `evals/results/`, produced by
`evals/run_eval.py` from the questions in `evals/qa.jsonl`.

## Data

- **Corpus:** the three public manuals in `manuals/` (sources and licences in `manuals/SOURCES.md`).
- **Questions:** 42 items in `qa.jsonl`. Each has the manual it targets, a category, the 1-based PDF
  pages that contain the answer (`gold_pages`), and a short reference answer.

| Category | n | What it tests |
|---|---|---|
| `single_page` | 14 | A fact or procedure on one page |
| `multi_page` | 5 | An answer spread over two or more pages |
| `table` | 12 | Lookups in specification and parts tables |
| `figure` | 5 | Reading a chart, an image-only page, a data plate, or an exploded view |
| `unanswerable` | 6 | The manual does not cover it; the right answer is to decline |

Questions are scoped to one manual, as in the app, where the user picks a manual first.

## Metrics

Retrieval (answerable items only; a hit means any gold page is in the list):

- **recall@k** for k = 1, 5, 10, over the system's final ranked pages. v1 returns at most 5
  documents, so its recall@10 equals its recall@5.
- **MRR**: mean reciprocal rank of the first gold page.
- **candidate recall**: whether a gold page appears anywhere in the wider list before reranking. It
  separates "never retrieved" from "retrieved but ranked out".
- **citation hit**: at least one cited page is a gold page. **citation precision**: share of cited
  pages that are gold pages.

Answers (graded by an LLM judge with fixed prompts at temperature 0; prompts are in `run_eval.py`):

- **correctness** against the reference answer: correct = 1, partial = 0.5, incorrect = 0, averaged
  over answerable items.
- **faithfulness**: every claim in the answer is supported by the excerpts the model was shown
  (faithful = 1, partial = 0.5, unfaithful = 0). Judged only for answers that do not decline.
- **abstention precision / recall**: of the answers that declined, how many were for unanswerable
  items; of the unanswerable items, how many were declined. **False abstentions** counts declines on
  answerable items.

Runtime: **latency p50 / p95**, wall time per question for retrieval plus generation.

Each run can be repeated (`--repeats`). Results report the mean, minimum and maximum across repeats,
so sampling noise is visible next to the score.

## Reproducing the v1 baseline

```bash
export OPENSEARCH_PASS='<any strong password>' OLLAMA_URL=http://<ollama-host>:11434
evals/baseline_v1.sh                      # v1 checkout, stores, ingestion, answers
export LLM_BASE_URL=... LLM_API_KEY=... LLM_JUDGE_MODEL=...
python evals/run_eval.py score evals/results/raw/v1.json --out evals/results/v1.json
```

`baseline_v1.sh` checks out tag `v1` next to the repo, starts its OpenSearch and Qdrant with v1's
own `docker-compose.yaml`, ingests the manuals with v1's own script, and runs the harness in v1's
own environment. v1 is evaluated unchanged: the harness only wraps its pipeline and its Ollama call
to record what was retrieved and what the model was shown.

Two v1 modes are scored: the default (`v1`, guardrails off, as the UI ships) and `v1-strict`
(guardrails on, which drops excerpts scoring below `RAG_MIN_DOC_SCORE`).

## Judge spot-check

The judge is checked by hand on a sample of its gradings, and disagreements are recorded in the
results notes rather than corrected silently.
