# Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the three manuals into everything the answer path needs: composed page parses whose block text maps exactly to highlight boxes, a SQLite table store with `lookup_table`, structure-aware chunks, page renders, and a hybrid (dense + BM25) Qdrant index.

**Architecture:** The slow GPU step (PaddleOCR on all 363 pages, about 5.5 h) runs once and saves raw parses. Everything else is a deterministic, CPU-only step over those raw parses: *compose* (text-layer lines on trusted pages, cleaned OCR lines elsewhere; block text built from its lines; table cells placed by geometry), then tables, chunks, renders and index. Each step reads files and writes files, so any step can be re-run without the GPU.

**Tech Stack:** Python 3.12, PyMuPDF, rapidfuzz, SQLite (stdlib, FTS5), qdrant-client (local mode), sentence-transformers (Qwen3-Embedding-0.6B as the default embedder; the tuned choice is plan 6), pytest.

**Spec:** `docs/superpowers/specs/2026-11-01-v2-design.md` (Ingestion 1–8, Query 5.1 for what the boxes must support). Inputs: `docs/decisions/001-parser-and-coordinates.md` (open questions 1, 2, 3, 6 and 7 are answered here). Sequence: `docs/superpowers/plans/2026-11-02-tier1-roadmap.md`.

## Global Constraints

- One coordinate system: page-normalised [0,1] boxes, top-left origin of the rendered page; only `manualqa/geometry.py` converts.
- Every highlightable unit (line, table cell, table row) carries the box of the text it shows. A box is never guessed: no box is better than another row's box.
- For every non-table block, `block.text == "\n".join(line.text for line in block.lines)`, so a character span of block text maps to lines without fuzzy alignment. The parser's own text is kept in `block.alt_text`.
- Scanned or malformed pages use OCR lines; trusted pages use the PDF text layer lines (exact text, exact boxes). The choice is recorded per page in `PageParse.text_source` (`"text_layer"` or `"ocr"`).
- Display renders 150 dpi; generator images about 1,000 px on the long edge.
- Data outputs live under `data/` (gitignored). Code, tests, small fixtures and decision records are committed. No LAN addresses, host names or local paths in committed files.
- GPU runs (parse, embeddings) happen on the laptop under the GPU-idle watchdog (kill after 30 s at 0% once busy, resume with `--resume`).
- Formatting: black, isort (profile black), flake8.
- Pushing progress is fine; keep commits small and described.

## Review Focus

1. **Repeated values in tables** (a CAGE code or "PAOZZ" on every row): a cell must get its own row's box or none. Covered by `test_place_cells_repeated_values_stay_in_their_row` (Task 4).
2. **Wrapped cells** (a description over two visual lines) and **rows the OCR missed**: the wrap is one cell with a box covering both lines; a missing row must not shift later rows. Covered by `test_place_cells_wrapped_description` and `test_place_cells_missing_row_does_not_shift` (Task 4).
3. **Tables continued across pages**: a parts list's group (figure) carries over to the next page's table until a new group appears. Covered by `test_group_carries_across_pages` (Task 5).
4. **Running headers, footers and page numbers** ("ARMY TM 9-6115-641-10", "15-1") must not become chunks or dominate BM25. Covered by `test_chunks_skip_running_headers` (Task 6).
5. **Identifiers in search**: "P14-8969" must be findable as a whole token and by its parts. Covered by `test_tokens_keep_identifiers` and `test_hybrid_search_finds_part_number` (Task 8).

---

## File structure

| File | Responsibility |
|---|---|
| `manualqa/blocks.py` (modify) | add `PageParse.text_source`, `Block.alt_text`; loading stays backward compatible |
| `manualqa/textclean.py` | `clean_ocr_text`: PaddleOCR-VL LaTeX to Unicode |
| `manualqa/parsers/textlayer.py` (modify) | expose `text_layer_lines(page, frame) -> list[Line]` |
| `manualqa/compose.py` | raw parse + PDF page → composed parse (line source, block text from lines, cells placed) |
| `manualqa/table_geometry.py` | `place_cells`: lines → table cells by row bands |
| `manualqa/tables.py` | `TableStore` (SQLite + FTS5), header/group derivation, `lookup_table` |
| `manualqa/chunks.py` | `Chunk`, `chunk_manual` |
| `manualqa/render.py` | page renders for display and for the generator |
| `manualqa/index.py` | `Embedder` protocol, embedders, BM25 sparse vectors, `build_index`, `search` |
| `manualqa/ingest.py` | CLI: compose → tables → chunks → renders → index, with a summary report |
| `tests/fixtures/paddle-raw.jsonl` | raw Paddle parses of FAA p16, operator p51, parts p58–p61 (from the spike run; public data) |
| `docs/decisions/002-ingestion.md` | chunk sizes, thresholds, embedder default, hybrid-vs-Paddle result, borderline-page check |

