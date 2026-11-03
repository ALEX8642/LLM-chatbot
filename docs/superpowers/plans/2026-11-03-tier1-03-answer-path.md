# Answer Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer a question about one manual with claims that are each tied to a verbatim quote from a specific line, table row or figure, shown only when the quote matches the source, with deterministic fact checks, abstention, and a v2 system in the eval harness, first run on the 42 dev items.

**Architecture:** retrieve (hybrid index from plan 2, reranked) → assemble evidence (text excerpts with block ids, table rows with headers from `lookup_table`, up to 3 page images) → generate with Qwen3.8 through the existing OpenAI-compatible gateway, one JSON object per line per claim → check each claim as it closes (quote match → highlight boxes; deterministic facts incl. right-row-wrong-column) → answer from surviving claims or abstain. Plain modules; every stage records inputs and outputs for the harness.

**Tech Stack:** Python 3.12, requests (OpenAI-compatible chat, streaming), sentence-transformers CrossEncoder (default reranker `BAAI/bge-reranker-v2-m3`, Apache-2.0; plan 6 chooses the real one), rapidfuzz, the plan 2 modules.

**Spec:** `docs/superpowers/specs/2026-11-01-v2-design.md` (Query 1–8, Goals 1 and 4, Anti-goals). Inputs: plan 2 outputs under `data/ingest/` (composed pages, `tables.sqlite`, `chunks.jsonl`, `pages/`, `qdrant/`). Sequence: `docs/superpowers/plans/2026-11-02-tier1-roadmap.md`.

## Global Constraints

- A claim is shown only once its quote has matched the source; a claim that fails any check is removed into a "removed, see why" list with the reason. Unknown block ids are dropped and counted.
- Every number and identifier in a claim must appear in its quote; for a table row, a value must sit in the column whose header the claim names (this catches right row, wrong column, e.g. a CAGE code given as a part number).
- If no claim survives, the system says it could not find the answer in the manual and lists what it found (pages and blocks retrieved).
- Figure claims (cited to a figure or page image) skip quote matching, are labelled "read from figure N", and are kept only when the figure has text that contains the claim's numbers (entailment is tier 2).
- Endpoints, keys and model names only from `.env` (`GEN_BASE_URL`, `GEN_API_KEY`, `GEN_MODEL`); nothing host-specific committed. Generator reasoning off unless measured to help.
- Calls to the Sparks' gateway are sequential (one request at a time) so household use does not suffer; dev runs, not sweeps.
- v2 results on dev are exploratory and say so; no headline number until the pre-registered test run (plan 7). v1's grades stay history until plan 5 re-grades.

## Review Focus

1. **Quotes that differ from the source only by extraction noise** (hyphenation across lines, ligatures, curly quotes, OCR letter confusions, letter-spaced text): they must match. `test_quote_match_tolerates_extraction_noise` (Task 2).
2. **A quote copied from the wrong block** (real text, other block): it fails, the claim is removed with reason "quote not in cited block". `test_quote_from_other_block_fails` (Task 2).
3. **The CAGE-code trap**: "the part number of the filter element is 18265" citing the row whose PART NUMBER is P14-8969 fails with reason "value in column FSCM, claim names PART NUMBER". `test_right_row_wrong_column_fails` (Task 3).
4. **Malformed model output** (prose lines, broken JSON, a line split across stream chunks): parsed lines become claims, prose is recorded and ignored, nothing crashes. `test_parser_survives_garbage_and_split_lines` (Task 4).
5. **The near-miss unanswerable** (on-topic question the manual does not cover): when all claims fail or none are produced, the answer abstains and lists what was found. `test_abstains_when_no_claim_survives` (Task 6).

---

### Task 1: Retrieval with reranking and evidence assembly

**Files:** create `manualqa/retrieve.py`, `tests/manualqa/test_retrieve.py`.

**Interfaces — produces:**
- `class Reranker(Protocol): name: str; def score(self, query: str, texts: list[str]) -> list[float]`; `CrossEncoderReranker(model="BAAI/bge-reranker-v2-m3")`; `HttpReranker(base_url, model)` for a `/v1/rerank` endpoint.
- `Evidence(id: str, kind: Literal["text", "row", "figure"], manual: str, page: int, block_id: str, text: str, boxes: list[Box], header: list[str] | None = None, cells: list[str] | None = None, cell_boxes: list[Box | None] | None = None)`. Row ids are `f"{block_id}:r{row}"`.
- `retrieve(question: str, manual: str, ctx: IngestContext, k_chunks: int = 8, pool: int = 50) -> RetrievalResult` with `evidence: list[Evidence]`, `ranked_pages: list[int]`, `candidate_pages: list[int]`, `page_images: list[Path]` (≤ 3, distinct pages, in rank order), `table_hits: int`.
- `IngestContext.load(path: Path, embedder: Embedder, reranker: Reranker)` holding composed pages by block id, the table store and the index path.

