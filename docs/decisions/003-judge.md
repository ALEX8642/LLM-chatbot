# 003: The independent judge

Date: 2026-11-03. Plan: [`2026-11-03-tier1-05-eval-set-and-judge.md`](../superpowers/plans/2026-11-03-tier1-05-eval-set-and-judge.md).

## Question

Which local model grades the headline comparison? The spec requires a family no compared generator
uses, so neither Qwen nor Cohere.

## Decision

**`phi4:14b` is the primary judge; `mistral-small3.2:24b` is the second, shown per judge.**
Both are served by Ollama on a 16 GB GPU, at temperature 0, with key-fact prompt version 1.

| Model | Digest | Licence |
|---|---|---|
| `phi4:14b` | `ac896e5b8b34` | MIT |
| `mistral-small3.2:24b` | `5a408ab55df5` | Apache-2.0 |

## Method

Candidates graded 55 answers (35 v1, 20 v2 run 2) labelled by Claude in `evals/calibration/`. The rule was
written into the plan before any run: highest kappa on item correctness; within 0.05 the higher kappa on
source support; if that also ties, the faster. Over 5% JSON failures is out.

| Model | Kappa correct | Kappa facts | Kappa source | Kappa abstained | JSON failures | s/row |
|---|---|---|---|---|---|---|
| **phi4:14b** | 1.00 | 0.97 | 1.00 | 0.83 | 1/55 | 5.8 |
| mistral-small3.2:24b | 1.00 | 0.97 | 1.00 | 0.92 | 0/55 | 7.9 |
| gpt-oss:20b | 1.00 | 1.00 | 0.86 | 0.87 | 1/55 | 5.9 |
| gemma3:12b | 0.94 | 0.96 | 0.73 | 0.81 | 6/55, out | 4.2 |

No candidate shows a length bias (slopes near 0.01 per 100 characters, intervals spanning 0).

## What this does not show

- **The first run was uninformative, and the set was changed after seeing it.** Every source label was
  "yes", so a judge that always says "supported" scored 1.0 and two that sometimes said no scored 0.0
  (`results-no-source-negatives.json`). Each correct answer was then also paired with a wrong page from
  its manual as a negative. The rule did not change, and neither did the winner.
- **The labels are Claude's, and not blind.** They were written after seeing Qwen's grades of the same
  answers. They choose among judges; they do not validate one. Plan 7's blind session checks the judge
  against Alexander, per system; a judge biased on one system would invalidate the comparison.
- **The set is easy.** Three models reach 1.00 on correctness, so it cannot separate them, and speed
  decided between the two that remained. Real grading will be harder than this.
- **Negatives are easy too.** A wrong page is a much plainer failure than a right page that lacks one fact.

## Cons

- phi4 is the weaker of the two on abstention (0.83 against 0.92). This matters for v1, which does not
  record abstention, so the judge decides it. v2 records its own. Unanswerable v1 items are the place to
  watch in the blind session, and to compare against the second judge.
- mistral did not fit the GPU entirely (13.8 of 15.4 GB in VRAM), so its speed here is understated.