The full raw parse is produced with the existing runner (`python -m evals.spike.run_spike --parser paddle --pages <all pages> --out data/raw --docs data/raw/overlays --resume`); it is already running when this plan starts. A dedicated parse CLI is not added: the runner already saves per page, resumes and isolates failures.

---

### Task 1: Schema additions and OCR text clean-up

**Files:** Modify `manualqa/blocks.py`; create `manualqa/textclean.py`, `tests/manualqa/test_textclean.py`; extend `tests/manualqa/test_blocks.py`.

**Interfaces — produces:**
- `PageParse.text_source: str = "ocr"` (values `"text_layer"`, `"ocr"`); `Block.alt_text: str = ""`. `load_pages` accepts files written before these fields existed.
- `clean_ocr_text(text: str) -> str`.

- [ ] **Step 1: Failing tests**

```python
@pytest.mark.parametrize("raw,clean", [
    ("15 $ \\pm $ 3 psi", "15 ± 3 psi"),
    ("$ 0^{\\circ} \\pm 0.5^{\\circ} $", "0° ± 0.5°"),
    ("at $ 32\\,^{\\circ}F $", "at 32°F"),
    ("$ \\frac{1}{12} $ gallon", "1/12 gallon"),
    ("2-10.2 $ \\underline{\\text{Stopping}} $", "2-10.2 Stopping"),
    ("$ Aileron: Up $ 12.5", "Aileron: Up 12.5"),
    ("no maths here", "no maths here"),
])
def test_clean_ocr_text(raw, clean): assert clean_ocr_text(raw) == clean

def test_load_pages_without_new_fields(tmp_path): # a JSON line lacking text_source/alt_text loads with defaults
def test_round_trip_new_fields(tmp_path):        # text_source="text_layer", alt_text="x" survive dump/load
```

- [ ] **Step 2:** run `pytest tests/manualqa/test_textclean.py tests/manualqa/test_blocks.py`; expect FAIL.
- [ ] **Step 3: Implement.** Inside each `$…$` span: `\pm`→±, `^{\circ}`/`^\circ`→°, `\times`→×, `\leq`→≤, `\geq`→≥, `\approx`→≈, `\mu`→µ, `\%`→%, `\frac{a}{b}`→`a/b`, `\text{…}`/`\mathrm{…}`/`\underline{…}`→contents, `\,`→nothing, other `\word` → word; drop the `$` signs; collapse whitespace. Text outside `$…$` is untouched apart from whitespace collapse at the joins.
- [ ] **Step 4:** tests PASS. **Step 5:** commit `manualqa: text_source and alt_text in the schema; clean PaddleOCR-VL LaTeX`.

### Task 2: Test fixtures from the spike's raw Paddle parses

**Files:** create `tests/fixtures/paddle-raw.jsonl`, `tests/manualqa/test_fixtures.py`.

- [ ] **Step 1:** Copy the raw Paddle `PageParse` lines for FAA p16, operator p51 and parts p58, p59, p60, p61 out of `spike-out/paddle/parses.jsonl` (the spike run at commit `a100a41`) into the fixture file. Check it has no local paths (`grep -E '/home/|192\.168\.'`) and is under 1 MB.
- [ ] **Step 2:** `test_fixture_pages_load_and_validate`: `load_pages` returns 6 pages, `validate` gives no problems, parts p59 has one table block with ≥ 150 cells.
- [ ] **Step 3:** commit `tests: raw PaddleOCR parses of six spike pages as fixtures`.

### Task 3: Compose: line source and block text from lines

**Files:** modify `manualqa/parsers/textlayer.py`; create `manualqa/compose.py`, `tests/manualqa/test_compose.py`.

**Interfaces:**
- Consumes: `needs_ocr`, `render_page`, `assign_lines`, `clean_ocr_text`, fixtures, `place_cells` (Task 4; until then table blocks keep cells as parsed).
- Produces:
  - `text_layer_lines(page: pymupdf.Page, frame: PageFrame) -> list[Line]` (the line extraction `TextLayerParser` already does, factored out; `TextLayerParser` uses it).
  - `compose_page(raw: PageParse, page: pymupdf.Page) -> PageParse`.
  - CLI `python -m manualqa.compose RAW.jsonl --manuals manuals --out COMPOSED.jsonl`.

