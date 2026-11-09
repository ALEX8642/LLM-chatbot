# Evaluation

The method and results are in [`EVAL.md`](../EVAL.md) and [`results/TEST.md`](results/TEST.md). This file covers the
tools.

| What | Where |
|---|---|
| Items: pool, dev set, frozen test set | `pool/`, `qa.jsonl`, `test.jsonl`; `split.py`, `sections.json` |
| Generate answers, then grade them | `run_eval.py generate`, `run_eval.py score` (judge: `LLM_BASE_URL`, `LLM_JUDGE_MODEL`) |
| The registered analysis | `analysis.py` |
| Human-check pages | `sessions/` |
| Component and checker selection | `retrieval_select.py`, `checker_select.py`, `judge_select.py`, `claims/` |
| Public benchmark (retrieval) | `vidore.py` |
| History: the first 42 questions and v1's baseline under the old judge | `results/NOTES.md` |

## v1

v1's code is not on this branch. Its answers and grades are in `results/raw/` and `results/test/`, enough to re-run
the analysis. To regenerate them: v1 at tag `v1`, run by `evals/baseline_v1.sh` and `evals/run_eval.py` at tag
`prereg`.
