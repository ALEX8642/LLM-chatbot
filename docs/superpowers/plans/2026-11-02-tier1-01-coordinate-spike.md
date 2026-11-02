# Coordinate Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Settle OCR handling and the coordinate pipeline before anything else: 10 pages per manual through two parser candidates (plus the PDF text layer as a reference), every box in one page-normalised coordinate system, overlays committed as reference images, and a decision record that picks the parser for the thin slice.

**Architecture:** A new package `manualqa/` holds the v2 code. One module owns coordinates (`geometry.py`: render a page and map PDF points or pixels to [0,1] boxes on that render); a block schema (`blocks.py`) is the contract every parser adapter emits; an OCR detector decides per page whether the text layer can be trusted. Parser adapters for Docling and PaddleOCR-VL run on the laptop GPU; a spike runner under `evals/spike/` produces overlays and metrics for the decision record.

**Tech Stack:** Python 3.12, uv, PyMuPDF, Pillow, rapidfuzz, pytest; Docling and PaddleOCR 3.x (PaddleOCR-VL 1.6, PP-OCRv5, table-cell detection) as conflicting optional extras.

**Spec:** `docs/superpowers/specs/2026-11-01-v2-design.md` (Ingestion steps 1–3, Process step 1, Tier 1 "Coordinate spike with 2 parsers, forced OCR, one coordinate system"). Sequence: `docs/superpowers/plans/2026-11-02-tier1-roadmap.md`.

## Global Constraints

- Public repo, MIT. No secrets, LAN addresses or host names in committed files (results, logs, decision records).
- Every box is stored in page-normalised [0,1] coordinates, origin top-left of the rendered page, measured on the same rendered image used for display; origin, CropBox/MediaBox and rotation are handled once, in `manualqa/geometry.py`, with tests.
- Display renders are 150 dpi.
- Scanned or malformed pages are always OCR'd; the embedded text layer is ignored when malformed. Detection is automatic and logged (reason stored per page).
- Block coordinates are a hard requirement for a parser; a parser that cannot give block boxes is rejected.
- Parsers and OCR run in-process on the laptop (WSL Ubuntu-24.04, RTX 4090 16 GB). Nothing runs on, or changes, the Sparks.
- Permissive licences only without a licence decision: Docling (MIT) and PaddleOCR (Apache-2.0) qualify; MinerU and Marker are out of this spike. Record the date licences were checked.
- Model weights and downloaded data are never committed.
- Page numbers are 1-based PDF page indexes, as in `evals/qa.jsonl`.
- Formatting: black + isort (profile black) + flake8 (`.flake8`), for `manualqa/`, `evals/spike/` and `tests/manualqa/`.
- Code reaches the laptop as a git bundle, not via GitHub. Nothing is pushed until Alex has approved the commit list.

## Review Focus

1. **Rendered size rounding.** PyMuPDF pixmap sizes are rounded; a frame computed from points × dpi instead of the actual pixmap is off by up to a pixel per edge. `PageFrame` takes its pixel size from the pixmap it rendered (test in Task 1).
2. **Mixed box origins from one parser.** Docling boxes carry `coord_origin` per box (TOPLEFT or BOTTOMLEFT); a single assumed origin flips some boxes vertically. The adapter converts per box (test in Task 6).
3. **Blank and image-only pages** (FAA page 1 has no text at all). A parser returning zero blocks must not crash the runner, and metrics must report "no data", not 0 (test in Task 5).
4. **One parser failure on one page** must not lose the other 29 pages: the error is stored on that page's `PageParse` and counted in the report (test in Task 5).
5. **Unicode differences in cell checks** ("±", ligatures, non-breaking spaces, case). Matching normalises with NFKC, case folding and whitespace collapse (test in Task 4).

---

## File structure

| File | Responsibility |
|---|---|
| `manualqa/__init__.py` | empty |
| `manualqa/geometry.py` | `Box`, `PageFrame`, `render_page`: the only place that knows about PDF origins, CropBox and rotation |
| `manualqa/blocks.py` | `Line`, `Cell`, `Block`, `PageParse`; JSONL dump/load; `validate` |
| `manualqa/ocr_detect.py` | `OcrDecision`, `needs_ocr(page)` |
| `manualqa/textnorm.py` | `norm(text)` used by every text comparison |
| `manualqa/overlay.py` | `draw_overlay(image, page_parse)` |
| `manualqa/parsers/__init__.py` | `Parser` protocol, `get_parser(name)` (lazy imports) |
| `manualqa/parsers/common.py` | `assign_lines(blocks, lines)`, `html_table_cells(html)` |
| `manualqa/parsers/textlayer.py` | reference parser: PDF text layer lines, no OCR |
| `manualqa/parsers/docling_parser.py` | Docling adapter |
| `manualqa/parsers/paddle_parser.py` | PaddleOCR-VL + PP-OCRv5 + table-cell detection adapter |
| `evals/spike/pages.json` | the 30 spike pages |
| `evals/spike/expectations.json` | table-cell checks taken from `evals/qa.jsonl` reference answers |
| `evals/spike/metrics.py` | coordinate agreement, OCR CER, cell checks |
| `evals/spike/run_spike.py` | runner: parse → JSONL, overlays, metrics |
| `evals/spike/report.py` | metrics of all parsers → markdown table |
| `docs/spike/<parser>/*.jpg`, `docs/spike/<parser>/metrics.json` | committed reference overlays and metrics |
| `docs/decisions/001-parser-and-coordinates.md` | decision record |
| `tests/manualqa/…` | tests, one file per module |

