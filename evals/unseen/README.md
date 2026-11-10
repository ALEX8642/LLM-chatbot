# Unseen-manual items

`fist.jsonl`: 104 items on FIST 3-30 (`manuals/`), written by Claude from the PDF's text layer and
pages on 2026-11-10, before either system was run on this manual or its parse was read. 92 answerable
(75 single page, 15 table, 2 multi-page) and 12 unanswerable near misses. Every answerable item's
anchors appear on its gold pages and every unanswerable item's anchors are absent from the whole text
layer (checked when written). Same format as `evals/test.jsonl`; `sections` is empty because there is
no dev/test split within this manual.

Frozen at tag `unseen-items-frozen`, sha256 begins `1c7842343fda9bab`. The plan for running and
analysing them is `docs/prereg-unseen.md`.

## Parse and source text

PaddleOCR-VL parsed all 87 pages (`docs/prereg-unseen.md` describes the run). Ingested with the locked
dependencies, the composed source text the judge reads has sha256
`34d32e5762363872e45b6f12708221a03bf277d634c46e5553f292d5158890e3`: 24 tables, 237 rows. Every anchor of every
answerable item appears verbatim on its gold pages in that text.