Behaviour of `compose_page`:
1. Decide the line source with `needs_ocr(page)`: trusted → `text_layer_lines` (`text_source="text_layer"`); flagged → the raw parse's lines with `clean_ocr_text` applied (`text_source="ocr"`).
2. Drop all lines from the raw blocks; re-assign the chosen lines to blocks with `assign_lines`; orphans become `"other"` blocks.
3. Non-table blocks: `alt_text` = raw text cleaned; `text` = lines joined with `\n`; blocks left with no lines keep `text=""` (figures without text are normal).
4. Table blocks: cell texts cleaned; `place_cells(block, block.lines)` (Task 4) sets cell boxes; `text` = cell texts joined row by row (cells separated by ` | `, rows by `\n`).
5. Block ids are re-numbered in reading order after orphans are appended (ids stay `stem:pN:bK`).

- [ ] **Step 1: Failing tests** (fixtures + bundled manuals):

```python
def test_trusted_page_uses_text_layer_lines(manual):   # FAA p16: text_source "text_layer"; every line text equals a PyMuPDF line text
def test_flagged_page_keeps_ocr_lines(manual):         # operator p51: text_source "ocr"; some block text contains "exhaust"
def test_block_text_is_its_lines(manual):              # every non-table block of both pages: text == "\n".join(lines)
def test_alt_text_keeps_parser_text(manual):           # FAA p16 heading block alt_text == cleaned raw text
def test_composed_pages_validate(manual):              # validate() == [] for all six fixture pages
```

- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS. **Step 5:** commit `manualqa: compose parses (text-layer lines on trusted pages, block text from lines)`.

### Task 4: Table cells placed by geometry

**Files:** create `manualqa/table_geometry.py`, `tests/manualqa/test_table_geometry.py`.

