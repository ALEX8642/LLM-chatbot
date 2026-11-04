# LLM-Chatbot v2 (in progress)

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A question-answering assistant for technical manuals whose core promise is that **the reader can
check every claim against the source while reading the answer**. In v2 each claim is tied to a verbatim quote from a
specific text line, table row or figure, highlighted on the page, and checked before it is shown.
Every design choice is made by measurement, against an evaluation built before the rebuild started.

> **Status (2026-11-03): this branch is a rebuild in progress, not a working app yet.** The shipped
> v1 app (Haystack 2.x, Ollama, Qdrant + OpenSearch, React UI) is preserved at tag
> [`v1`](https://github.com/ALEX8642/LLM-chatbot/tree/v1); its README there describes how to run
> it. Its code is still on this branch only because the v1 baseline is scored from it; v2 replaces it.

## Why v2

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

## What v2 is

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

## Progress

| Step | State |
|---|---|
| Eval harness, 42 dev questions, v1 baseline | done ([`evals/`](evals/)) |
| Design (revision 4) | done |
| Plan 1: coordinate spike (parsers, OCR detection, overlays) | done: PaddleOCR-VL chosen over Docling ([decision 001](docs/decisions/001-parser-and-coordinates.md)) |
| Plan 2: ingestion (hybrid text layer + Paddle, tables, chunks, index) | done: 363 pages, 92% of table cells boxed ([decision 002](docs/decisions/002-ingestion.md)) |
| Plan 3: answer path (checked claims, removal reasons, abstention) | done: exploratory dev runs in [`evals/results/NOTES-v2-dev.md`](evals/results/NOTES-v2-dev.md) |
| Plan 4: overlay UI (server, replay, frontend) | done: [M1 package](docs/m1/README.md), review pending |
| Plan 5: eval set and judge | in progress: 344 items split dev 172 / test 172, grader done; judge choice, v1 re-grade and gold-answer session next |
| Plans 6–8: component selection, pre-registered final run, presentation | not started |

## Repository layout

```
manualqa/              v2 package
  geometry.py          the one coordinate system (render pages; PDF points and pixels -> [0,1] boxes)
  blocks.py            block schema every parser emits (lines, tables with cells, figures)
  ocr_detect.py        decides per page whether the PDF text layer can be trusted
  overlay.py           draws parses over rendered pages for checking by eye
  parsers/             parser adapters (text layer reference, Docling, PaddleOCR-VL)
evals/
  qa.jsonl             42 dev questions with gold pages and reference answers
  run_eval.py          harness: generate, score (retrieval metrics, LLM judge), summarise
  results/             v1 baseline results and raw answers
  spike/               parser spike: pages, expectations, runner, metrics, report
manuals/               three public manuals (sources and licences in manuals/SOURCES.md)
docs/
  superpowers/specs/   the v2 design
  superpowers/plans/   implementation plans
  spike/               spike overlays and metrics
  decisions/           decision records (what was tried, what won, by how much)
api.py, backend/, frontend/, docker-compose.yaml, scripts/
                       v1 code (scored as the baseline; to be replaced)
```

## Running what exists

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
uv run pytest tests/ -q                                    # unit tests (GPU parser tests skip)
uv run python -m evals.spike.run_spike --parser textlayer  # spike: parses, overlays, metrics
uv run python -m evals.spike.report docs/spike/*/metrics.json
```

The parser candidates need a GPU and their own optional dependencies; tests that need them run with
`MANUALQA_PARSERS=1`. Reproducing the v1 baseline is described in [`evals/README.md`](evals/README.md).

## Data

The three bundled manuals are US Government publications (an FAA handbook and two Army technical
manuals), chosen because they stress different parts of a pipeline: born-digital prose with charts,
a scan with a letter-spaced text layer, and parts lists paired with exploded views. Sources,
licences and checksums: [`manuals/SOURCES.md`](manuals/SOURCES.md).

## How this is built

The code is written with AI coding agents (Claude Code, Codex, GitHub Copilot CLI) under Alexander
Feht's specification and review. Design decisions, rejected alternatives and every reported number
are committed in this repository.

This project is independently developed by Alexander Feht during personal time using personal
hardware. It is not affiliated with or commissioned by any employer, and was licensed under MIT prior
to any discussions with external parties.
