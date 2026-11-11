# Unseen manual

A manual neither system was built, tuned or tested on, for the out-of-sample check in
[`docs/prereg-unseen.md`](../../../docs/prereg-unseen.md). Stored unmodified, as downloaded.

| File | Document | Pages | Source | Licence / status | SHA-256 |
|---|---|---|---|---|---|
| `Reclamation_FIST_3-30_Transformer_Maintenance.pdf` | FIST Volume 3-30, *Transformer Maintenance* (Bureau of Reclamation, October 2000) | 87 | [usbr.gov](https://www.usbr.gov/power/data/fist/fist3_30/fist3_30.pdf), downloaded 2026-11-09 | Work of the U.S. Government (Department of the Interior), not subject to copyright in the U.S. (17 U.S.C. § 105). | `8f14532af9a50398f0e929a055924f2fe176e3b2f8940f82cc4b6ce0cd8e61a5` |

It differs from the three development manuals in publisher, subject (power transformer maintenance
and oil diagnostics) and layout: dense limit tables, worked examples, and a garbled text layer on its
cover pages. Page numbers in `evals/unseen/fist.jsonl` are 1-based PDF pages; the printed page
number is the PDF page minus 6.
