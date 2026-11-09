# 005: An external benchmark beside the held-out test (proposed, 2026-11-08)

**Status: step 1 protocol fixed (below); not yet run.** The registered result (`evals/results/TEST.md`) stands on the held-out test set.
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
