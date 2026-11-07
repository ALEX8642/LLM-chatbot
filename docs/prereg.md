# Pre-registration: v2 against v1 on the held-out test set

**Registered at tag `prereg`, before any system ran on `evals/test.jsonl`.** Alexander agreed on 2026-11-06. Everything
after the tag that changes a result is reported as a deviation.

## Question

Does v2 give more answers that are correct and supported by what they cite than v1, on questions not used to build it?

## Primary

- **Items:** `evals/test.jsonl`, 169 items (133 answerable, 36 unanswerable), frozen at tag `eval-test-frozen`, sha256
  begins `fa03c28ef5267c05`. It covers all three manuals (FAA 57, parts 61, operator 51), split by section so that no
  gold page lies in a dev section.
- **Endpoint (binary, per item):** the answer is correct and the judge finds its key facts in the cited source: a cited
  page for v1, the cited block for v2. An unanswerable item passes when the system abstains.
- **Contrast:** v2 against v1.
- **Judge:** `phi4:14b`, grader prompt version 2 (decision 003). It is from a different family than the generators.
- **Repeats:** 3 per system. An item's score is the majority of its graded repeats. A tie fails.
- **Test:** exact McNemar, two-sided, 5%, with the discordant counts printed.
- **Interval:** paired bootstrap of the difference, 95%, 10,000 draws, seed 20261106, resampling clusters. A cluster
  joins items that share a gold page, and all part-number questions, which behave like one template.
- **The claim "v2 is better"** needs both McNemar p < 0.05 and an interval above zero.
- **Ungraded items** (judge errors in all repeats) are left out of the pair, and counted in the report.

Code: `evals/analysis.py`, run on dev below.

## Secondary family, Holm corrected

1. v2 against v1 at temperature 0, phi4.
2. v2 against v1, judged by `mistral-small3.2:24b` on the first repeat.

## Reported, exploratory: intervals only, no significance claims

- Per manual. Parts is 35% of test against 16% of dev, and v2's dev gain is largest there, so the headline leans towards
  v2 (M2 review).
- Part-number questions (35) as a sub-score.
- Abstention, under both judges and as recorded (`recorded_abstained`).
- v2's source support at page level (`supported_in_pages`), because v1 cites whole pages and v2 blocks.
- The bootstrap with page clusters and with section clusters. Section clusters number too few to trust, so they are a
  check only.
- Table and single-page categories. Figure (5) and multi-page (5) are given as counts only, since one item moves them
  20 points.
- Time per answer, p50 and p95, with hardware; spread across repeats; removed claims per answer.
- The meaning check's removals, read by hand. On dev it caught no real error after its page look was added, so its
  value is an open question.

## Expectation

Dev: v2 0.83 (phi4) / 0.87 (mistral); v1 0.51 / 0.54; v1 at temperature 0 0.51 / 0.55. Dev steered v2's checks and
evidence and chose its reranker, while v1 was not tuned on it, so **v2's gain on test should be smaller than on dev.**

Analysis on dev, v2 against v1, phi4, one v2 repeat against three of v1:

| Clusters | Difference | 95% interval | v2 only / v1 only | McNemar p | Effective n | Smallest detectable |
|---|---|---|---|---|---|---|
| Page + template (primary) | +0.32 | 0.19 to 0.44 | 64 / 9 | 2e-11 | 76 | 0.21 |
| Page | +0.32 | 0.22 to 0.43 | 64 / 9 | 2e-11 | 113 | 0.17 |
| Section (13, a check only) | +0.32 | 0.24 to 0.41 | 64 / 9 | 2e-11 | 179 | 0.14 |

**Power.** Clustering leaves dev about 76 effective items, and test should be similar: about 21 points detectable at 80%
power, where the spec expected about 10. A difference under about 20 points may well be missed. McNemar treats items as
independent, so the interval is the more cautious of the two, which is why both are required.

## Fixed before the run

- **v2:** this commit, as in `docs/prereg-notes.md` and decisions 002, 003 and 004. Abstains when no claim survives; no
  threshold to tune.
- **v1 and v1 at temperature 0:** unchanged code at tag `v1`.
- **Source text for grading:** the ingest's own `composed.jsonl`, sha256 begins `21ce1fd29589b646`. The dev grades above
  used an earlier copy, differing in 75 of 3,497 blocks, mostly line-break characters, so they may move slightly.
- **Environment:** the laptop's 16 GB GPU; generator through the existing gateway. Model names and revisions are recorded
  in each raw file.

## Running it

1. Tag `prereg`. Run v1, v1 at temperature 0 and v2, 3 repeats each, with the code at the tag.
2. A run ended by a failure (crash, timeout, restart) is rerun whole and the failure reported, whatever it showed. A stall
   that does not end the run is reported and kept.
3. Judge all repeats with phi4, the first repeat with mistral.
4. Commit raw outputs and judge outputs, then run `evals/analysis.py`. Nothing is run on test before the tag, and nothing
   is tuned on it after.

A defect found after the run gets the pre-registered result reported first, then the fixed result beside it, labelled.

## Checks after the run

**Blind grading by Alexander:** about 100 answers across the systems, identity hidden and order random, including correct
v1 answers the judge rejected on source support (31 of 210 on dev against 5 of 96 for v2, reviewer's counts), and the
abstention items the judges disagree on. The session confirms each save and shows a stored count. He is not a subject
expert, which the report states.

**Judge validity rule:** agreement with his grades is reported per system. If the judge wrongly fails one system's answers
more often than the other's by over 10 points on this sample, the headline is reported with that warning and the blind
contrast beside it.

**Misses:** every v2 failure gets a label (not retrieved, parse error, misread, wrong table row, bad citation, wrong
abstention), first by rule from recorded facts, then by reading. The README shows misses alongside the headline.

## Known limits

- Test and dev are different sections of the same three manuals, so this is not a held-out manual.
- Both the labelled claims and gold answers were written by Claude, the gold ones partly checked by Alexander, who is not a
  subject expert (at least 4 of 60 needed context from another page).
- Leak search covered numbers and question similarity, so non-numeric paraphrase pairs may remain.
- Not run in tier 1, despite the spec: a risk-coverage curve (v2 abstains by rule, with no continuous score), whole-manual
  context rows, closed-book rows, counterfactual edits and a held-out manual.
- The stalls are unexplained, so a test run could hit one.
