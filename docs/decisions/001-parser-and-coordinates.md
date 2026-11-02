# 001: Parser and coordinate pipeline for the thin slice

Date: 2026-11-02. Plan: `docs/superpowers/plans/2026-11-02-tier1-01-coordinate-spike.md`.

## Question

Which parser does the thin slice use, and does one coordinate system hold from parser output to
the rendered page, including the scanned operator manual?

## Candidates

| Parser | Version (models) | Licence (checked 2026-11-02) | Notes |
|---|---|---|---|
| Docling | docling 2.130.0, docling-core 2.96.0; layout + TableFormer (accurate); RapidOCR 3.9.2 (torch backend) on flagged pages | MIT (Docling), Apache-2.0 (RapidOCR) | Text layer on trusted pages, full-page OCR on flagged pages |
| PaddleOCR | paddleocr 3.7.0, paddlepaddle-gpu 3.3.1 (CUDA 12.9); PaddleOCR-VL 1.6 (layout, text, tables as HTML), PP-OCRv5 (line boxes), table-cell detection | Apache-2.0 | Every page OCR'd from a 200 dpi render |
| PDF text layer (reference, not a candidate) | PyMuPDF 1.26.4 | AGPL-3.0 / commercial (already a v1 dependency) | Ground truth for line positions on trusted pages |

Not tried here: MinerU (licence to check), Marker (restrictive model licence).

## Method

- **Pages:** 30, 10 per manual, chosen to cover every page type: two-column prose, specification
  and parts tables, charts, vector-drawn text with no text layer (FAA p31), photos, exploded views,
  the rating plates (operator p57) and four letter-spaced scan pages (operator p51, 52, 70, 72). List:
  `evals/spike/pages.json`.
- **One coordinate system:** every box is page-normalised [0,1], top-left origin of the page as
  rendered. `manualqa/geometry.py` maps PyMuPDF extraction coordinates, raw PDF user space and pixels
  of any render. Tests draw rectangles on synthetic pages (4 rotations, with and without a crop box) and
  compare with rendered pixels. PyMuPDF's `page.transformation_matrix` ignores the crop-box offset on
  rotated pages; MuPDF's own page transform is used instead. Docling reports document items
  bottom-left and cells top-left, so each box is converted by its own origin.
- **OCR detection** (`manualqa/ocr_detect.py`, below) decides per page; the same decision is shown on
  every overlay.
- **Metrics** (`evals/spike/`): line agreement with the text layer on trusted pages (median IoU, and
  median centre offset in page units, because glyph-tight boxes score IoU ≈ 0.65 against PyMuPDF's
  line boxes, which include ascent and descent, even when correctly placed); character error rate
  against the text layer on letter-spaced pages (whitespace ignored, so reading order counts); ten
  table-cell checks taken from dev reference answers (`evals/spike/expectations.json`), each requiring
  the value in one cell and, for parts rows, the CAGE code in the same row; time per page on the
  laptop RTX 4090.
- **Eye check:** every overlay of both candidates was inspected side by side (all 30 pages).

## Results

| parser | pages | errors | validate problems | coord agreement (median IoU) | centre offset (median) | CER letter-spaced (median) | cell checks | cells with boxes | s/page |
|---|---|---|---|---|---|---|---|---|---|
| textlayer | 30 | 0 | 0 | 1.00 | 0.0000 | 0.00 | 0/10 | n/a | 0.02 |
| docling | 30 | 0 | 0 | 0.67 | 0.0016 | 0.12 | 4/10 | 773/773 | 1.41 |
| paddle | 30 | 0 | 0 | 0.73 | 0.0011 | 0.04 | 9/10 | 863/2086 | 41.05 |

Cell checks per item:

| Check | Docling | Paddle |
|---|---|---|
| Parts p12 `88-20243` with CAGE 30554 | no table found | pass |
| Parts p20 `105-269` with 68505 | no table found | pass |
| Parts p20 `105-311` with 68505 | no table found | pass |
| Parts p21 `112-95` with ROTOR | no table found | pass |
| Parts p59 `P14-8969` with 18265 | pass | pass |
| Parts p61 `R28` with 78225 | pass | pass |
| Operator p23 `.55 gal` | no table found | pass |
| Operator p24 `15 ± 3` | pass | fail: written as LaTeX `15 $ \pm $ 3` |
| FAA p28 `3050` | page read as one figure | pass |
| FAA p36 `6.68` | pass | pass |

CER on letter-spaced pages, Docling / Paddle: p51 0.08 / 0.03, p52 0.09 / 0.06, p70 0.25 / 0.04,
p72 0.15 / 0.00.

Eye check (both candidates unless stated):

| Pages | Finding |
|---|---|
| All 30 | Line boxes sit on their text; no offset, flip or scale error on any page, including the letter-spaced scans and the vector-drawn FAA p31. |
| FAA 16, 19, 36, 37, 50, 67 | Same layout from both: columns, headings, captions, figures and tables separated correctly. |
| FAA 28, 29 (type certificate excerpts) | Docling reads p28 as one figure and splits p29 into many small blocks; Paddle reads both as tables. |
| FAA 53 | Chart and loading table both found; chart labels read as lines. |
| Operator 22, 24 | Both find the specification table; Paddle's cell boxes on p24 are few and coarse. |
| Operator 23 | Docling finds no table, only text blocks; Paddle finds the table. |
| Operator 51, 52, 70, 72 | Both read the letter-spaced text; Paddle more accurately (CER above). Paddle merges the p72 troubleshooting steps into one large block; lines are still correct. |
| Operator 57 (rating plates) | Both OCR every field of both plates inside figure blocks. |
| Parts 11, 19, 58, 60 (exploded views) | Both find the figure and read the callout numbers. |
| Parts 12, 20, 21 | Docling finds no table on these pages (text-layer lines only). Paddle finds every table; some detected cell boxes spill outside the table edge or miss narrow columns. |
| Parts 59, 61, 130 | Both find the tables. Paddle's detected cell boxes are partly misaligned at the left and right edges. |

