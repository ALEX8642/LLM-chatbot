# Registration: v2 against a stock RAG pipeline with the same generator

**Registered at tag `prereg-owui`, before the stock pipeline answered any test or FIST question.** The runner was
built on development questions (`evals/qa.jsonl`), and the knowledge bases were built first. Everything after the tag that
changes a result is reported as a deviation.

## Why

v2 against v1 changed two things at once: the pipeline and the generator. A later run of v1 with v2's generator
(`evals/v1_generator_swap.py`) used v1's 2024 pipeline. This test pits v2's pipeline against a current, off-the-shelf
one with the same generator: Open WebUI's own document pipeline, as one owner runs it for everyday chat. If the stock
pipeline matches v2, the generator is doing the work.

## Question

With the same generator, does v2 give more answers that are correct and supported by what they cite than Open WebUI's
built-in knowledge-base retrieval?

## Systems

- **v2:** its registered outputs, unchanged. That is the main test run at tag `prereg` and the FIST run at tag
  `prereg-unseen`, both with Qwen3.8 (`Qwen3.8-Flash-Next-NVFP4-Fast`). No new v2 run.
- **Stock (`owui`):** Open WebUI v0.13.0, with its retrieval settings as found on 2026-11-12 and unchanged:
  - extraction: Docling (`docling-serve`, behind a proxy that only rotates upside-down scans);
  - chunks: 1,000 tokens with 100 overlap, markdown-header splitter;
  - embeddings: `nomic-embed-text:v1.5`;
  - search: hybrid BM25 (weight 0.5) plus dense, top 6, reranked by `BAAI/bge-reranker-v2-m3` to the top 3, relevance
    threshold 0;
  - prompt: its default RAG template, which asks for [id] citations.
- **Knowledge bases:** one holds the three main-test manuals (FAA Weight and Balance Handbook, Army 5 kW generator
  operator and parts manuals). One holds FIST 3-30 alone. Both are created through the API from the same PDFs as v2's.
- **Split uploads:** uploaded whole, the 114-page FAA handbook failed. Open WebUI's Docling call gives up after 120 s
  (`DOCLING_SERVE_MAX_SYNC_WAIT=120`), and raising that would change the server. So, as a user would, the three
  main-test manuals (101 to 148 pages) were uploaded in parts of 20 pages (`evals/owui_run.py kb --split 20`; 40-page parts of the parts manual still timed out). FIST
  (87 pages) went in whole. Pages are mapped back to the whole PDF. That a long manual fails as uploaded is itself a
  finding and is reported.
- **How each question is asked:** a fresh conversation through `/api/chat/completions`, with the knowledge base
  attached as a collection. The generator is the same model with v2's settings: temperature 0, seed 0, thinking off.
  The generation settings are the only thing not left at the stock defaults, so that the pipeline is the only
  difference.
- **What it cites:** the sources Open WebUI returns with the answer. Open WebUI numbers sources by file, so an [id]
  stands for every chunk of one PDF. The judge's cited source is the text of the chunks under the [id]s the answer
  cites, or all the chunks it was given if it cites none. Pages come from the chunk metadata (Open WebUI counts them
  from 0; they are recorded from 1) and are kept for a page-level sensitivity.
- **Grading code:** the grader at tag `prereg-unseen` (prompt version 2), run through `evals/owui_score.py`. That
  wrapper changes only where the cited source text comes from.

- **Runner checks, on 3 development questions:** the generation settings reach the model (a 5-token limit was obeyed,
  and no reasoning tokens were used). Open WebUI's retrieval is not repeatable: across two runs the chunks it returned,
  or their order, differed for all 3 questions, and so did the answers. The registered 3 repeats with majority scoring
  stand as they are.

## Items and analysis

As registered for the main test (`docs/prereg.md`) and for FIST (`docs/prereg-unseen.md`), unchanged:
- the items `evals/test.jsonl` (169) and `evals/unseen/fist.jsonl` (104);
- the endpoint: correct, and the judge finds the key facts in the cited source; an unanswerable item passes on an
  abstention;
- judges: phi4:14b with grader prompt version 2 on all repeats, and mistral-small3.2:24b on the first;
- 3 repeats, majority scoring, exact McNemar, and the clustered paired bootstrap with seed 20261106.

- **Primary:** v2 against stock on the main test (169 items, phi4). The claim "v2's pipeline beats the stock pipeline
  with the same generator" needs both p < 0.05 and an interval above zero.
- **Secondary:** the same on FIST (104 items), and mistral on both.
- **Described, not tested:**
  - stock against v1 with Qwen3.8 on the main test and FIST (outputs already committed);
  - how often stock cites anything at all;
  - time per answer.

## Known bias, stated beforehand

The stock pipeline cites about three 1,000-token chunks, far longer than v2's quoted blocks. In blind grading, phi4 on
prompt version 2 missed support in long sources much more often than in short ones
(`evals/results/judge-v3/README.md`). That biases this primary against the stock pipeline. Two further readings are
reported beside it: grader prompt version 3, which checks long sources fact by fact, as a sensitivity; and correctness
without support. **If v2 leads on the primary but not on those readings, the result is reported as not shown.**

## Expectation

A guess, not a threshold. The stock pipeline is between v1 with Qwen3.8 (0.556 on test) and v2 (0.805). It is closer
to v2 on FIST, where v2's checks misfired.

## Limits

- The stock pipeline runs on a shared home server. Its settings are those found that day, not tuned.
- The questions go through the same Qwen3.8 the family uses, so the server's load can vary.
- Claude wrote the items, the runner and this registration.
