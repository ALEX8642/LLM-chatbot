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

## Dev set of 172, independent judge (2026-11-04)

> **Superseded by the section below**, which uses the corrected grader. Kept for the record.

The first numbers from the independent judges and the key-fact grader, on the full dev set. `Correct` needs
every key fact. `Primary` also needs the judge to find them in the cited source. These are stricter than the
tables above, so do not compare across them. Dev only: the test set has not been run.
Files: `raw/{v1,v1-t0,v2}-dev172.json`, `{v1,v1-t0,v2}-dev172-{phi4,mistral}.json`.

| phi4:14b | v1 (3 repeats) | v1 at temp 0 (3 repeats) | v2 (1 repeat) |
|---|---|---|---|
| **Primary, all 172** | 0.51 | 0.53 | **0.68** |
| Correct, all 172 | 0.57 | 0.59 | 0.71 |
| Primary, original 42 | 0.40 | 0.40 | 0.76 |
| **Primary, 130 new items** | 0.54 | 0.57 | **0.65** |
| Primary, table (56) | 0.33 | 0.39 | 0.55 |
| Primary, single page (62) | 0.58 | 0.61 | 0.79 |
| Primary, figure (10) | 0.22 | 0.22 | 0.67 |
| Primary, multi-page (11) | 0.27 | 0.36 | 0.45 |
| Unanswerable correct (33) | 0.82 | 0.74 | 0.76 |

The second judge, `mistral-small3.2:24b`, on one repeat: primary 0.53, 0.55 and 0.68. The judges agree
on correctness on 98-99% of items, and on primary on 92% (v1) and 96% (v2).

**How to read it:**

- **The 130 new items are the fairer estimate.** The checker was fixed by looking at the original 42, so 0.76
  there is inflated. v1 also does unusually badly on those 42, so the gap there (0.36) overstates the gain:
  on new items it is 0.11 against v1 and 0.09 against v1 at temperature 0. No confidence intervals yet; plan 7
  has the analysis code. They are also not held out: they shaped no fix so far, but they are dev.
- **v2 is no better than v1 at unanswerables** (0.76 against 0.82), and v1 at temperature 0 is close to v2.
  v2 answers 8 of 33. Some are true but off-question (the service ceiling definition, the calibration
  interval), the relevance gap again. One, faa-ch1-10, says in words that the text does not state it, but
  the system recorded a claim, so it is graded as an answer.
- **False abstentions remain: 20 of 139 answerable items** (14%). The largest removal reason is "quote not in
  cited block" (18), then context absent from the cited page (`SR20`, 6; `8MR3005CA`, 4).
- **Temperature 0 helps v1 slightly and is a fairer baseline.** 164 of 172 answers repeat exactly.

**Limits:** v2 has one repeat, v1 three. Claude wrote the items, and no person has checked them or the judge yet.
v2 latency is p50 8.4 s against v1's 2.8 s; its p95 of 61 s has not been explained, and may be other load on
the laptop or the gateway. v2's length bias (0.07 per 100 characters, interval above 0) probably reflects short
abstention text rather than judge preference, but that is unverified, and it should be retested with abstentions
excluded.

The judge errors first seen here came from phi4 adding text after its JSON, a parser bug fixed in `e240ed2`.
`228217b` raised the token limit on a wrong diagnosis; it changed no error counts, and was kept because it
matches judge selection. About 1 item per run still fails, because the judge split a key fact in two.

## Dev set of 172, corrected grader (2026-11-05)

After the M2 review: exact matching no longer fails bold or percent signs or passes values inside longer codes;
abstention is judged for both systems (prompt version 2); page citations are deduplicated. Same runs as above.
Primary needs the answer correct and the judge finding its key facts in the cited source. Dev only.

| Primary | v1 | v1 at temp 0 | v2 |
|---|---|---|---|
| All 172, phi4 | 0.50 | 0.51 | **0.71** |
| All 172, mistral | 0.54 | 0.55 | **0.70** |
| 130 new items, phi4 | 0.52 | 0.54 | **0.69** |
| 130 new items, mistral | 0.57 | 0.58 | **0.69** |
| Original 42, phi4 | 0.42 | 0.43 | 0.79 |
| Parts manual (28), phi4 | 0.27 | 0.25 | 0.75 |
| Operator manual, phi4 | 0.48 | 0.52 | 0.65 |
| FAA handbook, phi4 | 0.59 | 0.60 | 0.76 |
| Table (56), phi4 | 0.32 | 0.34 | 0.55 |
| Single page (62), phi4 | 0.57 | 0.59 | 0.79 |

v1 has 3 repeats under phi4 and 1 under mistral; v2 has 1 under each. v2's primary at page-level citation is 0.73 (phi4)
and 0.71 (mistral). v2 wrongly declines 20 of 138 answerable items, and v1 16 (the 1 item with a judge error is left out).

**Unanswerables are not settled.** Of 33:

| | v1 | v1 at temp 0 | v2 |
|---|---|---|---|
| phi4 | 0.81 | 0.82 | 0.94 |
| mistral | 0.76 | 0.73 | 0.85 |
| Recorded by v2 | | | 0.76 |

