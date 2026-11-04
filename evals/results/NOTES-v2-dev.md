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

## Run 2 (2026-11-03): `raw/v2-dev-run2.json`, `v2-dev-run2.json`

After the fact-check fix (`1ec3b71`, `a5ecf89`); same 42 items, stack and judge, one repeat. This fix was
made by looking at these same items, so the gain is what tuning on dev gives, not a held-out result.

| | v1 (mean of 3) | Run 1 | Run 2 |
|---|---|---|---|
| Correctness | 0.49 | 0.57 | 0.72 |
| Table correctness | 0.33 | 0.25 | 0.63 |
| Figure correctness | 0.20 | 0.80 | 0.80 |
| Parts manual correctness | 0.03 | 0.25 | 0.83 |
| FAA handbook correctness | 0.68 | 0.57 | 0.63 |
| Citation hit | 0.69 | 0.64 | 0.81 |
| Faithfulness | 0.48 | 1.00 | 0.97 |
| Unanswerables abstained | 0.56 | 1.00 (6/6) | 0.83 (5/6) |
| False abstentions | 6.3 | 10 | 4 |
| Latency p50 | 2.4 s | 8.8 s | 8.7 s |

Six of the ten false abstentions came back (faa-07, op-08, parts-01, parts-02, parts-03; parts-06 in part).

**Still wrong:**

- **False abstentions, 4.** faa-03, faa-04: `SR20` is in the question but not on the data sheet's
  continuation pages, so the context rule does not apply. op-02: the claim adds `MEP-802A`, which the
  question does not mention. faa-05: quote not in cited block. Widening the context rule to the whole
  manual would fix the first two but would also pass an SR22 claim built on an SR20 row, so it is not done.
- **unans-03 regression.** It now answers with a true stock number for an oil, which does not answer the
  question. Run 1 removed it only by accident. The checker tests claims against sources, not whether a
  claim answers the question.
- **parts-06, in part.** The part number claim is removed because p21's table header lacks the FSCM
  column, so values sit one column off. A parse problem, not a checker problem.
- **faa-14.** Still the wrong figure reading (30, reference 16.8); figure claims have no quote check.
- **faa-07.** Graded correct, but the judge calls it unfaithful: the value 6.68 at 59 °F is right, and the
  flattened row shown to the judge loses the column heading. Probably a judge error; not checked by a person.

One judge reply had no JSON (faa-14, the faithfulness call), so its faithfulness is not counted.
