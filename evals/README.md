# Evaluation

The method and results are in [`EVAL.md`](../EVAL.md) and [`results/TEST.md`](results/TEST.md). This file covers the
tools.

| What | Where |
|---|---|
| Items: pool, dev set, frozen test set | `pool/`, `qa.jsonl`, `test.jsonl`; `split.py`, `sections.json` |
| Generate answers, then grade them | `run_eval.py generate`, `run_eval.py score --grader keyfacts` (judge: `LLM_BASE_URL`, `LLM_JUDGE_MODEL`) |
| The registered analysis | `analysis.py` |
| Human-check pages | `sessions/` |
| Component and checker selection | `retrieval_select.py`, `checker_select.py`, `judge_select.py`, `claims/` |
| Public benchmark (retrieval) | `vidore.py` |
| History: the first 42 questions and v1's baseline under the old judge | `results/NOTES.md` |

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
