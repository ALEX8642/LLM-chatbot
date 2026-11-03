# v2 on the 42 dev items (exploratory)

Thin slice from plan 3: hybrid ingest, default embedder and reranker, Qwen3.8 as generator, one
repeat. **Judge: Qwen3.8, the history judge, same as v1's numbers in `NOTES.md`.** It is a generator
here too, so none of this is the headline comparison; plan 5 chooses the independent judge.

## Run 1 (2026-11-03): `raw/v2-dev.json`, `v2-dev.json`

| | v1 (mean of 3) | v2 run 1 |
|---|---|---|
| Correctness | 0.49 | 0.57 |
| Recall@5 | 0.89 | 0.94 |
| Faithfulness | 0.48 | 1.00 |
| Unanswerables abstained | 0.56 | 1.00 (6/6) |
| False abstentions | 6.3 | 10 |
| Table correctness | 0.33 | 0.25 |
| Figure correctness | 0.20 | 0.80 |
| Parts manual correctness | 0.03 | 0.25 |
| Latency p50 | 2.4 s | 8.8 s |

One item (faithfulness call) got a judge reply without JSON; it is counted as a judge error.

**Main finding: the deterministic fact check is too strict.** All 10 false abstentions had the right
evidence, and usually the right page ranked first; the checker removed every claim:

- Context restated from the question, not in the quote: `SR20` (faa-03, faa-04), `MEP-802A` (op-02),
  `59` °F (faa-07), item numbers (parts-01, parts-03, parts-06).
- Number words: the page says "fifteen seconds", the claim says 15 (op-08).
- Quotes with an ellipsis, or rebuilt from table cells: "quote not in cited block" (parts-02, faa-05).

The same check also removed real errors, which any fix must keep catching: a 172S useful load borrowed
from an unrelated worked example (unans-02) and an oil from the supplies list (unans-03).

Other misses: faa-14 read the wrong value from a figure (30, reference 16.8); figure claims have no
quote check, so nothing caught it. Nine "partial" grades are omissions against long reference answers
(faa-06, faa-08, faa-12, op-03, op-09 to op-12, parts-04).