Spike pages (`evals/spike/pages.json`), chosen from the page profile of 2026-11-02 to cover every page type, mostly gold pages of dev items:

```json
{
  "FAA_Weight_and_Balance_Handbook.pdf": [16, 19, 28, 29, 31, 36, 37, 50, 53, 67],
  "Army_5kW_Generator_Operator_Manual.pdf": [22, 23, 24, 25, 28, 51, 52, 57, 70, 72],
  "Army_5kW_Generator_Parts_Manual.pdf": [11, 12, 19, 20, 21, 58, 59, 60, 61, 130]
}
```

FAA: two-column prose (16), tables (28, 36, 67), vector-drawn text with no text layer (31), charts (50, 53). Operator: tables (22–24), photos with labels (25, 28), letter-spaced text layer (51, 52, 70, 72), rating-plate image (57). Parts: exploded views (11, 19, 58, 60), parts-list tables (12, 20, 21, 59, 61), cross-reference index (130). No page in the three manuals is rotated or has a CropBox different from its MediaBox, so rotation and CropBox are covered by synthetic tests only.

---

### Task 1: Package, geometry and CI

**Files:**
- Create: `manualqa/__init__.py`, `manualqa/geometry.py`, `tests/manualqa/__init__.py`, `tests/manualqa/test_geometry.py`
- Modify: `pyproject.toml` (deps, extras, pytest marker), `.github/workflows/ci.yml`

