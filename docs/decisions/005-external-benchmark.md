# 005: An external benchmark beside the held-out test (2026-11-08)

**Status: step 1 run 2026-11-08; results below.** The registered result (`evals/results/TEST.md`) stands on the held-out test set.
An external benchmark would add a number outsiders recognise, reported as exploratory and kept apart from it.

## Candidates

| | ViDoRe V3, Industrial Maintenance | FACTS Grounding |
|---|---|---|
| What it tests | Retrieval and answers over real PDF manuals: find the page, answer from it | Whether an answer stays faithful to a document handed to the model |
| Fit to this project | Close: 27 US Air Force technical orders, 5,244 pages, 283 queries, page-level gold, multi-hop and unanswerable queries | Partial: skips retrieval, tables, scans and citations, which is where v2's gains are |
| Size | 283 queries in this corpus; 3,099 across ViDoRe V3's 10 corpora | 860 public examples (859 more held private) |
| Scoring | NDCG@10 per page; end-to-end answers judged correct by GPT-5.2 | Three frontier LLM judges; the leaderboard runs on Kaggle |
| Published reference | Best end-to-end on this corpus about 66% (Gemini 3 Pro and others, 5 runs) | Leaderboard of frontier models |
| Licence | Public corpora, "commercially permissive" (exact licence to check) | CC-BY-4.0 |
| Cost here | Ingesting 5,244 pages: at the 363-page rate, about 70 hours on the laptop, less on the 5090 (not measured) | Small: text documents, no ingestion |

Sources: [ViDoRe V3 paper](https://arxiv.org/abs/2601.08620), [FACTS Grounding](https://deepmind.google/discover/blog/facts-grounding-a-new-benchmark-for-evaluating-the-factuality-of-large-language-models/),
[FACTS public data](https://huggingface.co/datasets/google/FACTS-grounding-public), [FACTS leaderboard](https://www.kaggle.com/facts-leaderboard).

## Recommendation

**ViDoRe V3's industrial manuals.** It is the same task as this project, on the same kind of document (military
maintenance manuals), with page-level gold, so it tests the whole system, and its published systems give a reference
point. FACTS Grounding tests only the answer-writing half, against judges this project did not choose; it could follow
later at little cost.

**Two cautions.**

- **Judge.** Its published answer scores use GPT-5.2 as judge. This project's judge is phi4, so v2's answer score would
  not be directly comparable with the published 66%. NDCG@10 needs no judge and is directly comparable. Using GPT-5.2 would
  need an API key and contradicts nothing here (it is not a v2 generator), but it is Alexander's call.
- **Cost.** Ingestion is the expense. A cheaper first step: text-layer ingestion only (no Paddle), to get NDCG@10 for
  retrieval in hours, then decide on the full run.

**Before running:** confirm the licence and download the corpus; fix the protocol (corpus, metrics, judge) in this record
before any run, as was done for the test set; and leave the v2 configuration exactly as registered.

## Constraint and protocol (fixed 2026-11-08, before any run)

Alexander ruled out paid APIs, so the GPT-5.2-judged answer score is off the table. FACTS Grounding needs frontier judges
too, so it is out.

**Step 1, retrieval only, no judge** (`evals/vidore.py`):

- Corpus `vidore/vidore_v3_industrial` (CC-BY-4.0): all 5,244 pages, using the corpus's own page markdown, not v2's
  parser, so this measures v2's retrieval alone.
- Queries: the English ones, with the published graded relevance (qrels).
- System: the registered v2 retrieval, unchanged: `Qwen3-Embedding-0.6B` + BM25 fused, top 50 reranked by
  `Qwen3-Reranker-4B` at half precision; pages ranked by their best chunk. Searched across the whole corpus, since a
  query does not name its document.
- Metrics: NDCG@10 over pages (linear gains, as MTEB), recall@10, and the same NDCG before reranking.
- Comparison: published NDCG@10 for this corpus, from the paper or the MTEB leaderboard, with the caveat that most
  published retrievers read page images, not text.
- Reported as exploratory, apart from the registered result. Nothing in v2 is changed for it.

**Not decided:** an end-to-end answer run judged locally (phi4) would be free but not comparable with the published
answer scores; the queries are partly machine-generated (`query_generator` "sdg"), which the report must say.

## Step 1 result (2026-11-08)

283 English queries over all 5,244 pages, the registered v2 retrieval, `evals/results/vidore/`. Intervals are 95%
bootstrap over queries.

| Retriever, on the corpus's page markdown | NDCG@10 (0–1) |
|---|---|
| **v2: Qwen3-Embedding-0.6B + BM25, fused** | **0.497** (0.454 to 0.540) |
| **v2, then Qwen3-Reranker-4B (the system as registered)** | **0.567** (0.525 to 0.610) |
| BM25 alone, published | 0.456 |
| Qwen3-Embedding-8B alone, published | 0.447 |
| Mixedbread embedding, published | 0.533 |
| Mixedbread embedding + its reranker, published | 0.639 |

Published figures: [Mixedbread's text evals](https://www.mixedbread.com/evals/vidore-v3-text), Industrial (EN), "documents
pre-parsed to markdown", tested September 2026. Mixedbread is a vendor reporting its own models, and its runs were not
reproduced here.

- **Standing, checked 2026-11-09:** placed among the 8 runs in Mixedbread's text-retrieval table for this corpus, v2
  would be 2nd, 0.072 behind the first. v2 is not in that table; it was placed there by this project, and Mixedbread's
  runs, a vendor's own, were not reproduced. The rank is a snapshot, not a leaderboard position. The protocol named the
  paper or the MTEB leaderboard as the comparison; neither gave industrial-only text figures that were found, so this
  vendor page was used instead. Image-based
  retrievers, which lead the official [ViDoRe leaderboard](https://huggingface.co/blog/nvidia/nemotron-colembed-v2), read
  page images and publish no industrial-only figures that were found, so they are not ranked against here.
- v2's fused first stage (0.497) is above published BM25 (0.456) and Qwen3-Embedding-8B (0.447), the larger sibling
  of the 0.6B model v2 uses; the reranker adds 7 points.
- The queries are partly machine-generated (the dataset's `query_generator` field), as the corpus card says.
- The best published text pipeline is about 7 points ahead, outside v2's interval. On this corpus v2's retrieval is good
  but not the best available.
- Recall@10 is 0.586. Time per query on the laptop GPU: p50 6.2 s, p95 7.8 s, almost all of it the 4B reranker.
- This measures retrieval only, on someone else's text extraction. v2's parser, table store, checks and answers are not
  tested by it.

**A defect found along the way.** The first full attempt timed out: v2's search reopened its index from disk for every
query, which took tens of seconds on 9,368 chunks. Fixed in `81fd5da` (speed only), after the registered test run, so it
is a labelled deviation from the registered system. The step 1 result above is from the fixed code.
