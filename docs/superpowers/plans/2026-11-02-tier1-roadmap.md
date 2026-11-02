# Tier 1 (minimum credible version): plan sequence

Spec: `docs/superpowers/specs/2026-11-01-v2-design.md`, section "Delivery tiers".

Tier 1 spans several independent subsystems, so it is built as a sequence of plans. Each plan
produces working, tested software on its own, and each is written only when its predecessor has
landed, because its predecessor's results decide its contents (the spike picks the parser and fixes
the block schema the ingestion plan builds on, and so on).

| # | Plan | Delivers | Ends with |
|---|---|---|---|
| 1 | Coordinate spike (`2026-11-02-tier1-01-coordinate-spike.md`) | `manualqa` package: one coordinate system, block schema, OCR detection, two parser adapters, overlay images, spike metrics | `docs/decisions/001-parser-and-coordinates.md`, overlay reference images |
| 2 | Ingestion | Whole-manual parse with the chosen parser, structure chunking, SQLite table store with `lookup_table`, page renders (150 dpi display, ~1,000 px for the generator), Qdrant local index (dense + BM25) | Ingested index of the 3 manuals; table-lookup tests on the parts manual |
| 3 | Answer path (thin slice, backend) | Retrieval (dense + sparse, RRF, rerank), generator call with page images to Qwen3.8, line-delimited claim format parsed while streaming, quote match, deterministic fact checks, abstention; v2 system in `evals/run_eval.py` | First v2 run on the 42 dev items |
| 4 | Overlay UI (thin slice, frontend) | FastAPI SSE, React overlay highlights from stored boxes, verified and removed states, multi-turn, replay mode | **M1 review** (overlays + 10 live answers) |
| 5 | Eval set and judge | Item pool, dev ≥ 80 (≥ 20 unanswerable) and test 150–200 split by section, near-miss unanswerables, gold-answer session artifact, local non-Qwen non-Cohere judge with key-fact checklists, v1 and v1-at-temperature-0 re-graded | **M2 review**, test set frozen |
| 6 | Component selection | One upgraded embedder and reranker chosen on dev recall (decision records 002, 003), tuned stack | Tuned step-D configuration on dev |
| 7 | Pre-registration and final run | Analysis code (McNemar, clustered bootstrap, minimum detectable effect), pre-registration tag, test run, blind-grading session, failure taxonomy, misses | Committed raw outputs and headline number |
| 8 | Presentation | README (GIF, one table, misses), `EVAL.md`, demo polish | **M4 review** |

Order constraints: 5 can start any time after 1 (it does not depend on v2 code) and must finish
before 7. Tier 2 starts only after 8, in the spec's add order.
