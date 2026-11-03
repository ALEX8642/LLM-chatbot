# 002: Ingestion (hybrid text layer + Paddle)

Date: 2026-11-03. Plan: [`2026-11-02-tier1-02-ingestion.md`](../superpowers/plans/2026-11-02-tier1-02-ingestion.md).
Follows [decision 001](001-parser-and-coordinates.md), which chose PaddleOCR and left eight open questions for this plan.

## Question

How do the raw page parses become what the answer path reads: blocks whose text has line boxes,
tables whose cells have boxes, chunks, page renders and a search index?

## Decision

**Hybrid composition.** On pages where the OCR detector trusts the PDF text layer, the text and
line boxes come from the text layer; Paddle supplies only the layout (block types and regions) and
the table structure. On flagged pages (letter-spaced scan, raster image cover, text drawn as
vector paths, no text) everything comes from Paddle. Every block's text is built from its own lines,
so a quote match always lands on boxes (open question 3 of decision 001). `PageParse.text_source`
records which source a page used (open question 7).

**Table cells are placed by geometry**: each row's y-band and each column's x-band, anchored on
cells whose text is unique on the page, not by matching text alone (repeated values such as `PAOZZ`
or `18265` would otherwise land on the wrong row).

## Result on the spike pages (open question 1)

The same 30 spike pages and checks as decision 001, with the hybrid built from the spike's raw Paddle
parses:

| parser | coord agreement (median IoU) | centre offset (median) | CER letter-spaced (median) | cell checks | cells with boxes |
|---|---|---|---|---|---|
| paddle | 0.79 | 0.0007 | 0.04 | 9/10 | 413/2086 |
| **hybrid** | **1.00** | **0.0000** | **0.02** | **10/10** | **1445/2086** |

All 10 cell checks find the value and box it (Paddle alone missed `15 ± 3` on operator p24 and
left three found values without a box: FAA p28, operator p23, parts p12). The letter-spaced pages are
OCR pages in both rows; their CER halves because block text is rebuilt from the block's OCR lines
instead of taken from the VL model's block text.

## Full run

363 pages of the three manuals, parsed on the laptop's RTX 4090 Laptop GPU: 4.9 h of parsing in
total (median 36 s a page, slowest 261 s), resumable page by page. Ingest after that takes 2 min 14 s
(compose 14 s, tables 1 s, renders 28 s, embeddings + index 87 s).

| | |
|---|---|
| Pages | 363 (text layer 225, OCR 138: image cover 75, letter-spaced 47, no text 14, vector text 2), 0 errors |
| Blocks | 3,497 (text 1,470, other 878, heading 372, caption 335, figure 222, table 220) |
| Chunks | 880 (text 400, table 289, figure 191) |
| Tables | 220, with 3,890 rows; 3,726 rows (96%) have a box |
| Table cells | 22,636 non-empty; 20,760 (92%) have a box |

**Checked by eye** (composed overlays): parts table p59 (every cell boxed, wrapped description
kept with its row); two borderline letter-spaced operator pages, p18 and p82 (open question 6: text
reads cleanly, line boxes are tight); FAA formula page p25 and vector-text page p31; image-cover
pages FAA p49 (chapter opener over a photo) and operator p99 (fold-out form). No misplaced blocks.

## Thresholds and why

| Setting | Value | Why |
|---|---|---|
| OCR detector | letter-spaced ≥ 50% one-char tokens; image cover ≥ 30% of page; vector text ≥ 500 drawings and ≤ 200 chars; no text ≤ 20 chars | From decision 001's spike; unchanged |
| LaTeX clean-up | only `$ … $` with inner spaces | PaddleOCR-VL writes maths that way; dollar amounts like `$5` must survive (open question 2) |
| Table row span | up to 5 text lines per row | Parts group labels wrap over 4 text-layer lines |
| Short cell values | ≤ 4 chars must match exactly | Fuzzy partial matches score `5` against `68505` as 100 |
| Group labels | sparse row (≤ half the columns), ≥ 20 chars, not a `(n)` column label; plus `FIG …` lines inside the table | Header labels were taken for groups; Paddle dropped `FIG. 16 RADIATOR AND HOSES` from p61's table HTML |
| Running headers/footers | top 12%, bottom 15%, ≤ 60 chars | Real parts headers end at y = 0.09, page numbers sit at 0.885 |
| Chunks | ≤ 1,500 chars; tables 25 rows a chunk; captions within 0.05 of the page join their figure/table | Keeps a parts group inside one or two chunks |
| Embedder | `st:Qwen/Qwen3-Embedding-0.6B` (dense) + BM25 sparse, fused by RRF in Qdrant | A working default only; plan 6 chooses the real embedder on the eval set |

## Cons and costs

- **Parse time:** about 5 GPU-hours per full ingestion of these three manuals. Paddle can hang
  with the GPU idle (decision 001, question 5, and an intermittent hang inside the VL model's
  embedding kernel); the full run needed a watchdog that kills and resumes. vLLM serving
  (question 4) is still unmeasured.
- **Detected cell boxes** are still used only to find the table structure; highlights come from
  line boxes. 8% of non-empty cells have no box (mostly OCR'd tables).
- **PyMuPDF (AGPL-3.0)** is kept for rendering and coordinates (decision 001, question 8).

## Notes for plan 3's dev run (answer path)

1. Quote matching must tolerate the OCR text on the 138 OCR pages (residual CER about 0.02 on
   the letter-spaced ones).
2. Table answers should go through `lookup_table` on rows, not through table chunks alone; 289 table
   chunks are there for retrieval.
3. Figure blocks (222) carry only their caption and any text inside them, so figure answers need
   the page image.
