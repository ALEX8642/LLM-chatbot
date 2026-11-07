# Held-out test results (registered at tag `prereg`)

Run 2026-11-06/07 on the 169 frozen test items, with the code at `prereg` (`b131567`), as `docs/prereg.md` set out.
Raw outputs: `evals/results/raw/{v1,v1-t0,v2}-test.json`. Judge outputs and the analysis: `evals/results/test/`.

## Primary (registered)

v2 against v1, judge phi4, majority of 3 repeats.

| | v2 | v1 | Difference | 95% interval | v2 only / v1 only | McNemar p |
|---|---|---|---|---|---|---|
| Primary endpoint | **0.805** | 0.420 | **+0.385** | 0.209 to 0.516 | 72 / 7 | 1e-14 |

Both registered conditions hold: McNemar p < 0.05 and the interval lies above zero. **v2 gives more correct, supported
answers than v1 on this test set.** All 169 items were graded.

The interval is wide. Joining all 35 part-number questions into one cluster, as registered, leaves about 47 effective
items, and the design could only reliably detect a difference of about 28 points. The difference found is larger.

## Secondary (registered, Holm corrected)

| Contrast | v2 | Comparator | Difference | 95% interval | v2 only / other only | Holm p |
|---|---|---|---|---|---|---|
| v2 against v1 at temperature 0, phi4 | 0.805 | 0.426 | +0.379 | 0.222 to 0.488 | 70 / 6 | 1e-14 |
| v2 against v1, mistral, first repeat | 0.805 | 0.467 | +0.337 | 0.146 to 0.491 | 66 / 9 | 8e-12 |

## Exploratory

| Manual | v2 (phi4 / mistral) | v1 (phi4 / mistral) |
|---|---|---|
| FAA handbook (57) | 0.88 / 0.84 | 0.53 / 0.60 |
| Generator operator (51) | 0.78 / 0.78 | 0.45 / 0.53 |
| Generator parts (61) | 0.75 / 0.79 | 0.30 / 0.30 |

- **The gain does not rest on the parts manual.** It is largest there (+45 points), as the M2 review expected, but the
  FAA handbook gains 35 points and the operator manual 33 under phi4.
- **Part-number questions (35):** v2 0.80 / 0.86, v1 0.06 / 0.09.
- **Categories (phi4):** table 51 of 67 against 11; single-page 45 of 56 against 29; unanswerable correctly declined 32 of
  36 against 29. Figure (v2 4 of 5, v1 1 of 5) and multi-page (4 of 5, 1 of 5) are counts only, as registered.
- **Other cluster choices:** page clusters give +0.385, 0.292 to 0.473; section clusters, a check only, 0.297 to 0.477.
- **Repeats:** v2 gave the same answer to all 169 items in all 3 repeats, so its spread is zero and repeats added nothing for
  it. v1's primary across repeats: 0.434, 0.417, 0.407.
- **Judges:** phi4 and mistral agree on v2's item scores for 161 of 169.
- **Time per answer (v2, laptop RTX 4090 16 GB):** p50 13.3 s, p95 22 s, worst 23 s, in every repeat.
- **Meaning check:** removed no claim on test. The deterministic checks removed 20 claims a repeat. Its value is still
  unshown.

## Deviations and events

- **v2's first attempt failed.** It hung at repeat 3, item 130, until its 5-hour limit. Its last log line was written at
  22:55:43; Windows logged GPU driver event `nvlddmkm` 153 at 22:55:44, the only one from that driver in six days. As
  registered, v2 was rerun whole; no results had been written. The log is `evals/results/test/v2-attempt1.log`. The rerun
  used a shorter time limit, which does not affect answers. The earlier dev slowdowns left no such event and are still
  unexplained.
- The raw files do not record the commit; they were produced from a detached checkout of `prereg`.

## v2's misses (33 of 169)

Labelled by Claude, first by rule from recorded facts, then by reading the answer against the reference. Not yet
checked by Alexander. Per item: `evals/results/test/v2-misses.jsonl`.

| Label | Items | What it means |
|---|---|---|
| Wrong abstention, model found nothing | 7 | No claim offered: the evidence did not hold the answer, or the model did not see it |
| Incomplete | 6 | Right as far as it goes, but missing a key fact the reference has |
| Judge rejected support | 5 | Correct and citing the gold page; the judge did not find the facts in the cited block |
| Wrong abstention, claims removed by checks | 4 | The model answered; the fact checks removed every claim |
| Answered an unanswerable question | 4 | Two read a value from a figure or another table |
| Not retrieved | 2 | No gold page among those ranked |
| Checker removed a true claim | 2 | The unit check (op-2-3-13) and the column check (parts-g08-02) removed correct claims |
| Wrong passage, misread, judge miss | 1 each | |

Read with care, two things stand out. **About 6 misses look like judge errors** (5 rejected support plus op-2-1-08, whose
answer matches the reference); the blind grading should show whether they are. **The checks cost v2 up to 6 items**: two
true claims removed outright, and four abstentions where every claim was removed, not all of them read yet. The checks
are what make a citation trustworthy, so this is their price, now measured.

## Still to do (registered)

- Blind grading by Alexander (session published), and judge agreement per system with the 10-point rule.
- The misses in the README.
