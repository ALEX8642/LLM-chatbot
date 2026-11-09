# History

How v2 came about, kept out of the README so the front page stays about the result.

## Why v2: what v1 got wrong

v1 was scored first, unchanged, on 42 questions over three public manuals
([`evals/results/NOTES.md`](evals/results/NOTES.md)). The baseline showed that retrieval mostly
works and reading does not:

| v1 (default settings) | Value |
|---|---|
| Recall@5 (a gold page among the 5 retrieved) | 0.89 |
| Answer correctness | 0.49 |
| Correctness on table questions | 0.33 |
| Correctness on figure questions | 0.20 |
| Correctness on the parts manual | 0.03 |

Tables flattened by text extraction wreck answers (one answer gave a CAGE code as a part number: right
row, wrong column), figures are retrieved but unreadable, and the relevance gate drops correct pages.
These answers were graded by Qwen3.8, which v2 also uses as a generator, so before any v1–v2
comparison, v1 is re-graded by an independent judge from another model family.

## The design

Design: [`docs/superpowers/specs/2026-11-01-v2-design.md`](docs/superpowers/specs/2026-11-01-v2-design.md)
(approved after four independent reviews). In short:

- **Parsing with coordinates:** OCR-grade parsing into text lines, tables (cells intact) and figures,
  every box in one page-normalised coordinate system, so highlights land on the rendered page. Scanned
  or malformed pages are always OCR'd.
- **Tables as data:** every table goes into SQLite; a `lookup_table` tool returns the exact row with
  its header.
- **Page images to a vision model** alongside the retrieved text.
- **Claim-level citations, checked:** the model answers one claim per line with a block id and a
  verbatim quote. A claim is shown only if its quote matches the source; numbers and identifiers must
  sit in the column whose header matches. Claims that fail are removed into a "see why" disclosure,
  and if none survive, the assistant says it could not find the answer.
- **Evaluation a sceptical engineer would trust:** a held-out test set split by manual section, one
  pre-registered headline metric with an exact McNemar test and a clustered bootstrap interval, an
  independent judge from a model family that is not among the generators, human checks of gold
  answers and grading, and the misses reported.
- **Plain Python modules behind standard HTTP APIs** (OpenAI-compatible chat, embeddings, rerank), so
  any compatible endpoint works; no orchestration framework.

The build follows [delivery tiers](docs/superpowers/specs/2026-11-01-v2-design.md#delivery-tiers):
a minimum credible version first, planned as a
[sequence of eight plans](docs/superpowers/plans/2026-11-02-tier1-roadmap.md).

## The plans, as delivered

| Step | State |
|---|---|
| Plans 1–4: coordinate spike, ingestion, answer path, overlay UI | done ([decisions 001](docs/decisions/001-parser-and-coordinates.md), [002](docs/decisions/002-ingestion.md); [M1](docs/m1/README.md)) |
| Plan 5: eval set and judge | done: dev 172, test 169 frozen at tag `eval-test-frozen`, judge phi4 ([decision 003](docs/decisions/003-judge.md)) |
| Plan 6: component selection | done: Qwen3-Reranker-4B, tested on 16 and 32 GB ([decision 004](docs/decisions/004-retrieval.md)) |
| Plan 7: pre-registration and test run | done: [`evals/results/TEST.md`](evals/results/TEST.md) |
| Plan 8: presentation | done: this README, [`EVAL.md`](EVAL.md), demo GIF, public benchmark ([decision 005](docs/decisions/005-external-benchmark.md)), cold-clone check; M4 review pending |