The judges count some of v2's true but off-topic answers as declines. phi4 still does so after the wording was
tightened (6 disagreements with v2's own record, mistral 3). Some of these say in words that the text does not state the
answer, so the record is not simply right either. By phi4's figure v2 beats v1 here; by v2's own record it does not.
These cases go into the blind session. The prompt was not reworded further. If v2's 6 disagreements count as wrong, its
overall phi4 primary falls by about 0.035.

**Other cautions.** phi4 rejects correct answers on source support at very different rates: 14 of 71 for v1, 5 of 96 for v2;
mistral 3 of 70 and 2 of 94. So phi4 may be biased against v1 on this, which is why mistral shows a smaller gap; the blind
session should test it. The checker was fixed on the original 42, so the 130 new items are the fairer figure, and the gap
there is 0.11-0.17 by judge and baseline. There are no confidence intervals yet. v2's length bias (0.06 per 100 characters,
interval above 0) is still unexplained. Item wording is Claude's, checked by a sample of 60 and a review of 30.

## Checks and evidence rebuilt (2026-11-05): `raw/v2-dev172.json`, `v2-dev172-{phi4,mistral}.json`

172 dev items, one repeat, judges phi4 and mistral. All tuning is on dev; the test set is unrun. The rows are
cumulative. v1 on the same items is 0.50-0.54.

| Stage | Primary (phi4 / mistral) | Answerable declined | Unanswerable answered | Claims kept / removed | p95 s |
|---|---|---|---|---|---|
| Before | 0.71 / 0.70 | 20 | 8 | 282 / 46 | 61 |
| Table grid rebuild (`b051ae6`) | not judged | 19 | 9 | 274 / 48 | 15 |
| Facts against the source; captions bring tables; quotes relocate; headings carried (`e1875a8`) | 0.77 / 0.79 | 10 | 6 | 298 / 27 | 17 |
| Every table row stored (`81dc92e`) | 0.79 / 0.80 | 7 | 7 | 312 / 15 | 17 |
| Meaning check, block only (`e5563f9`) | 0.78 / 0.78 | 9 | 7 | 302 / 25 | 18 |
| Meaning check, block then page (`3d2b431`) | 0.79 / 0.80 | 7 | 7 | 309 / 18 | 18 |
| Qwen3-Reranker-4B at half precision (decision 004) | 0.84 / 0.87 | 3 | 3 | 305 / 13 | 42 |

A run takes one temperature-0 sample, so a change of one or two items is not evidence, and later rows mix check
changes with whatever the changed evidence did to the model's output.

**What raised the score.** Label-and-value tables never reached the model: the table store kept only rows with
two or more numeric cells, and a table's caption could rank without its rows. The model read those values from the
page image, cited the caption, and the quote failed. Most of the gain is this, not stricter checking.

**Replay check on the checks themselves.** Re-running the 322 recorded claims of the grid run through the new
fact checks, with no model calls: none wrongly removed, 12 restored, 8 fewer declines. (Commit `e1875a8`'s message
says 13; that count predates a last tightening.)

**Table audit.** Text-layer cells whose box does not hold their text: 276 originally, 59 of 20,668 now. Of 947
printed parts rows, none has codes missing from its item's row, though that scan was also loosened while tightening
it. Boxes on OCR pages are unchanged in kind: 26% of cells have none.

**Meaning check.** Choice: the generator, asked yes or no (0.27 s a claim), over two NLI models, on 109 labelled
claims (`evals/claims/`, 70 real and read by Claude, 39 false ones written by Claude to keep the facts and change the
meaning).

| Checker | False claims caught | True claims flagged |
|---|---|---|
| Generator, block then page (in use) | 38 of 39 | not rerun in two stages on this set; block alone 1 of 70 |
| Generator, block only | 39 of 39 | 1 of 70 |
| DeBERTa-v3-base (MoritzLaurer) | 23 of 39 | 1 of 70 |
| nli-deberta-v3-small | 12 of 39 | 1 of 70 |

The false claims are constructed and were written by the same author as the labels, so these rates show what the
check can see, not how often the generator makes such errors. On real dev claims it removes 3 of 312: all three look
true or merely garbled, so **on dev it catches no real error and costs no score.** The block-only version did catch
one real overclaim ("exhaust smoke is caused by improper fuel" when the manual says to check for it), which the page
look lets through along with the true claims it was added to save. It stays as a guard against claims saying the
opposite, and its value is unproven on real output. Figure claims are not checked.

**Remaining false declines (7):** faa-03, faa-04 and faa-ch2-07 name the SR20 and cite p26, which describes the data
sheet without naming it; faa-ch9-08 and faa-14 read values from figures; op-02 names a model not in the cited row;
parts-g01-01 misses retrieval. Unanswerable answers rose by one with the wider evidence, and that number remains
unsettled between the judges (0.85 / 0.91).

**Unexplained.** One attempt at the last run slowed from 10 s to minutes an item from about item 90 with the GPU
pegged at 40 W and its memory full; judging then began beside it. A rerun of the same code was normal, p95 18 s. The
cause is not known. p95 fell from 61 s to about 18 s over these runs, also unexplained.

**Reranker.** Both judges agree on 10 items improving and 3 getting worse (faa-ch3-05, faa-12, unans-05). Multi-page
rose from 0.45 / 0.55 to 0.64 / 0.73 and table from 0.73 / 0.75 to 0.80 / 0.86, on 11 and 56 items. p50 rose from 10 s
to 13 s; p95 from 18 s to 42 s, which is not yet explained and matters for use. Dev has now tuned this system
repeatedly, so expect the test score to be lower.
