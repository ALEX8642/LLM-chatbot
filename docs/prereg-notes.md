# Inputs for the pre-registration (plan 7)

Requirements from the M2 review of the frozen test set, to carry into the pre-registered analysis.

**Report, beyond the primary endpoint:**

- Per-manual results. Parts is 35% of test against 16% of dev, and v2's dev gain is largest there, so the
  headline leans towards v2. Reweighting dev by manual gives a 24.7-point gap instead of 17 (reviewer's figure).
- A sub-score for the "part number" questions, which behave like a template (35 in test, reviewer's count).
- Abstention under both judges. It decides many v1 items, and phi4 is the weaker judge on it.
- Sensitivities: recorded abstention instead of judged (`recorded_abstained`); v2 source support at page level
  (`supported_in_pages`), because v1's citations are whole retrieved pages and v2's are blocks.

**Do not report as categories:** figure (5) and multi-page (5). One item moves a score 20 points. Counts only.

**Include in the blind grading session:** correct v1 answers the judge rejected on source support (31 of 210 on dev,
against 5 of 96 for v2, reviewer's counts; those read looked like judge misses), since this may bias against v1.

**Known about the split:** no stratification or dev cap was implemented; sections forced by the original 42 items
set dev's size. Leak search covered numbers and question similarity, so non-numeric paraphrase pairs may remain.
Exact matching does not understand negation ("208 volts, not 120 volts" passes "120 volts"), so exact answers were
removed where a nearby value could appear. Figure questions whose value is in the text layer do not test vision.

**From regrading dev (2026-11-05):** phi4 is lax on abstention and strict on source support, and these lean opposite ways
between the systems. Decide before the test run whether abstention should come from the second judge, and require the blind
session to cover both (the 6 v2 disagreements with its record, and correct v1 answers rejected on source support).

## The system to freeze (2026-11-06)

Tuned on dev only; the test set has not been run by any system.

- **v2:** the `v2` branch at this commit. Text layer plus PaddleOCR-VL ingest; `Qwen3-Embedding-0.6B` + BM25; top 50
  reranked by `Qwen3-Reranker-4B` at half precision to 8 chunks; Qwen3.8 at temperature 0; quote match, fact checks and
  the meaning check. Decisions 002 and 004.
- **Comparators:** v1 and v1 at temperature 0, unchanged.
- **Judges:** phi4 primary, mistral second, grader prompt version 2 (decision 003).
- **Hardware:** 16 GB GPU; the generator on the existing gateway.

**Dev results to register as the expectation:** primary 0.83 / 0.87 (phi4 / mistral) against v1 0.50-0.54 and v1 at
temperature 0 0.51-0.55. Expect test to be lower: dev steered many changes in this round. v1's dev grades predate no
system change, since v1 did not change.

**Add to what is reported:**

- Time per answer, p50 and p95, with the hardware, and whether any stall occurred. Two dev attempts stalled for reasons
  unknown, so a stall during the test run is to be reported, and the affected run repeated only if it times out.
- The meaning check's removals on test, read by hand. On dev it removes 1 to 3 real claims and has caught no real
  error since the page look was added, so its value is an open question for the report, not a claim.
- Run-to-run noise: 165 of 172 dev answers matched between two runs differing only in a memory setting. Repeats on test
  are needed to separate this from real differences.

**Add to the blind session:**

- It must confirm each save and show a stored count; earlier clicks were lost once, cause unknown.
- The 6 v2 abstention items on which the judges disagreed.
- Correct v1 answers rejected on source support (above).