Behaviour: hybrid `search(question, pool)` filtered to the manual → rerank → top `k_chunks` → expand each chunk into evidence: text/heading blocks become `text` evidence (one per block, text = block text, boxes = its line boxes); table chunks become one `row` evidence per stored row of that block (from the table store); figure chunks become `figure` evidence. Then table lookup: identifiers in the question (`tokens` with a digit, length ≥ 3) and "item N" / "figure N" patterns → `lookup_table` (query, `columns={"item": N}`, `figure=`) → extra `row` evidence first in the list. Deduplicate by id.

- [ ] Tests (fake embedder from plan 2's test, a fake reranker that scores by token overlap, a tmp index built from the six fixture pages composed): `test_retrieve_returns_row_evidence_for_part_number` ("What is part P14-8969?" → first evidence is the row with P14-8969, kind "row", header present, boxes non-empty); `test_item_in_figure_lookup` ("What is item 17 in figure 15?" → that row present); `test_page_images_distinct_and_capped`; `test_text_evidence_boxes_are_line_boxes`. FAIL → implement → PASS → commit `manualqa: retrieval with reranking and evidence (text, rows, figures)`.

### Task 2: Quote matching to highlight boxes

**Files:** create `manualqa/quotes.py`, `tests/manualqa/test_quotes.py`.

**Interfaces — produces:** `match_quote(quote: str, ev: Evidence) -> QuoteMatch | None` with `QuoteMatch(score: float, span: tuple[int, int], boxes: list[Box])`. `QUOTE_MIN = 90`.

Normalisation for matching (a mapping back to original character offsets is kept): NFKC, case fold, curly to straight quotes, soft hyphen and end-of-line hyphenation removed ("air-\ncleaner" → "aircleaner" vs "air cleaner": compare with all whitespace removed), common OCR confusions folded (`0/o`, `1/l/i`, `5/s` only when both sides are letters-or-digits mixed). Alignment: `rapidfuzz.fuzz.partial_ratio_alignment` on whitespace-free normalised strings; map the aligned span back to block text offsets; boxes = the line boxes whose character range overlaps the span (text evidence) or the cell boxes whose text overlaps (row evidence; row text is `header: value` pairs joined by `; `).

- [ ] Tests: `test_exact_quote_gives_line_boxes` (quote spanning two lines → both lines' boxes, nothing else); `test_quote_match_tolerates_extraction_noise` (hyphenation, ligature "ﬁlter", curly quotes, "T h i s  s e c t i o n" letter-spacing → match); `test_quote_from_other_block_fails` (text from another block → None); `test_row_quote_gives_cell_boxes` (quote "P14-8969" on its row → that cell's box); `test_short_quote_needs_exact` (a 3-character quote must appear exactly). FAIL → implement → PASS → commit `manualqa: quote matching with highlight boxes`.

### Task 3: Deterministic fact checks

**Files:** create `manualqa/facts.py`, `tests/manualqa/test_facts.py`.

**Interfaces — produces:** `check_facts(claim: str, quote: str, ev: Evidence) -> FactResult(ok: bool, reason: str | None)`.

Rules: facts = numbers (with decimals, ±, fractions) and identifiers (tokens mixing letters and digits, or with hyphens and digits) in the claim, normalised (`3,050` = `3050`; units ignored). Each must appear in the quote → else reason `"<fact> not in quote"`. For `row` evidence additionally: for each fact, the columns whose cell contains it; if the claim names a column (a header label of that row matched with partial_ratio ≥ 85 on the claim text) and that named column's cell does not contain the fact while another column's does → reason `"value in column <A>, claim names <B>"`.

- [ ] Tests: `test_numbers_must_be_in_quote`; `test_thousands_separator_equivalent`; `test_right_row_wrong_column_fails` (the CAGE trap on the p59 row: claim "the part number is 18265" → fail with the column reason; claim "the part number is P14-8969" → ok); `test_claim_without_facts_passes` (a procedural statement with no numbers → ok). FAIL → implement → PASS → commit `manualqa: deterministic fact checks (numbers in quote, right row right column)`.

### Task 4: Claim-format prompt, streaming parser, generator client

**Files:** create `manualqa/generate.py`, `manualqa/prompts.py`, `tests/manualqa/test_generate.py`.

**Interfaces — produces:**
- `build_messages(question: str, history: list[dict], evidence: list[Evidence], page_images: list[Path]) -> list[dict]` (OpenAI chat format; images as `image_url` data URLs; each evidence shown as `[<id>] (page N) <text>`).
- System prompt (exact copy in `prompts.py`): answer only from the evidence; output one JSON object per line, `{"claim": "...", "block": "<evidence id>", "quote": "<verbatim text copied from that evidence>"}`; quotes copied exactly, as short as possible but containing every number in the claim; for a figure or page image cite the figure evidence id and set `"quote": ""`; if the evidence does not answer the question output exactly `{"abstain": "<what is missing>"}`; no other text.
- `ClaimParser` with `feed(text: str) -> list[RawClaim]` (returns claims completed by this chunk) and `close() -> list[RawClaim]`; `RawClaim(claim: str, block: str, quote: str, raw: str)`; non-JSON lines go to `parser.ignored`; an `{"abstain": ...}` line sets `parser.abstain`.
- `Generator(base_url, api_key, model)` with `stream(messages) -> Iterator[str]` (SSE text deltas; `temperature=0`, `seed=0`, reasoning disabled through `chat_template_kwargs={"enable_thinking": false}` when the model accepts it) and `from_env()` reading `GEN_*`.

- [ ] Tests: `test_parser_streams_claims` (two claims fed in 7-character pieces → each returned on the feed that completes its line); `test_parser_survives_garbage_and_split_lines` (prose line, broken JSON, valid claim split across three feeds → one claim, two ignored); `test_parser_abstain`; `test_messages_include_images_and_ids` (data URL present, every evidence id appears); `test_generator_parses_sse` (a fake `requests` session yielding SSE lines → concatenated deltas). FAIL → implement → PASS → commit `manualqa: claim-format prompt, streaming claim parser, generator client`.

### Task 5: Answer pipeline

**Files:** create `manualqa/answer.py`, `tests/manualqa/test_answer.py`.

**Interfaces — produces:** `answer(question: str, manual: str, ctx: IngestContext, gen: Generator, history: list[dict] | None = None) -> Answer` and a streaming variant `answer_stream(...) -> Iterator[AnswerEvent]` (events: `claim_shown` after quote match, `claim_settled` after fact checks, `claim_removed`, `abstained`, `done`). `Answer(text: str, claims: list[CheckedClaim], removed: list[CheckedClaim], abstained: bool, abstain_reason: str | None, retrieval: RetrievalResult, unknown_blocks: int, timings: dict)`; `CheckedClaim(claim, block, quote, page, boxes, status: Literal["verified", "figure", "removed"], reason: str | None)`.

Order per claim: unknown block → dropped (counted); figure evidence → figure rule (Global Constraints); else `match_quote` → none → removed "quote not in cited block"; else `check_facts` → fail → removed with reason; else verified. Abstain when `parser.abstain` or no claim is verified/figure. `text` = verified and figure claims joined; the abstain text is fixed: "I could not find the answer in the manual." followed by the pages that were retrieved. Follow-up questions: `history` is passed to the generator as prior turns; rewriting into a standalone question is one extra generator call with a fixed prompt, done only when `history` is non-empty.

- [ ] Tests (fake generator yielding canned lines; context from fixtures): `test_verified_claim_has_boxes`; `test_wrong_quote_removed_with_reason`; `test_cage_trap_removed`; `test_abstains_when_no_claim_survives`; `test_unknown_block_dropped_and_counted`; `test_stream_events_order` (shown before settled; removed claims never shown as verified). FAIL → implement → PASS → commit `manualqa: answer pipeline (checked claims, removal reasons, abstention)`.

### Task 6: v2 system in the eval harness and first dev run

**Files:** modify `evals/run_eval.py` (add `v2` adapter; `--ingest`, `--system v2`); create `tests/manualqa/test_eval_v2.py`; results under `evals/results/` (raw + summary), notes in `evals/results/NOTES-v2-dev.md`.

**Interfaces — produces:** adapter returning the existing record fields (`answer`, `ranked_pages`, `candidate_pages`, `cited_pages` = pages of verified and figure claims, `context` = the evidence text shown, `timings`) plus `claims`, `removed`, `abstained`, `unknown_blocks`, `time_to_first_claim_s`. The harness config records generator model name (from the endpoint, not the host), reranker, embedder, ingest summary hash.

- [ ] Steps: test the adapter with the fake generator (`test_v2_adapter_record_fields`); then on the laptop (stores and models there, generator through the gateway, sequential) run `generate --system v2 --repeats 1` on the 42 dev items, then `score` with the existing judge (judge v2, history judge: Qwen3.8 — labelled as such); write `NOTES-v2-dev.md` (exploratory; per-category table next to v1's; quote-match rate, removed-claim rate and reasons, abstentions, time to first claim; every miss listed with its cause). Commit and push.
