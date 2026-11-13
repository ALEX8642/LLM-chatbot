# LLM-Chatbot v2

[![CI](https://github.com/ALEX8642/LLM-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/ALEX8642/LLM-chatbot/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A question-answering assistant for technical manuals in which **every claim can be checked against the source while
you read the answer**. Each claim carries a verbatim quote from a specific text line, table row or figure, is checked
against that source before it is shown, and is highlighted on the page. A claim that fails is removed; if none
survive, the assistant says it could not find the answer.

![Three answers replayed: a part number with its table row highlighted, an engine-cranking limit with its caution highlighted, and a question the manual does not answer, declined](docs/demo.gif)

*Each claim links to its source, highlighted on the page. The last question is not in the manual, so it declines.*

## What we learned

**v2 is much better than the alternatives on the three manuals it was developed on, and only as good as them on a manual
it had never seen.** Its gains come from handling those manuals' tables, figures and procedures. Most of that has not
carried over to a new manual yet.

| Correct and supported (phi4 judge) | Main test: 169 questions, 3 manuals v2 was developed on | FIST 3-30: 104 questions, a manual neither system had seen |
|---|---|---|
| v1, old pipeline, 7B model | 0.42 | 0.64 (0.86 with human grades) |
| v1, old pipeline, same model as v2 | 0.56 | 0.69 |
| Stock Open WebUI RAG, same model as v2 | 0.53 | 0.82 |
| **v2, same model** | **0.80** | 0.80 (0.90 with human grades) |
| v2 with Claude Opus 5.5 | 0.85 | 0.86 |

- **Main test** (registered before running): v2 leads every alternative, by 25 to 39 points with phi4 and 16 to 34 with
  the second judge (mistral). Most of the lead is on tables (0.76 against 0.31 for stock RAG). The questions are held-out sections, but of the same manuals that
  steered v2's design.
- **A second unseen manual** (kept private for copyright, 80 questions): v2 level with v1, and ahead of stock RAG on every
  reading but not by the pre-stated standard (+14 on the primary, p 0.04; +6 to +13 on the others).
- **Unseen manual:** the registered test favoured v2 over v1, but blind human grading showed the judge was harder on
  v1's citations. With the human grades the two are level. Stock RAG is level with v2 too. v2's own checks, tuned on
  the first three manuals, removed true claims there (since fixed: [unseen manual](#unseen-manual)).
- **Generator:** a frontier model (Claude Opus 5.5) adds about 5 points, not significant. Swapping v1's 7B model for v2's
  adds about 14 on the main test. The pipeline matters more than the model on the main test, but not on the unseen
  manual.
- **The judges:** local judges can be biased by citation style by up to 35 points on disputed answers, in either
  direction, so every headline here was checked against blind human grades or several judges.
- **What v2 gives regardless:** every claim is shown with a verbatim quote highlighted on the page, and answers are
  repeatable (stock RAG gave the same answer three times for only 14% of test questions).

Details: [Result](#result), [Unseen manual](#unseen-manual),
[stock pipeline comparison](evals/results/owui/RESULTS.md), [`EVAL.md`](EVAL.md).

## At a glance

- **Public benchmark:** v2's retrieval scores NDCG@10 0.567 on ViDoRe V3's industrial manuals, placed 2nd of the 9 text
  retrievers in one vendor's published table when checked on 2026-11-09 (details below).
- **Try it:** [in the browser](https://alex8642.github.io/LLM-chatbot/), replaying 14 recorded answers in the real
  interface; or from a fresh clone, with no GPU or model (see [Running it](#running-it)).
- **Needs, to run live:** Docker or Python, an NVIDIA GPU with 16 GB, and an OpenAI-compatible endpoint serving a
  vision-capable model.

## Result

The test was registered before it was run ([`docs/prereg.md`](docs/prereg.md), tag `prereg`): the questions, the
measure, the comparison and the statistics were fixed first, and the result is reported whatever it showed.

| Correct, with the key facts in the cited source | v2 | v1 |
|---|---|---|
| Local judge (phi4, majority of 3 runs) | **0.805** | 0.420 |
| Difference | **+0.385** (95% interval 0.21 to 0.52) | |
| Items only one system gets right | 72 | 7 |
| Blind human grading of 50 items (21 of them picked where the judge had failed an answer) | 42 of 50 | 31 of 50 |

- **The systems:** v1 is a hybrid-search pipeline with Command R7B, a 7B model run locally. v2 is this pipeline with
  Qwen3.8 behind an OpenAI-compatible endpoint. Run after registration with Qwen3.8 as its generator
  (`evals/v1_generator_swap.py`), v1 scores 0.556 (phi4) and 0.645 (mistral): v2 leads it by +0.249 (p < 0.001) and
  +0.160 (interval lower bound 0). So most of the gain is the pipeline, not the model.
- **The judge is harder on v1.** In blind grading it wrongly failed 19 of 50 v1 answers against 7 of v2's, which
  triggered the registered warning: it often misses support in v1's whole-page citations. On the items drawn at random
  it agreed with the human grader on 52 of 58. Allowing for its misses puts the gap at 31 to 33 points rather than 38.
  v2 leads on every reading.
- **A registered expectation failed:** the gain was expected to shrink on test, since development steered v2, but it
  grew (+0.32 on dev, +0.385 on test). v1 fell more on test (0.51 to 0.42), mostly on the parts manual, which is a
  larger share of the test set.
- **Where v2 still fails** (33 of 169): it declines when the answer is there (11; in 4 its own checks removed every
  claim), gives right but incomplete answers (6), answers questions the manuals do not cover (4), and twice its checks
  remove a true claim. About 6 failures look like judge errors. Every miss is labelled in
  [`v2-misses.jsonl`](evals/results/test/v2-misses.jsonl).
- **Time per answer:** about 13 s (p95 22 s) with retrieval on a 16 GB GPU and the generator on a separate server;
  v1 took 2 to 3 s with its small model on the same machine.

Method, figures by manual and category, and every check: [`EVAL.md`](EVAL.md) and
[`evals/results/TEST.md`](evals/results/TEST.md). The test questions were written for this project, so this table has
no outside ranking.

**Public benchmark.** On ViDoRe V3's industrial manuals (5,244 pages of US Air Force technical orders, 283 queries),
v2's retrieval, given the corpus's own page text, scores NDCG@10 0.567 (0.525 to 0.610). Placed among the 8 runs
[Mixedbread published](https://www.mixedbread.com/evals/vidore-v3-text) for text retrievers on the same text, it would
be 2nd, 0.072 behind their best pipeline; those runs are a vendor's own and were not reproduced. The leaders of the
official ViDoRe board read page images instead, and are not compared. Some benchmark questions are machine-generated.
This tests retrieval only. [Decision 005](docs/decisions/005-external-benchmark.md).

## Unseen manual

A fourth public manual, FIST 3-30 (Reclamation, transformer maintenance), with 104 questions written before either system
ran on it, registered in [`docs/prereg-unseen.md`](docs/prereg-unseen.md). Full report:
[`evals/unseen/RESULTS.md`](evals/unseen/RESULTS.md).

| Correct and supported | v2 | v1 | Difference (95% interval) |
|---|---|---|---|
| phi4 judge (registered primary) | 0.804 | 0.647 | +0.157 (0.031 to 0.284), p 0.014 |
| mistral judge (secondary) | 0.817 | 0.856 | −0.038, n.s. |
| phi4, with Alexander's blind grades on the 62 answers he checked | 0.903 | 0.864 | +0.039 (−0.041 to 0.125), p 0.48 |

- **The registered win does not hold up.** phi4 wrongly failed 23 of 31 good v1 answers in the blind check against 10 of
  18 good v2 answers; mistral erred the other way (0 of 31 against 7 of 20). Both trip the registered judge warning.
  Corrected with the human grades, both judges give the same answer: level.
- **v2's checks overfit the development manuals.** In 7 of its 10 real failures a check removed a true claim (a number
  taken from the question, a fraction written differently, misread table columns). On the main test that was 2 of 33.
  Fixed after the run and re-run, v2 rises to 0.843 (phi4) / 0.865 (mistral); against v1's 0.647 / 0.856 the judges
  still split, so the human-corrected "level" remains the best reading.
- **Frontier generator:** v2 with Opus 5.5 scores 0.860 / 0.837 (phi4 / mistral) here against Qwen3.8's 0.804 / 0.817,
  and 0.849 / 0.870 on the main test against 0.805 / 0.805. None of the differences is significant. Opus's claims were
  removed by the checks 41 times against Qwen3.8's 11, so its score is a floor. Run with the Batch API
  (`evals/batch_run.py`) for about $14.

## Limits

- The main test and development questions come from the same three manuals, though from different sections. On the one
  unseen manual (above), v2 was not shown to be better than v1.
- The local judges are biased by citation style, in opposite directions, by up to 35 points on disputed answers. Every
  headline here has been checked against blind human grades, but those cover only the answers sampled.
- Claude wrote the questions, the code and the failure labels. The registration, the section split and the human checks
  guard against that; the human checks are by one person, who is not a subject expert.
- v1 is the only baseline. Its registered run uses a smaller model; the run with v2's generator came after registration.
- The meaning check, which asks the model whether the source says what a claim says, removed nothing on test.
- Highlights cover whole printed lines, so one can include a neighbouring word.
- The checks were tightened after the registered run (a part-number prefix, figure claims, letter-spaced OCR). On dev
  they changed no answer ([`NOTES-v2-dev.md`](evals/results/NOTES-v2-dev.md)); they have not been run on test.
- A review found the quote match could pass a quote that changed its source's number, swapped "may" for "must", or
  started just after a "Do not" it left out; the fact checks and the model's meaning check were the only guard. A
  wording check now refuses those. Re-run offline on every claim v2 verified, it removes none of the 711 on test or the
  290 on dev.

## How it works

1. **Parse with coordinates:** PaddleOCR-VL and the PDF's text layer give text lines, table cells and figures, each
   with its box on the page.
2. **Tables as data:** every table row goes into SQLite with its column headers.
3. **Retrieve:** dense and keyword search fused, then a reranker picks the passages and table rows; the model also sees
   page images.
4. **Answer claim by claim:** the model writes one claim per line with a quote. A claim is shown only if its quote
   matches the source and keeps its numbers and words such as "may", "must" and "not", its numbers and part numbers
   are in the right column and unit, and the source says what the claim says.

## Repository layout

```
manualqa/              v2: parsing, ingestion, retrieval, answer path with checks, server
  parsers/             parser adapters (text layer, PaddleOCR-VL, Docling)
  compose.py           text layer + Paddle merged per page; table_grid.py, table_geometry.py place cells
  tables.py            SQLite table store and lookup_table
  index.py, retrieve.py  dense + BM25 index, fusion, reranker, evidence
  answer.py            claims, quote match, facts.py, claimcheck.py, abstention
  server.py            FastAPI with streaming answers and replay
  static_demo.py       the browser demo's files
frontend/              React interface: claims with page highlights
evals/
  pool/, qa.jsonl, test.jsonl   items; dev and the frozen test set
  run_eval.py, grade.py         generate and grade (key facts, judge)
  analysis.py                   the registered analysis
  results/                      dev notes, TEST.md, raw outputs, judge outputs
  sessions/                     human-check pages and their records
docs/
  decisions/           what was tried, what won, by how much (001-005)
  prereg.md            the registration
  superpowers/         the design and the build plans (written for and by the coding agents)
  HISTORY.md           why v2, the design in brief, the plans as delivered
manuals/               three public manuals and their parses (sources and licences in manuals/SOURCES.md)
docker/, compose.yaml  the image's start script and the replay, live and cpu profiles (image.yml publishes it)
```

v1 (Haystack, Ollama, Qdrant + OpenSearch) is preserved at tag [`v1`](https://github.com/ALEX8642/LLM-chatbot/tree/v1).
The harness that ran it for the registered comparison is at tag
[`prereg`](https://github.com/ALEX8642/LLM-chatbot/tree/prereg); its answers and grades are kept here in `evals/results/`.

## Running it

**In the browser:** [the replay demo](https://alex8642.github.io/LLM-chatbot/), nothing to install.

**With Docker:** the interface, server, manuals and their parses in one image, pulled from GitHub's registry
(`ghcr.io/alex8642/llm-chatbot`; add `--build` to build it from the checkout instead). Open <http://localhost:8000>
once it is running.

```bash
git clone https://github.com/ALEX8642/LLM-chatbot && cd LLM-chatbot

# Replay: the recorded answers, no GPU or model needed
docker compose --profile replay up

# Live: copy the settings file and set your chat endpoint in it, then
cp .env.example .env
docker compose --profile live up    # NVIDIA GPU
docker compose --profile cpu up     # no GPU: set a rerank endpoint in .env
```

Live answers need an OpenAI-compatible chat endpoint serving a model that accepts images (vLLM, LiteLLM, Ollama, LM
Studio or a hosted API); `.env.example` explains each setting. The `live` profile needs an NVIDIA GPU with 16 GB of
memory and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
The image is about 450 MB and replay needs nothing more. The first live start installs the rest into Docker volumes:
PyTorch (about 7 GB with CUDA, or 1.5 GB for the processor in the `cpu` profile), the embedder and reranker (about
9 GB), then the index; on a home connection and a 16 GB laptop GPU that took 25 minutes. Later starts take about 35
seconds, and answers 10-20 seconds. The `cpu` profile runs the embedder on the processor and expects the reranker on a
rerank endpoint (`.env.example`); it has been tested only in parts. Scores here were measured with Qwen3.8 as the
generator; other models will behave differently. The server has no login, so compose publishes it on this machine only.

**From source:** Python 3.12, [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
# Replay (installs the full dependencies, several GB with PyTorch; the browser demo needs none)
uv sync --extra dev
uv run python -m manualqa.server --replay docs/demo/replay.jsonl --port 8000
cd frontend && npm install && npm run build && npx vite preview   # open the printed address

# Live: ingest the bundled parses (minutes), then serve and start the interface as above
uv run python -m manualqa.ingest --raw manuals/paddle-parses.jsonl.gz --out data/ingest
export GEN_BASE_URL=https://your-endpoint GEN_MODEL=your-model GEN_API_KEY=...
uv run python -m manualqa.server --ingest data/ingest --port 8000
```

Parsing the manuals again with PaddleOCR-VL takes several hours and a recent NVIDIA driver for CUDA 12.9
(`uv sync --extra paddle`, then `uv run python -m evals.spike.run_spike --parser paddle --pages all --resume`; rerun
with `--resume` if it hangs); the bundled parses are its output.

The browser demo is the same interface built with `--mode demo`, reading the recordings as static files
(`.github/workflows/pages.yml`, `manualqa/static_demo.py`).

Questions and answers are recorded to `data/recordings/` unless the server is started with `--no-record`. Running the
evaluation: [`EVAL.md`](EVAL.md) and [`evals/README.md`](evals/README.md).

## Data

The three bundled manuals are US Government publications (an FAA handbook and two Army technical
manuals), chosen because they stress different parts of a pipeline: born-digital prose with charts,
a scan with a letter-spaced text layer, and parts lists paired with exploded views. Sources,
licences and checksums: [`manuals/SOURCES.md`](manuals/SOURCES.md).

**Licences.** The code is MIT. It depends on PyMuPDF, which is AGPL-3.0: if you serve this application to others over a
network, the AGPL's terms apply to that service. Model licences are recorded in the decision records.

## How this is built

The code is written with AI coding agents (Claude Code, Codex, GitHub Copilot CLI) under Alexander
Feht's specification and review. Design decisions, rejected alternatives and every reported number
are committed in this repository; how v2 came about is in [`docs/HISTORY.md`](docs/HISTORY.md).

This project is independently developed by Alexander Feht during personal time using personal
hardware. It is not affiliated with or commissioned by any employer, and was licensed under MIT prior
to any discussions with external parties.