**Interfaces:**
- Produces:
  - `Box(x0: float, y0: float, x1: float, y1: float)`, frozen dataclass, page-normalised, top-left origin; `Box.iou(other: Box) -> float`; `Box.to_px(width: int, height: int) -> tuple[int, int, int, int]`; `Box.center -> tuple[float, float]`.
  - `PageFrame` (frozen dataclass: `width_px: int`, `height_px: int`, `dpi: int`, plus whatever it needs privately) with `from_pdf_topleft(x0, y0, x1, y1) -> Box` (PyMuPDF's unrotated page coordinates, as returned by `page.get_text("dict")` and used by `page.draw_rect`), `from_pdf_user(x0, y0, x1, y1) -> Box` (raw PDF user space: MediaBox origin, y up), `from_px(x0, y0, x1, y1, width_px: int, height_px: int) -> Box` (pixels on any render of this page at any dpi).
  - `render_page(page: pymupdf.Page, dpi: int = 150) -> tuple[PIL.Image.Image, PageFrame]`: the frame's pixel size is the rendered pixmap's size.

- [ ] **Step 1: Write the failing tests** in `tests/manualqa/test_geometry.py`.

Helper `dark_bbox(img) -> tuple[int,int,int,int]`: bounding box of pixels with all channels < 64. Helper `make_page(rotation, cropbox)`: new `pymupdf` document, one 612×792 pt page, `set_cropbox(cropbox)` when given, then `set_rotation(rotation)`.

```python
CASES = [(r, c) for r in (0, 90, 180, 270) for c in (None, (50, 60, 562, 752))]

@pytest.mark.parametrize("rotation,cropbox", CASES)
def test_topleft_rect_lands_on_rendered_pixels(rotation, cropbox):
    page = make_page(rotation, cropbox)
    rect = (100, 150, 200, 250)            # inside the crop box
    page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))
    img, frame = render_page(page, dpi=150)
    box = frame.from_pdf_topleft(*rect)
    assert box.to_px(*img.size) == pytest.approx(dark_bbox(img), abs=2)

@pytest.mark.parametrize("rotation,cropbox", CASES)
def test_user_space_rect_lands_on_rendered_pixels(rotation, cropbox):
    page = make_page(rotation, cropbox)
    # raw content stream: y-up user space, MediaBox origin
    append_stream(page, b"0 0 0 rg 100 300 100 100 re f")
    img, frame = render_page(page, dpi=150)
    assert frame.from_pdf_user(100, 300, 200, 400).to_px(*img.size) == pytest.approx(dark_bbox(img), abs=2)

def test_frame_size_is_the_pixmap_size():
    page = make_page(0, (0.3, 0.3, 300.7, 400.9))   # fractional points round
    img, frame = render_page(page, dpi=150)
    assert (frame.width_px, frame.height_px) == img.size

def test_from_px_is_resolution_independent():
    page = make_page(90, None)
    _, frame = render_page(page, dpi=150)
    a = frame.from_px(100, 200, 300, 400, 1000, 2000)
    b = frame.from_px(200, 400, 600, 800, 2000, 4000)
    assert a == b == Box(0.1, 0.1, 0.3, 0.2)

def test_box_iou():
    assert Box(0, 0, 0.5, 0.5).iou(Box(0, 0, 0.5, 0.5)) == 1
    assert Box(0, 0, 0.5, 0.5).iou(Box(0.5, 0.5, 1, 1)) == 0
    assert Box(0, 0, 0.4, 0.4).iou(Box(0.2, 0, 0.6, 0.4)) == pytest.approx(1 / 3)
```

`append_stream(page, data)`: create a new content stream object with `doc.get_new_xref()` / `doc.update_object` + `doc.update_stream` and append it to the page's `/Contents` array (`doc.xref_set_key`). The pixel truth must not come from code under test.

- [ ] **Step 2: Run** `uv run pytest tests/manualqa/test_geometry.py -v`. Expected: FAIL (`ModuleNotFoundError: manualqa`).

- [ ] **Step 3: Implement `manualqa/geometry.py`.** Build the mapping from PyMuPDF's own matrices so the rotation and CropBox logic is not re-derived: `page.transformation_matrix` (user space → unrotated top-left space), `page.rotation_matrix` (unrotated → rotated display), then scale to `page.rect` (rotated, cropped, 0-origin) and divide by its width and height. `render_page` uses `page.get_pixmap(dpi=dpi)` and converts to a Pillow RGB image. Normalised boxes are clamped to [0,1] and ordered (x0 ≤ x1, y0 ≤ y1) after rotation.

- [ ] **Step 4: Run** `uv run pytest tests/manualqa/test_geometry.py -v`. Expected: 19 passed.

- [ ] **Step 5: Project wiring.**
  - `pyproject.toml`: add `pillow` and `rapidfuzz` to `dependencies`; add extras `docling = ["docling"]` and `paddle = ["paddleocr[doc-parser]", "paddlepaddle-gpu"]` with the Paddle index under `[tool.uv.sources]` / `[[tool.uv.index]]` per the PaddleOCR 3.x install guide for the laptop's CUDA (check current docs with context7 before writing the pins); declare `[tool.uv] conflicts = [[{ extra = "docling" }, { extra = "paddle" }]]`; register pytest marker `parsers: needs a GPU parser extra; run with MANUALQA_PARSERS=1`; add `"manualqa*"` to package discovery if needed so `import manualqa` works under `uv run`.
  - `tests/manualqa/conftest.py`: skip tests marked `parsers` unless `MANUALQA_PARSERS=1`.
  - CI: `uv sync --extra dev` (not `--all-extras`, which now conflicts); run black, isort and flake8 on `api.py backend/ manualqa/ evals/spike/ tests/manualqa/`.
  - Run: `uv sync --extra dev && uv run pytest tests/ -q && uv run black --check manualqa tests/manualqa && uv run flake8 manualqa tests/manualqa`. Expected: all pass, no lint output.

- [ ] **Step 6: Commit**

```bash
git add manualqa tests/manualqa pyproject.toml uv.lock .github/workflows/ci.yml
git commit -m "manualqa: one coordinate system (render, PDF points and pixels to page-normalised boxes)"
```

### Task 2: Block schema

**Files:**
- Create: `manualqa/blocks.py`, `tests/manualqa/test_blocks.py`

**Interfaces:**
- Consumes: `Box` (Task 1).
- Produces:
  - `Line(text: str, box: Box)`
  - `Cell(row: int, col: int, text: str, box: Box | None, header: bool = False)` (0-based row and col; `box` is None when the parser gives no cell box)
  - `Block(id: str, kind: Kind, text: str, box: Box, lines: list[Line] = [], cells: list[Cell] = [])` with `Kind = Literal["text", "heading", "table", "figure", "caption", "other"]`; ids are `f"{manual_stem}:p{page}:b{n}"`, n 0-based in reading order
  - `PageParse(manual: str, page: int, parser: str, width_px: int, height_px: int, dpi: int, ocr: bool, ocr_reason: str | None, blocks: list[Block], seconds: float, error: str | None = None)`
  - `dump_pages(pages: Iterable[PageParse], path: Path) -> None` (JSON lines, one page per line), `load_pages(path: Path) -> list[PageParse]`
  - `validate(pp: PageParse) -> list[str]`: human-readable problems; empty list means valid

- [ ] **Step 1: Write the failing tests**

```python
def test_round_trip(tmp_path): # a PageParse with a table block (cells, one with box=None), a text block with lines
    dump_pages([pp], tmp_path / "p.jsonl")
    assert load_pages(tmp_path / "p.jsonl") == [pp]

def test_validate_accepts_good_page():
    assert validate(pp) == []

@pytest.mark.parametrize("bad,needle", [
    (Box(-0.1, 0, 0.5, 0.5), "outside"),
    (Box(0.6, 0, 0.5, 0.5), "x0 > x1"),
])
def test_validate_flags_bad_boxes(bad, needle): ...  # a block (or a line, or a cell) with the bad box → one problem containing needle

def test_validate_flags_duplicate_ids(): ...  # two blocks with the same id → problem containing "duplicate id"
def test_validate_flags_table_without_cells(): ...  # kind "table", cells [] → "table without cells"
```

- [ ] **Step 2: Run** `uv run pytest tests/manualqa/test_blocks.py -v`. Expected: FAIL (import error).
- [ ] **Step 3: Implement** with dataclasses and `dataclasses.asdict`; loading rebuilds nested dataclasses explicitly (no pickle, no third-party schema library).
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "manualqa: block schema shared by all parsers"`

### Task 3: OCR detection and the text-layer reference parser

**Files:**
- Create: `manualqa/ocr_detect.py`, `manualqa/parsers/__init__.py`, `manualqa/parsers/textlayer.py`, `tests/manualqa/test_ocr_detect.py`, `tests/manualqa/test_textlayer.py`

**Interfaces:**
- Consumes: `render_page`, `PageFrame` (Task 1); `Line`, `Block`, `PageParse` (Task 2).
- Produces:
  - `OcrDecision(ocr: bool, reason: str | None, letter_spaced: float, image_cover: float, text_chars: int, drawings: int)`; reasons are exactly `"letter_spaced"`, `"image_cover"`, `"vector_text"`, `"no_text"`.
  - `needs_ocr(page: pymupdf.Page) -> OcrDecision`
  - `class Parser(Protocol): name: str; def parse(self, pdf: Path, pages: list[int], ocr: dict[int, OcrDecision]) -> list[PageParse]`
  - `get_parser(name: str) -> Parser` for `"textlayer"`, `"docling"`, `"paddle"`; heavy libraries are imported only inside the chosen adapter module.
  - `TextLayerParser`: one `"text"` block per PyMuPDF text block, its lines from `page.get_text("dict")`, boxes through `PageFrame.from_pdf_topleft`; it never OCRs (it is the reference, not a candidate) but copies `ocr`/`ocr_reason` from the decision it is given.

Thresholds (constants in `ocr_detect.py`, from the 2026-11-02 profile: normal pages have letter-spaced ratio ≤ 0.26 except 17 borderline operator pages in 0.3–0.8; 42 operator pages are ≥ 0.8):
`LETTER_SPACED_MIN = 0.5` (share of whitespace-separated tokens that are one character), `IMAGE_COVER_MIN = 0.3` (share of page area covered by raster images), `VECTOR_TEXT_DRAWINGS_MIN = 500` with `VECTOR_TEXT_CHARS_MAX = 200`, `NO_TEXT_CHARS_MAX = 20`. Checked in that order; the first that fires is the reason.

- [ ] **Step 1: Write the failing tests** (they open the bundled manuals; `manual(name)` is a fixture returning an open `pymupdf.Document`):

```python
@pytest.mark.parametrize("pdf,page,reason", [
    ("Army_5kW_Generator_Operator_Manual.pdf", 51, "letter_spaced"),
    ("Army_5kW_Generator_Operator_Manual.pdf", 70, "letter_spaced"),
    ("Army_5kW_Generator_Operator_Manual.pdf", 57, "image_cover"),
    ("Army_5kW_Generator_Parts_Manual.pdf", 58, "image_cover"),
    ("FAA_Weight_and_Balance_Handbook.pdf", 31, "vector_text"),
    ("FAA_Weight_and_Balance_Handbook.pdf", 1, "image_cover"),
    ("FAA_Weight_and_Balance_Handbook.pdf", 16, None),
    ("Army_5kW_Generator_Operator_Manual.pdf", 22, None),
    ("Army_5kW_Generator_Parts_Manual.pdf", 20, None),
])
def test_needs_ocr(manual, pdf, page, reason):
    d = needs_ocr(manual(pdf)[page - 1])
    assert (d.ocr, d.reason) == (reason is not None, reason)

def test_textlayer_finds_known_line(): # FAA p16: some Line whose norm(text) contains "aircraft can perform safely"; its box lies in the top half (y1 < 0.5)
def test_textlayer_pages_validate():   # parse FAA [16, 28] → validate() == [] for each page, page/manual/parser fields set
```

If FAA page 1 (cover, image, no text) does not come out as `image_cover`, check its image cover before changing the expectation; it must still be flagged, by `image_cover` or `no_text`.

- [ ] **Step 2: Run** `uv run pytest tests/manualqa/test_ocr_detect.py tests/manualqa/test_textlayer.py -v`. Expected: FAIL (import errors).
- [ ] **Step 3: Implement.** Image cover: union-free sum of `page.get_image_info()` boxes clipped to `page.rect`, divided by page area, capped at 1. Drawings: `len(page.get_drawings())`.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then log the flag counts for the whole of each manual (a one-off `uv run python -c` loop) and paste them into the commit message body.
- [ ] **Step 5: Commit** `git commit -m "manualqa: detect pages whose text layer cannot be trusted; text-layer reference parser"`

### Task 4: Text normalisation and overlays

**Files:**
- Create: `manualqa/textnorm.py`, `manualqa/overlay.py`, `tests/manualqa/test_textnorm.py`, `tests/manualqa/test_overlay.py`

**Interfaces:**
- Consumes: `Box`, `PageParse` and friends.
- Produces:
  - `norm(text: str) -> str`: NFKC, case-folded, every whitespace run (including NBSP) collapsed to one space, stripped. Later plans' quote matching extends this; this plan needs only these rules.
  - `draw_overlay(image: PIL.Image.Image, pp: PageParse, long_edge: int = 1100) -> PIL.Image.Image`: block outlines 3 px by kind (text `#1f77b4`, heading `#9467bd`, table `#2ca02c`, figure `#ff7f0e`, caption `#7f7f7f`, other `#8c564b`), lines 1 px `#17becf`, cells 1 px `#2ca02c`, block id at each block's top-left; when `pp.ocr`, a red banner `OCR: <reason>` across the top; when `pp.error`, a red banner with the error's first 80 characters. Output resized so its long edge is `long_edge`.

- [ ] **Step 1: Write the failing tests**

```python
def test_norm():
    assert norm("15 ± 3 PSI") == "15 ± 3 psi"
    assert norm("ﬁlter  element\n") == "filter element"

def test_overlay_draws_block_outline_and_leaves_inside_clear():
    img = Image.new("RGB", (1000, 1000), "white")
    pp = page_with_block(kind="text", box=Box(0.1, 0.1, 0.5, 0.5))
    out = draw_overlay(img, pp, long_edge=1000)
    assert out.getpixel((100, 300)) == ImageColor.getrgb("#1f77b4")
    assert out.getpixel((300, 300)) == (255, 255, 255)

def test_overlay_resizes_long_edge():
    out = draw_overlay(Image.new("RGB", (1275, 1650), "white"), page_with_block(), long_edge=1100)
    assert max(out.size) == 1100

def test_overlay_marks_ocr_pages():   # pp.ocr=True → some pixel in the top 20 rows is red (255, 0, 0)
```

- [ ] **Step 2: Run** `uv run pytest tests/manualqa/test_textnorm.py tests/manualqa/test_overlay.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with `unicodedata` and `PIL.ImageDraw` (default font). Draw on the full-size image, then resize with `Image.LANCZOS`, so line widths are measured at render resolution.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "manualqa: overlay renderer for parse inspection"`

### Task 5: Spike metrics and runner (with the text-layer parser)

**Files:**
- Create: `evals/spike/__init__.py`, `evals/spike/pages.json` (content above), `evals/spike/expectations.json`, `evals/spike/metrics.py`, `evals/spike/run_spike.py`, `evals/spike/report.py`, `tests/manualqa/test_spike.py`
- Modify: `.gitignore` (add `spike-out/`)

**Interfaces:**
- Consumes: everything above; `get_parser`, `needs_ocr`, `render_page`, `draw_overlay`, `dump_pages`, `norm`.
- Produces:
  - `coord_agreement(pp: PageParse, ref: list[Line]) -> float | None`: for each reference line, the parser line with the highest `rapidfuzz.fuzz.ratio` on `norm` text, kept if ≥ 90; median IoU over kept pairs; `None` if no pairs.
  - `ocr_cer(pp: PageParse, ref_text: str) -> float | None`: Levenshtein normalised distance (`rapidfuzz.distance.Levenshtein.normalized_distance`) between all block texts in order and `ref_text`, both `norm`ed with all whitespace removed; `None` if either is empty.
  - `cell_checks(pp: PageParse, checks: list[dict]) -> list[dict]`: each check `{"manual", "page", "value", "match": "exact"|"contains", "row_has": str | None}` passes when a cell's `norm` text equals (or contains) `norm(value)` and, if `row_has` is set, another cell in the same block and row contains `norm(row_has)`; result adds `"passed": bool`, `"cell_has_box": bool`.
  - CLI: `uv run python -m evals.spike.run_spike --parser NAME [--pages evals/spike/pages.json] [--out spike-out] [--docs docs/spike]` writes `spike-out/NAME/parses.jsonl`, `docs/spike/NAME/<stem>-p<NNN>.jpg` (quality 80) and `docs/spike/NAME/metrics.json` (per page: ocr, ocr_reason, seconds, error, block/line/cell counts, share of table cells with boxes, validate problems, coord agreement against the text layer on non-OCR pages, CER against the text layer on `letter_spaced` pages; plus the cell-check results and parser package versions).
  - CLI: `uv run python -m evals.spike.report docs/spike/*/metrics.json` prints one markdown table, one row per parser: pages parsed, errors, validate problems, median coordinate agreement, median CER on letter-spaced pages, cell checks passed/total, cells with boxes, seconds per page.

`expectations.json` (values from the reference answers in `evals/qa.jsonl`):

```json
[
  {"manual": "Army_5kW_Generator_Parts_Manual.pdf", "page": 59, "value": "P14-8969", "match": "exact", "row_has": "18265"},
  {"manual": "Army_5kW_Generator_Parts_Manual.pdf", "page": 61, "value": "R28", "match": "exact", "row_has": "78225"},
  {"manual": "Army_5kW_Generator_Parts_Manual.pdf", "page": 12, "value": "88-20243", "match": "exact", "row_has": "30554"},
  {"manual": "Army_5kW_Generator_Parts_Manual.pdf", "page": 20, "value": "105-269", "match": "exact", "row_has": "68505"},
  {"manual": "Army_5kW_Generator_Parts_Manual.pdf", "page": 20, "value": "105-311", "match": "exact", "row_has": "68505"},
  {"manual": "Army_5kW_Generator_Parts_Manual.pdf", "page": 21, "value": "112-95", "match": "exact", "row_has": "ROTOR"},
  {"manual": "Army_5kW_Generator_Operator_Manual.pdf", "page": 24, "value": "15 ± 3", "match": "contains", "row_has": null},
  {"manual": "Army_5kW_Generator_Operator_Manual.pdf", "page": 23, "value": "0.55", "match": "contains", "row_has": null},
  {"manual": "FAA_Weight_and_Balance_Handbook.pdf", "page": 28, "value": "3,050", "match": "contains", "row_has": null},
  {"manual": "FAA_Weight_and_Balance_Handbook.pdf", "page": 36, "value": "6.68", "match": "contains", "row_has": null}
]
```

Before committing it, open each page's text layer and confirm each value appears there as written; fix the value (not the reference answer) if the manual writes it differently, and note any change in the commit message.

- [ ] **Step 1: Write the failing tests**

```python
def test_coord_agreement_identical_lines_is_one():   # pp built from ref lines → 1.0
def test_coord_agreement_no_text_match_is_none():     # parser lines with unrelated text → None
def test_coord_agreement_shifted_box():               # same text, box shifted by half its width → ≈ 1/3
def test_ocr_cer_ignores_whitespace_and_case():       # "T h i s  S E C T I O N" vs "This section" → 0.0
def test_ocr_cer_empty_is_none():                     # pp with no blocks → None
def test_cell_check_exact_with_row():                 # row (P14-8969, 18265) passes; R28 only as substring "R280" fails exact
def test_runner_textlayer_two_pages(tmp_path):        # run_spike main() with --parser textlayer on {FAA: [16, 1]} → parses.jsonl has 2 pages, 2 jpgs, metrics.json; page 1 has ocr=True and coord agreement None
def test_runner_keeps_going_after_parser_error(tmp_path, monkeypatch):  # a fake parser registered via get_parser raising on page 16 only → page 16 PageParse has error set and no blocks, page 1 still parsed, report counts 1 error
```

The runner calls the parser one page at a time so a failure is isolated to its page; the error string is the exception type and message, never a traceback with local paths.

- [ ] **Step 2: Run** `uv run pytest tests/manualqa/test_spike.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `metrics.py`, `run_spike.py`, `report.py`.
- [ ] **Step 4: Run** `uv run pytest tests/manualqa/test_spike.py -v`. Expected: PASS. Then run the real thing: `uv run python -m evals.spike.run_spike --parser textlayer` and open three overlays (FAA p16, operator p51, parts p59) with the Read tool: boxes must sit on the text. `uv run python -m evals.spike.report docs/spike/*/metrics.json` prints a one-row table.
- [ ] **Step 5: Commit** code, `pages.json`, `expectations.json`, and `docs/spike/textlayer/` (check total size with `du -sh docs/spike`, expected under 4 MB):
  `git commit -m "evals/spike: 30-page parser spike runner with overlays and metrics; text-layer reference run"`

### Task 6: Docling adapter

Runs on the laptop. Get the code there with a git bundle (`git bundle create /tmp/v2.bundle v2`, `scp` to the laptop, `git fetch` it into WSL `~/LLM-chatbot`), then `uv sync --extra dev --extra docling` in WSL.

**Files:**
- Create: `manualqa/parsers/common.py`, `manualqa/parsers/docling_parser.py`, `tests/manualqa/test_parsers_common.py`, `tests/manualqa/test_docling_parser.py`

**Interfaces:**
- Consumes: `Parser` protocol, `OcrDecision`, `render_page`/`PageFrame`, schema.
- Produces:
  - `assign_lines(blocks: list[Block], lines: list[Line]) -> list[Line]` in `common.py`: appends each line to the smallest block whose box contains the line's centre; returns the lines no block contains.
  - `DoclingParser` (`name = "docling"`), registered in `get_parser`; `docling_box_to_norm(bbox, page_width_pt: float, page_height_pt: float) -> Box`, a pure function honouring each bbox's own `coord_origin`.

Behaviour: convert one page at a time (`page_range`) so OCR can be chosen per page: pages with `ocr=True` use full-page OCR forced (`force_full_page_ocr=True`), others use the text layer; table structure on, accurate mode. Map Docling item labels to `Kind` (section_header/title → heading, table → table, picture → figure, caption → caption, text/list_item/paragraph → text, anything else → other). Table cells from the table item's cells with their row/col offsets, header flag from column-header cells, and their bbox when present. Lines: Docling's line-level text cells for the page (text-layer or OCR cells), assigned to blocks with `assign_lines`; orphan lines become `"other"` blocks. Check the current Docling API with context7 before writing the adapter; record the Docling version and OCR engine in `metrics.json`.

- [ ] **Step 1: Write the failing tests**

```python
# test_parsers_common.py (runs anywhere)
def test_assign_lines_by_centre():      # line centred inside block A → in A.lines; line outside all → returned
def test_assign_lines_prefers_smallest_block():  # nested blocks: line goes to the inner one

# test_docling_parser.py
def test_docling_box_bottomleft():   # bbox l=61.2, t=712.8, r=306, b=633.6, BOTTOMLEFT on 612x792 → Box(0.1, 0.1, 0.5, 0.2)
def test_docling_box_topleft():      # bbox l=61.2, t=79.2, r=306, b=158.4, TOPLEFT on 612x792 → Box(0.1, 0.1, 0.5, 0.2)

@pytest.mark.parsers
def test_docling_faa16_agrees_with_text_layer():  # parse FAA [16] → validate()==[], coord_agreement vs text layer ≥ 0.7
@pytest.mark.parsers
def test_docling_letter_spaced_page_is_ocrd():    # operator [51] with its needs_ocr decision → pp.ocr True, some block text contains "exhaust"
```

The two box tests use a minimal stand-in object with `l, t, r, b, coord_origin` attributes, so they run in CI without Docling installed.

- [ ] **Step 2: Run** `uv run pytest tests/manualqa/test_parsers_common.py -v` (anywhere) and, in WSL, `MANUALQA_PARSERS=1 uv run pytest tests/manualqa/test_docling_parser.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `assign_lines`, then the adapter.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then `uv run python -m evals.spike.run_spike --parser docling`.
- [ ] **Step 5: Commit** the adapter and tests (on the laptop, then bundle back; or copy the two files back and commit here). The run outputs are committed in Task 8.
  `git commit -m "manualqa: Docling adapter (per-page forced OCR, table cells, line boxes)"`

### Task 7: PaddleOCR-VL adapter

Runs on the laptop in a separate environment: `uv sync --extra dev --extra paddle` (the extras conflict, so this replaces the Docling environment; re-sync to switch back).

**Files:**
- Create: `manualqa/parsers/paddle_parser.py`, `tests/manualqa/test_paddle_parser.py`
- Modify: `manualqa/parsers/common.py`, `tests/manualqa/test_parsers_common.py`

**Interfaces:**
- Consumes: `assign_lines` (Task 6), `norm` (Task 4), `cell_checks` (Task 5).
- Produces:
  - `html_table_cells(html: str) -> list[Cell]`: row/col for every `<td>`/`<th>` honouring `rowspan`/`colspan` (a spanned cell is recorded once, at its top-left position), `header=True` for `<th>` and for cells inside `<thead>`, `box=None`. Use `html.parser` from the standard library.
  - `PaddleParser` (`name = "paddle"`), registered in `get_parser`.

Behaviour: every page is OCR'd from a render (Paddle never reads the text layer); render at `OCR_DPI = 200` with `render_page` and convert pixel boxes with `frame.from_px(..., width_px, height_px)` of that render. PaddleOCR-VL 1.6 gives layout blocks, their text, and table HTML; PP-OCRv5 (det + rec) gives line boxes, assigned with `assign_lines`, orphans kept as `"other"` blocks; table cells come from `html_table_cells` on the table HTML, and cell boxes from the table-cell detection module run on the table crop: a detected cell box is given to the HTML cell whose `norm` text best matches (`fuzz.ratio` ≥ 85) the OCR lines whose centres fall inside it; unmatched cells keep `box=None` (that share is a reported metric, not an error). Check the current PaddleOCR 3.x API with context7 before writing the adapter; record model names and versions in `metrics.json`. `ocr`/`ocr_reason` still record the detector's decision so the overlays and the report stay comparable across parsers.

- [ ] **Step 1: Write the failing tests**

```python
def test_html_table_cells_spans():
    cells = html_table_cells("<table><tr><th colspan=2>A</th><th>B</th></tr>"
                             "<tr><td rowspan=2>x</td><td>y</td><td>z</td></tr>"
                             "<tr><td>w</td><td>v</td></tr></table>")
    assert [(c.row, c.col, c.text, c.header) for c in cells] == [
        (0, 0, "A", True), (0, 2, "B", True),
        (1, 0, "x", False), (1, 1, "y", False), (1, 2, "z", False),
        (2, 1, "w", False), (2, 2, "v", False)]

@pytest.mark.parsers
def test_paddle_faa16_agrees_with_text_layer():  # as for Docling: validate()==[], coord agreement ≥ 0.7
@pytest.mark.parsers
def test_paddle_parts59_finds_part_number_cell():  # cell_checks for the P14-8969 expectation passes
```

- [ ] **Step 2: Run** `uv run pytest tests/manualqa/test_parsers_common.py -v` (anywhere) and, in WSL, `MANUALQA_PARSERS=1 uv run pytest tests/manualqa/test_paddle_parser.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `html_table_cells`, then the adapter.
- [ ] **Step 4: Run** both commands. Expected: PASS. Then `uv run python -m evals.spike.run_spike --parser paddle`.
- [ ] **Step 5: Commit** `git commit -m "manualqa: PaddleOCR-VL adapter (layout, line boxes, table cells)"`

### Task 8: Spike results and decision record

**Files:**
- Create: `docs/spike/docling/*`, `docs/spike/paddle/*` (copied back from the laptop with `tar`), `docs/decisions/001-parser-and-coordinates.md`

- [ ] **Step 1: Bring results back** and check them: `du -sh docs/spike` (expected under 12 MB for three parsers; if more, lower JPEG quality to 70, never drop pages); `grep -rE '192\.168\.|\.lan\b|/home/' docs/spike` returns nothing.
- [ ] **Step 2: Inspect every overlay** of both candidates with the Read tool (60 images). For each page note: boxes on the text (yes / offset / flipped), tables split into cells, letter-spaced pages read as words, figure blocks around the figure, rating plate text read. This is the coordinate check by eye that the spec requires; the metrics do not replace it.
- [ ] **Step 3: Write the decision record** `docs/decisions/001-parser-and-coordinates.md` with these sections: *Question* (parser and coordinate pipeline for the thin slice); *Candidates* (Docling, PaddleOCR-VL 1.6, with versions, models and licences, date checked; MinerU and Marker excluded and why); *Method* (the 30 pages and why, the text-layer reference, the metrics, the eye check); *Results* (the `report.py` table, then a per-page eye-check table: page, Docling, Paddle); *OCR detection* (the thresholds, the flag counts per manual from Task 3, the borderline 0.3–0.8 operator pages and what the overlays show for them); *Decision* (the parser for the thin slice, with the margin that decided it; if the candidates tie, prefer the one with line and cell boxes); *What lost and why*; *Open questions for plan 2*. Link the overlays most worth seeing: FAA 16 and 31, operator 51 and 57, parts 59, for both candidates.
- [ ] **Step 4: Verify** `uv run pytest tests/ -q` and the lint commands from Task 1 pass on this box (parser-marked tests skip here).
- [ ] **Step 5: Commit**

```bash
git add docs/spike docs/decisions/001-parser-and-coordinates.md
git commit -m "decisions: 001 parser and coordinate pipeline (spike results, overlays)"
```

- [ ] **Step 6: Show Alex the commit list** (`git log --oneline origin/v2..v2`) with the decision and three overlays; push only after he approves.
