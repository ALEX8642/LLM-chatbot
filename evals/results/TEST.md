# Held-out test results (registered at tag `prereg`)

Run 2026-11-06/07 on the 169 frozen test items, with the code at `prereg` (`b131567`), as `docs/prereg.md` set out.
Raw outputs: `evals/results/raw/{v1,v1-t0,v2}-test.json`. Judge outputs and the analysis: `evals/results/test/`.

## Primary (registered)

v2 against v1, judge phi4, majority of 3 repeats.

| | v2 | v1 | Difference | 95% interval | v2 only / v1 only | McNemar p |
|---|---|---|---|---|---|---|
| Primary endpoint | **0.805** | 0.420 | **+0.385** | 0.209 to 0.516 | 72 / 7 | 1e-14 |

Both registered conditions hold: McNemar p < 0.05 and the interval lies above zero. **v2 gives more correct, supported
answers than v1 on this test set.** Every item has a majority score; the judge failed to grade 1, 1 and 2 of v1's 169
answers in its three repeats, and none of v2's.

**The systems differ in more than the pipeline.** v1 generates with Command R7B (`command-r7b`, Q4_K_M, run locally
through Ollama); v2 with Qwen3.8 (`Qwen3.8-Flash-Next-NVFP4-Fast`) behind an OpenAI-compatible gateway. The design planned
a row with v2's pipeline and Command R7B, to separate the two; it was not run, and the registration did not list it
among the omissions. The difference above is the pipeline and the generator together.

The interval is wide. Joining all 35 part-number questions into one cluster, as registered, leaves about 47 effective
items, and the design could only reliably detect a difference of about 28 points. The difference found is larger.

## Secondary (registered, Holm corrected)

| Contrast | v2 | Comparator | Difference | 95% interval | v2 only / other only | Holm p |
|---|---|---|---|---|---|---|
| v2 against v1 at temperature 0, phi4 | 0.805 | 0.426 | +0.379 | 0.222 to 0.488 | 70 / 6 | 1e-14 |
| v2 against v1, mistral, first repeat | 0.805 | 0.467 | +0.337 | 0.146 to 0.491 | 66 / 9 | 8e-12 |

Holm p: `python -m evals.analysis holm evals/results/test/analysis-v2-vs-v1-t0-phi4.json
evals/results/test/analysis-v2-vs-v1-mistral.json` (1.3e-14 and 7.7e-12, rounded above).

## Exploratory

Intervals here are 95% bootstraps over items (phi4, majority scores), so they ignore clustering and are narrower than
they should be.

| Manual | v2 (phi4 / mistral) | v1 (phi4 / mistral) | Difference, phi4 |
|---|---|---|---|
| FAA handbook (57) | 0.88 / 0.84 | 0.53 / 0.60 | +0.35 (0.20 to 0.50) |
| Generator operator (51) | 0.78 / 0.78 | 0.45 / 0.53 | +0.33 (0.16 to 0.49) |
| Generator parts (61) | 0.75 / 0.79 | 0.30 / 0.30 | +0.46 (0.31 to 0.61) |

- **Each manual gains on its own,** most on the parts manual, as the M2 review expected.
- **A registered expectation failed.** The registration expected v2's gain to be smaller on test than on dev (+0.32),
  since dev steered v2. It is larger (+0.385). v1 fell from 0.51 on dev to 0.42 on test, and test holds more of the
  parts manual (36% against 16%), where v1 scores 0.30.
- **Part-number questions (35):** v2 0.80 / 0.86, v1 0.06 / 0.09; difference +0.74 (0.57 to 0.89).
- **Abstention.** Unanswerable items declined, judged: v2 32 / 31 of 36, v1 29 / 28 (phi4 / mistral); as recorded by
  v2 itself, 31. Answerable items wrongly declined: v2 11 of 133 under both judges and as recorded; v1 22 / 20. v1 records
  no abstention of its own.