**Interfaces — produces:** `place_cells(block: Block, lines: list[Line]) -> None` (sets `Cell.box`; never moves a line to another HTML row). Also `row_boxes(block: Block) -> dict[int, Box]` (union of the row's cell boxes; rows with no boxed cell absent).

Algorithm (the tests pin the behaviour; this is the part the signature does not determine):

```text
1. Visual rows: sort lines by centre y; start a new visual row when a line's centre y exceeds
   the current row's mean centre y by more than 0.6 × median line height.
2. Row alignment: score(html_row i, visual_row j) = share of row i's non-empty cells whose
   norm text is found in visual row j's joined norm text (rapidfuzz partial_ratio >= 90).
   Dynamic programming over (i, j), monotonic in both: each html row takes 0..3 consecutive
   visual rows (0 = OCR missed it); maximise total score; a visual row joins a span only if it
   adds score > 0 to that html row. Unmatched visual rows are skipped.
3. Within an aligned html row: give each line to the cell in that row with the highest
   partial_ratio(norm(line), norm(cell)) >= 85; ties go to the cell whose column order matches
   the line's left-to-right position among the row's lines.
4. Cell box = union of its lines' boxes; cells with no line keep box=None.
```

- [ ] **Step 1: Failing tests** (synthetic `Block`s built in the test; one real fixture test):

```python
def test_place_cells_simple_grid():                       # 2×3 grid, one line per cell -> each cell's box == its line's box
def test_place_cells_repeated_values_stay_in_their_row(): # 3 rows each with "68505" and "PAOZZ": every cell's box has the y of its own row
def test_place_cells_wrapped_description():               # "HOSE,PREFORMED AIR" + "FILTER" on two visual lines -> one cell, box = union
def test_place_cells_missing_row_does_not_shift():        # html rows 1..4, OCR lines only for rows 1, 2, 4 -> row 3 cells None, row 4 boxed in row 4's band
def test_row_boxes_union():                               # row box covers all boxed cells of the row
def test_parts_p59_rows(manual):                          # composed fixture p59: cell "P14-8969" and the row's "18265" have boxes in the same visual row, which contains the text-layer line "P14-8969"
```

- [ ] **Step 2:** FAIL. **Step 3:** implement; wire into `compose_page`. **Step 4:** PASS, plus Task 3 tests still PASS. **Step 5:** commit `manualqa: place table cells by row bands, never across rows`.

### Task 5: Table store and `lookup_table`

**Files:** create `manualqa/tables.py`, `tests/manualqa/test_tables.py`.

**Interfaces — produces:**
- `derive_table(block: Block) -> TableInfo` with `header: list[str]` (one label per column, header rows joined with spaces), `header_rows: int`, `groups: dict[int, str]` (row → group label).
- `TableStore(path: Path)` with `add_page(pp: PageParse) -> None` (in page order; carries the current group across pages of one manual), `lookup_table(query: str | None = None, columns: dict[str, str] | None = None, manual: str | None = None, figure: str | None = None, limit: int = 10) -> list[RowHit]`.
- `RowHit(table_id: str, manual: str, page: int, block_id: str, row: int, header: list[str], cells: list[str], cell_boxes: list[Box | None], row_box: Box | None, group: str | None, figure: str | None)`.

Rules (generic, not parts-specific):
- **Header rows:** parser-flagged header cells if any; otherwise the leading rows before the first *data row*, a row with at least two non-empty cells containing a digit that is not a column number in parentheses like "(3)".
- **Group label:** in a non-data row, a cell of 20+ characters. It applies to following rows (and following pages of the same manual) until the next group label. `figure` = the number after `FIG`/`FIGURE` in the group label, if any.
- **Storage:** SQLite tables `tables` and `rows`, plus an FTS5 table over each row's cell texts and group. `columns` filters match a header label by `partial_ratio(norm(key), norm(label)) >= 80` and the cell value by `norm` equality.

- [ ] **Step 1: Failing tests:**

```python
def test_header_and_group_parts_p59(manual):  # composed fixture p59: header has a label containing "part number"; group of row "17" contains "FIG 15"; figure == "15"
def test_lookup_by_item_in_figure(tmp_path, manual):   # store from fixtures: columns={"item": "17"}, figure="15" -> one hit; its cells contain "P14-8969" and "18265"; row_box is not None
def test_lookup_by_part_number(tmp_path, manual):      # query="P14-8969" -> the same row first
def test_lookup_returns_header_with_row(tmp_path, manual):  # hit.header has the same length as hit.cells
def test_group_carries_across_pages(tmp_path):         # two synthetic pages: p1 table with group "FIG 4 X", p2 table without group -> p2 rows have figure "4"
def test_no_hit_returns_empty(tmp_path, manual):       # columns={"item": "999"} -> []
```

- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS. **Step 5:** commit `manualqa: SQLite table store with lookup_table (rows with headers, groups, boxes)`.

### Task 6: Chunks

**Files:** create `manualqa/chunks.py`, `tests/manualqa/test_chunks.py`.

**Interfaces — produces:** `Chunk(id: str, manual: str, pages: list[int], kind: Literal["text", "table", "figure"], heading: str, text: str, block_ids: list[str])`; `chunk_manual(pages: list[PageParse]) -> list[Chunk]`; `dump_chunks`/`load_chunks` (JSON lines). Values: `MAX_CHARS = 1500` per text chunk; `TABLE_ROWS_PER_CHUNK = 25`.

Rules: blocks in reading order across pages; a heading starts a new text chunk and becomes its `heading` (the heading text is also the first line of `text`); text blocks accumulate until adding one would pass `MAX_CHARS` (a single longer block becomes its own chunk); a table is its own chunk (caption if a caption block touches it, header line, then up to 25 rows, header repeated in each part); a figure becomes a chunk only when it has text (its lines, plus its caption); `"other"` blocks in the top or bottom 8% of the page (running headers, footers, page numbers) are skipped.

- [ ] **Step 1: Failing tests:** `test_heading_starts_chunk`, `test_text_chunk_size_limit`, `test_table_chunk_repeats_header` (60-row synthetic table → 3 chunks, each starting with the header line), `test_figure_with_text_becomes_chunk` (rating-plate-like figure with lines), `test_chunks_skip_running_headers` (an "ARMY TM 9-6115-641-10" `other` block at y < 0.08 is in no chunk), `test_chunk_ids_stable` (same input → same ids).
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5:** commit `manualqa: structure-aware chunks (sections, tables with headers, figures with text)`.

### Task 7: Page renders

**Files:** create `manualqa/render.py`, `tests/manualqa/test_render.py`.

**Interfaces — produces:** `render_manual(pdf: Path, out_dir: Path) -> dict[int, tuple[Path, Path]]`, writing `out_dir/<stem>/p<NNN>.jpg` (150 dpi, quality 85, display) and `p<NNN>-gen.jpg` (long edge 1000 px, quality 90, generator). Skips files that exist.

- [ ] Tests: `test_render_sizes` (FAA p16: display width equals `render_page(..., 150)` width; generator long edge 1000), `test_render_skips_existing` (second call does not rewrite: mtime unchanged). FAIL → implement → PASS → commit `manualqa: page renders for display and generator`.

### Task 8: Hybrid index

**Files:** create `manualqa/index.py`, `tests/manualqa/test_index.py`.

**Interfaces — produces:**
- `class Embedder(Protocol): name: str; dim: int; def embed(self, texts: list[str], query: bool = False) -> list[list[float]]`.
- `SentenceTransformerEmbedder(model: str = "Qwen/Qwen3-Embedding-0.6B", device: str | None = None)` (query prompt per the model card when `query=True`); `OpenAIEmbedder(base_url: str, model: str, api_key: str | None)` (calls `/v1/embeddings`; settings from `.env`).
- `tokens(text: str) -> list[str]`: lowercase word tokens; an identifier with hyphens or digits is kept whole *and* split ("P14-8969" → `p14-8969`, `p14`, `8969`).
- `sparse_vector(text: str) -> tuple[list[int], list[float]]`: term ids by a stable hash (`zlib.crc32`), values = BM25 term-frequency saturation (k1 = 1.2, b = 0.75 with the corpus average length passed in); IDF applied by Qdrant (`Modifier.IDF`).
- `build_index(chunks: list[Chunk], path: Path | str, embedder: Embedder) -> None` (collection `chunks`, named vectors `dense` and `bm25`, payload = chunk fields); `search(query: str, path, embedder, k: int = 10, manual: str | None = None) -> list[tuple[Chunk, float]]` (Query API: prefetch dense and sparse, fuse with RRF; filter by manual).

- [ ] **Step 1: Failing tests** (a deterministic fake embedder hashing tokens into 64 dims; Qdrant local in a tmp dir):

```python
def test_tokens_keep_identifiers():          # tokens("Part P14-8969, CAGE 18265") ⊇ {"p14-8969", "p14", "8969", "18265", "part", "cage"}
def test_sparse_vector_stable():             # same text -> same indices and values; different word order -> same set
def test_hybrid_search_finds_part_number(tmp_path):   # 3 chunks; query "P14-8969" -> the chunk containing it ranks first
def test_search_filters_by_manual(tmp_path): # manual filter excludes other manuals' chunks
```

- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5:** commit `manualqa: hybrid Qdrant index (dense + BM25 sparse, RRF)`.

### Task 9: Ingest CLI, full run and decision record

**Files:** create `manualqa/ingest.py`, `tests/manualqa/test_ingest.py`, `docs/decisions/002-ingestion.md`; modify `.gitignore` (`data/`), `README.md` (progress row).

**Interfaces — produces:** `python -m manualqa.ingest --raw data/raw/paddle/parses.jsonl --manuals manuals --out data/ingest [--embedder st:Qwen/Qwen3-Embedding-0.6B | openai:<model>] [--skip-index]` writing `composed.jsonl`, `tables.sqlite`, `chunks.jsonl`, `pages/`, `qdrant/` and `summary.json` (pages per text source, blocks, chunks per kind, tables, rows, rows with boxes, cells with boxes, time per step).

- [ ] **Step 1:** `test_ingest_fixtures_end_to_end(tmp_path)`: fixtures through the CLI with `--skip-index` → files exist; `summary.json` counts match the fixtures; `lookup_table` on the output finds P14-8969.
- [ ] **Step 2–4:** FAIL → implement → PASS; commit `manualqa: ingest CLI`.
- [ ] **Step 5: Hybrid vs Paddle on the spike pages** (decision 001, open question 1): compose the spike's raw Paddle parses, re-score with `run_spike --parser hybrid --parses <composed>`, and compare with the Paddle row (cell checks, cells with boxes, coordinate agreement on trusted pages, CER on letter-spaced pages).
- [ ] **Step 6: Full run.** When the laptop's full parse has finished, run ingest on the laptop (embeddings on its GPU), copy `summary.json` back, and look at 10 composed overlays (two per page type, including two borderline letter-spaced operator pages, open question 6).
- [ ] **Step 7:** write `docs/decisions/002-ingestion.md` (the hybrid result, thresholds and why, the default embedder and that plan 6 chooses the real one, the borderline-page check, open questions for plan 3); update the README progress row; commit; push.
