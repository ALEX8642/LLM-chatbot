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