- **Source support at page level** (v2's cited pages, as v1 is graded, instead of its cited blocks): v2 0.817 / 0.811
  against 0.805 at block level.
- **Categories (phi4):** table 51 of 67 against 11; single-page 45 of 56 against 29; unanswerable correctly declined 32 of
  36 against 29. Figure (v2 4 of 5, v1 1 of 5) and multi-page (4 of 5, 1 of 5) are counts only, as registered.
- **Other cluster choices:** page clusters give +0.385, 0.292 to 0.473; section clusters, a check only, 0.297 to 0.477.
- **Repeats:** v2 gave the same answer to all 169 items in all 3 repeats, so its spread is zero and repeats added nothing for
  it. v1's primary across repeats: 0.434, 0.417, 0.407.
- **Judges:** phi4 and mistral agree on v2's item scores for 161 of 169.
- **Time per answer (v2):** p50 13.3 s, p95 22 s, worst 23 s, in every repeat, with retrieval on a 16 GB laptop GPU
  (RTX 4090 Laptop) and the generator on a separate server. v1, all on the laptop: median 2.3 s.
- **Meaning check:** removed no claim on test. The deterministic checks removed 20 claims a repeat. Its value is still
  unshown.

## Deviations and events

- **v2's first attempt failed.** It hung at repeat 3, item 130, until its 5-hour limit. Its last log line was written at
  22:55:43; Windows logged GPU driver event `nvlddmkm` 153 at 22:55:44, the only one from that driver in six days. As
  registered, v2 was rerun whole; no results had been written. The log is `evals/results/test/v2-attempt1.log`. The rerun
  used a shorter time limit, which does not affect answers. The earlier dev slowdowns left no such event and are still
  unexplained.
- The raw files do not record the commit; they were produced from a detached checkout of `prereg`.
- The failure labels below add three the registration did not list ("incomplete", "judge miss", "checker removed a true
  claim"), because the registered set had no place for what reading the misses found.

## v2's misses (33 of 169)

Labelled by Claude, first by rule from recorded facts, then by reading the answer against the reference. Where
Alexander's blind grading covered an item, the file records his grade. Per item: `evals/results/test/v2-misses.jsonl`.

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

Two things stand out. **About 6 misses look like judge errors:** the 5 rejected on support, which Alexander passed in
blind grading, and op-2-1-08, whose answer matches the reference. **The checks cost v2 up to 6 items:** two true claims
removed outright, and four abstentions where every claim was removed, some of which may have been right to remove.

## Blind grading (registered check)

Alexander graded 100 answers, v1's and v2's first-repeat answers to 50 test items, with the system hidden and the order
shuffled (`evals/sessions/blind_grades.jsonl`, key `evals/sessions/blind_key.json`). He is not a subject expert and
found it hard; his grades are one careful reader's, not an expert's. A pass is "correct" with the cited pages showing it,
or a decline on an unanswerable item.

| | v2 | v1 | v2 only / v1 only | McNemar p |
|---|---|---|---|---|
| Alexander, 50 items | 42 (0.84) | 31 (0.62) | 15 / 4 | 0.019 |
| phi4 on the same answers | 36 | 15 | | |

**The registered judge-validity rule is triggered.** On the whole sample phi4 wrongly fails 19 of 50 v1 answers (38%)
against 7 of 50 v2 answers (14%), more than the 10-point limit, so the headline carries this warning and the blind
contrast stands beside it.

The rule did not allow for how the sample was drawn, and that matters here. 21 items were chosen because the judge had
already rejected them or disagreed: 15 correct v1 answers rejected on source support, 8 v2 items where the judges
disagreed, and 5 correct v2 answers rejected on support (9 distinct v2 items). Alexander passed 14 of the 15 v1 answers
and 8 of the 9 v2 ones. On the 29 items drawn at random, phi4 agrees with him on 24 of 29 v1 answers and 28 of 29 v2
answers, wrongly failing 2 v1 and 1 v2 and wrongly passing 3 v1: no clear bias there.

So the judge does miss support in v1's answers more than in v2's, in the specific way the M2 review predicted: v1 cites
whole retrieved pages, and the judge often does not find the fact among them. Allowing for it, by counting those 14 v1
and 5 v2 answers as passes, or by letting Alexander's grade replace the judge's on every graded item, puts the gap at
31 to 33 points instead of 38 (majority scores). These corrections are estimates, not registered figures. **Every
reading still has v2 clearly ahead.**
