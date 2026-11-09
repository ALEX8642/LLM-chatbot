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

## In one minute

- **Result:** on 169 questions held out from development, over three public manuals, **80% of v2's answers are correct
  and supported by what they cite, against 42% for v1**, a conventional retrieval-augmented pipeline. v2 also uses a
  much larger generator than v1, so the gain is the pipeline and the model together.
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
  Qwen3.8 behind an OpenAI-compatible endpoint. A run of v2's pipeline with v1's model, planned in the design, was not
  done, so how much of the gain is the pipeline alone is not measured.
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

## Limits

- Test and development questions come from the same three manuals, though from different sections. A manual neither
  system has seen is the next test.
- Claude wrote the questions, the code and the failure labels. The registration, the section split and the human checks
  guard against that; the human checks are by one person, who is not a subject expert.
- v1 is the only baseline, and it uses a smaller model (above).
- The meaning check, which asks the model whether the source says what a claim says, removed nothing on test.
- Highlights cover whole printed lines, so one can include a neighbouring word.
- The checks were tightened after the registered run (a part-number prefix, figure claims, letter-spaced OCR). On dev
  they changed no answer ([`NOTES-v2-dev.md`](evals/results/NOTES-v2-dev.md)); they have not been run on test.

## How it works

1. **Parse with coordinates:** PaddleOCR-VL and the PDF's text layer give text lines, table cells and figures, each
   with its box on the page.
2. **Tables as data:** every table row goes into SQLite with its column headers.
3. **Retrieve:** dense and keyword search fused, then a reranker picks the passages and table rows; the model also sees
   page images.
4. **Answer claim by claim:** the model writes one claim per line with a quote. A claim is shown only if its quote
   matches the source, its numbers and part numbers are in the right column and unit, and the source says what the
   claim says.

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
docker/, compose.yaml  the image's start script and the replay, live and cpu profiles
```

v1 (Haystack, Ollama, Qdrant + OpenSearch) is preserved at tag [`v1`](https://github.com/ALEX8642/LLM-chatbot/tree/v1).
The harness that ran it for the registered comparison is at tag
[`prereg`](https://github.com/ALEX8642/LLM-chatbot/tree/prereg); its answers and grades are kept here in `evals/results/`.

## Running it

**In the browser:** [the replay demo](https://alex8642.github.io/LLM-chatbot/), nothing to install.

**With Docker:** the interface, server, manuals and their parses in one image. Open
<http://localhost:8000> once it is running.

```bash
git clone https://github.com/ALEX8642/LLM-chatbot && cd LLM-chatbot

# Replay: the recorded answers, no GPU or model needed
docker compose --profile replay up --build

# Live: copy the settings file and set your chat endpoint in it, then
cp .env.example .env
docker compose --profile live up --build    # NVIDIA GPU
docker compose --profile cpu up --build     # no GPU: set a rerank endpoint in .env
```

Live answers need an OpenAI-compatible chat endpoint serving a model that accepts images (vLLM, LiteLLM, Ollama, LM
Studio or a hosted API); `.env.example` explains each setting. The `live` profile needs an NVIDIA GPU with 16 GB of
memory and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
The first start downloads the embedder and reranker (about 9 GB) and builds the index from the bundled parses (about
5 minutes in all on a 16 GB laptop GPU, plus the download); later starts take about 40 seconds, and answers 10-20
seconds. The image is about 12 GB. The `cpu` profile runs the embedder on the processor and expects the reranker on a
rerank endpoint (`.env.example`); it has been tested only in parts. Scores here were measured with Qwen3.8 as the
generator; other models will behave differently. The server has no login, so compose publishes it on this machine only.

**From source:** Python 3.12, [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
# Replay
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