## OCR detection

`needs_ocr` flags a page, in this order, for a letter-spaced text layer (≥ 50% one-character
tokens), raster images covering ≥ 30% of the page, text drawn as vector paths (≥ 500 drawings with
≤ 200 text characters), or no text (≤ 20 characters). Flags on the whole manuals:

| Manual | Pages | letter_spaced | image_cover | vector_text | no_text | text layer trusted |
|---|---|---|---|---|---|---|
| Operator | 101 | 46 | 17 | 0 | 0 | 38 |
| Parts | 148 | 1 | 35 | 0 | 1 | 111 |
| FAA | 114 | 0 | 23 | 2 | 13 | 76 |

17 operator pages have a letter-spaced ratio between 0.3 and 0.8 (for example p32, 69, 82 and 86 at
0.62–0.79, which are flagged). None of them is in the spike set, so their handling has not been checked
by eye. The 13 FAA `no_text` pages are near-blank (chapter dividers, blank versos). OCR on them
costs little.

## Decision

**PaddleOCR (PaddleOCR-VL 1.6 + PP-OCRv5 + table-cell detection) for the thin slice.** It wins on the two
things v1 failed at: tables (9/10 cell checks against 4/10; Docling missed three whole parts-list
pages, and the parts manual was v1's worst manual at 0.03 correctness) and the letter-spaced scan
(median CER 0.04 against 0.12). Its line boxes are at least as well placed (median centre offset 0.0011
of the page against 0.0016).

Costs accepted:

- **Speed:** about 41 s a page on the laptop, about 4 hours for the 363 pages, once per ingestion.
  Docling takes 1.4 s a page.
- **Cell boxes:** only 41% of Paddle's table cells get a detected cell box, and some detected boxes
  are misaligned. Table highlights will therefore be drawn from the OCR line boxes inside a cell. Those
  are accurate on every page; the detected cell boxes are not.

## What lost and why

- **Docling:** fast, permissive, and every cell it finds has a box. It lost because its layout model
  found no table on parts pages 12, 20 and 21, operator p23 and FAA p28. Its OCR on the letter-spaced
  pages was also three times less accurate. Two setup problems were fixed along the way: RapidOCR 3.10.0 lacks an
  attribute Docling 2.130 imports, so OCR silently found no engine (pinned below 3.10), and OCR
  auto-selection was replaced by a named engine.
- **The text layer alone:** exact on born-digital pages and on the parts tables (one line box per
  cell). But it is unusable on 63 of the operator manual's 101 pages and has no table structure.

## Open questions for plan 2 (ingestion)

1. **Hybrid:** use the text layer on trusted pages (exact boxes, 0.02 s a page) and Paddle only for
   flagged pages and table structure? This would cut ingestion time and give exact cell boxes on the
   parts tables. Measure it against Paddle alone on the same checks.
2. **Paddle text clean-up:** Paddle writes some symbols as LaTeX (`$ \pm $`). Normalise them to
   Unicode before quote matching.
3. **Cell highlights:** derive cell boxes from the OCR lines in each cell rather than the cell
   detector.
4. **Speed:** PaddleOCR-VL can run behind a vLLM server. Measure that only if ingestion time becomes
   a problem.
5. **Known Paddle bug:** `PaddleOCRVL` must be created after the other Paddle models; creating one
   after it makes its `predict()` hang with the GPU idle (paddleocr 3.7.0, paddlepaddle-gpu 3.3.1).
6. Check two or three of the borderline letter-spaced operator pages by eye.
7. **Licence decision for Alexander:** `manualqa` renders pages and maps coordinates with PyMuPDF,
   which is AGPL-3.0 (v1 already depended on it). The design asks for a decision when a component is
   restrictive. The permissive alternative is pypdfium2 (Apache-2.0 / BSD-3-Clause); `geometry.py` is
   the only module that would change, and its pixel tests would show whether the swap holds.

## Reproduce

```bash
uv sync --extra dev --extra paddle      # or --extra docling (the two extras conflict)
uv run python -m evals.spike.run_spike --parser paddle
uv run python -m evals.spike.report docs/spike/*/metrics.json
```

Overlays worth seeing (Docling | Paddle): FAA p16
([docling](../spike/docling/FAA_Weight_and_Balance_Handbook-p016.jpg) |
[paddle](../spike/paddle/FAA_Weight_and_Balance_Handbook-p016.jpg)), FAA p31
([docling](../spike/docling/FAA_Weight_and_Balance_Handbook-p031.jpg) |
[paddle](../spike/paddle/FAA_Weight_and_Balance_Handbook-p031.jpg)), operator p51
([docling](../spike/docling/Army_5kW_Generator_Operator_Manual-p051.jpg) |
[paddle](../spike/paddle/Army_5kW_Generator_Operator_Manual-p051.jpg)), operator p57
([docling](../spike/docling/Army_5kW_Generator_Operator_Manual-p057.jpg) |
[paddle](../spike/paddle/Army_5kW_Generator_Operator_Manual-p057.jpg)), parts p20
([docling](../spike/docling/Army_5kW_Generator_Parts_Manual-p020.jpg) |
[paddle](../spike/paddle/Army_5kW_Generator_Parts_Manual-p020.jpg)).
