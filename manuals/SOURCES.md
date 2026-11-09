# Bundled manuals

These public documents are bundled so anyone can clone the repo and run the app and the evaluation.
Each PDF is stored unmodified, as downloaded. Page numbers in `evals/qa.jsonl` are 1-based PDF page
indexes, not the printed page labels.

| File | Document | Pages | Source | Licence / status | SHA-256 |
|---|---|---|---|---|---|
| `FAA_Weight_and_Balance_Handbook.pdf` | FAA-H-8083-1B, *Aircraft Weight and Balance Handbook* (FAA, 2016) | 114 | [faa.gov](https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/FAA-H-8083-1.pdf), downloaded 2026-11-01 | Work of the U.S. Government, not subject to copyright in the U.S. (17 U.S.C. § 105). The handbook credits some photographs and sample diagrams to third parties (see its Acknowledgments page); they are redistributed only as part of the unmodified FAA publication. | `84015042cdf8f4ab46cfec8a55fd47e9c96cbe95b423f0f6cab14e4425079a10` |
| `Army_5kW_Generator_Operator_Manual.pdf` | TM 9-6115-641-10 / TO 35C2-3-456-11, *Operator's Manual, Generator Set, Skid Mounted, Tactical Quiet, 5 kW, 60 and 400 Hz (MEP-802A, MEP-812A)*, 30 Dec 1992 with changes 1 and 2 | 101 | [radionerds.com mirror](https://www.radionerds.com/images/6/64/TM-9-6115-641-10.pdf), downloaded 2026-11-01 | Distribution Statement A: approved for public release; distribution is unlimited. Work of the U.S. Government. | `12a98cad5ced1eb099faf24c2b481618f408cb6e9589f22c47d48303a6cf46f0` |
| `Army_5kW_Generator_Parts_Manual.pdf` | TM 9-6115-641-24P / TO 35C2-3-456-14, *Unit, Direct Support and General Support Maintenance Repair Parts and Special Tools List* for the same generator sets | 148 | [radionerds.com mirror](https://www.radionerds.com/images/7/79/TM-9-6115-641-24P.pdf), downloaded 2026-11-01 | Distribution Statement A: approved for public release; distribution is unlimited. Work of the U.S. Government. | `53dc2418976fda2f2524a6ce9469f8622df6550ed686a2e8000d0f23a0799ba6` |

## Why these three

They cover different document styles, which stress different parts of the pipeline:

- **FAA handbook:** born-digital, two-column prose with worked examples, tables, and charts
  (loading graphs, CG envelopes). Some pages are images with no text layer (for example, the
  equipment-list excerpt on page 31).
- **Operator manual:** a 1990s scan with an OCR text layer. About half of its pages have a
  letter-spaced text layer ("T h i s s e c t i o n …"), which defeats keyword search. It contains
  procedures, preventive-maintenance tables, a troubleshooting table and data plates that exist only
  as images.
- **Parts manual:** exploded-view diagrams paired with parts-list tables. Plain text extraction
  flattens each table to one value per line.

The two Army manuals describe the same equipment, which allows cross-manual questions (for example,
"which part does this troubleshooting step refer to, and what is its part number").

## Parses

`paddle-parses.jsonl.gz` is PaddleOCR-VL's output for every page of the three manuals (the
`spike-out/paddle/parses.jsonl` the evaluated index was built from, gzipped). Parsing takes hours on
a GPU; ingesting this file takes minutes, so a fresh clone or the Docker image starts from it.
With PyMuPDF 1.26.4 from `uv.lock`, it reproduces the tested `composed.jsonl` byte for byte.
