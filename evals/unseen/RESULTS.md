# Unseen manual: results

Neither system had seen FIST 3-30 (Reclamation, transformer maintenance, 87 pages) before this run. The plan is
`docs/prereg-unseen.md` (tag `prereg-unseen`); the items are `fist.jsonl` (104: 92 answerable, 12 unanswerable).
Raw outputs are in `results/raw/`, judged files and analyses in `results/`.

**In short:** the registered test came out in v2's favour, but Alexander's blind check shows that result came from the
judge. phi4 rejects correct v1 answers far more often than correct v2 answers. With his grades in place of the judges'
on the answers he checked, v2 and v1 are level on this manual: +3.9 points, interval −4 to +13, p 0.48.

## Registered result

The endpoint is correct and supported, phi4, majority of 3 repeats. The test is paired, with page clusters.

| | v2 (Qwen3.8) | v1 (Command R7B) | Difference | 95% interval | McNemar p |
|---|---|---|---|---|---|
| phi4 (primary) | 0.804 | 0.647 | +0.157 | 0.031 to 0.284 | 0.014 |
| mistral (secondary) | 0.817 | 0.856 | −0.038 | n.s. | |

The primary met the registered rule (p < 0.05 and the interval above zero). The secondary judge disagreed. Both systems
beat the registered guesses (v2 0.60-0.75, v1 0.30-0.45).

## Blind check by Alexander

There were 62 screens, with the system hidden and the order shuffled. The selection was fixed before grading
(`evals/sessions/build_blind_unseen.py`, `results/blind_selection.json`):
- all 24 v1 answers that phi4 judged correct but unsupported while mistral passed them;
- all 22 v2 answers phi4 failed;
- 8 controls per system, drawn from answers both judges passed.

To pass, an answer had to be right and its cited pages had to show it, which is the judges' rule. A decline passes only
on an unanswerable item. Grades are in `results/blind_grades.jsonl`. Alexander is not a transformer expert. He graded
against the reference answer and the page images. Writing style can give the system away, since v2 writes short
quote-backed claims, so the blinding is weak.

| Answers checked | Alexander passed | Judges agree with him |
|---|---|---|
| v1, the judge split (24) | 23 (one cited a page that does not show it) | phi4 on 1, mistral on 23 |
| v2, phi4 failures (22) | 12 | phi4 on 10 (it gave no grade on 2), mistral on 15 |
| controls (16) | 16 | both on all 16 |

**Judge validity rule** (registered: a gap over 10 points between systems in how often the judge wrongly fails them):

| Judge | Wrongly fails v1 | Wrongly fails v2 | Gap | Wrong passes |
|---|---|---|---|---|
| phi4 | 23 of 31 (74%) | 10 of 18 (56%) | 19 points against v1 | 0 |
| mistral | 0 of 31 (0%) | 7 of 20 (35%) | 35 points against v2 | 1 (v1 fist-70) |

The rule is triggered for both judges, in opposite directions. The sample was chosen where the judges fail answers, so
these rates describe the disputed answers, not the whole run. The 16 controls found no wrong passes.

**A second grader.** Claude Opus 5.5 graded the same 62 screens later, blind, from the same page images and with
the same instructions (`results/opus_blind_grades.jsonl`). It agrees with Alexander's pass/fail on 55 of 62, with no
lean towards either system: on v1 they pass the same number, and on v2 Opus passes 3 fewer. Of the 7 disagreements,
Opus fails three v2 answers whose problems a reading confirms:
- fist-33 gives the compression (0.10 in) as the thickness (0.15 in);
- fist-48 leaves out the daily sampling the question asks for;
- fist-90 leaves out the reading to investigate.

On the same screens phi4 agreed with him on 27 of 60 and mistral on 54 of 62. Opus is not independent of the author
(Claude wrote the items and the systems), so it is a check on the grading, not a replacement for a person.

## Human-corrected result

For the 62 checked answers, Alexander's grade replaces the judge's. The other answers keep phi4's (or mistral's) grade.
(`results/analysis-human-corrected.json`)

| | v2 | v1 | Difference | 95% interval | McNemar p |
|---|---|---|---|---|---|
| phi4 + Alexander | 0.903 | 0.864 | +0.039 | −0.041 to 0.125 | 0.48 |
| mistral + Alexander | 0.885 | 0.846 | +0.038 | −0.044 to 0.128 | 0.50 |

The two judges agree once corrected. On this manual v2 is not shown to be better than v1. The registered result is
reported above, unchanged, and this one stands beside it.

Caveats:
- The answers he did not check keep the judge's grade.
- v1 answers that both judges failed were not checked.
- v1 with Command R7B is not fully deterministic across repeats; his grade is of the first repeat.

## Why v2 failed (`results/v2-misses.jsonl`)

All 22 of v2's phi4 failures:

| Label | Items |
|---|---|
| Judge miss (Alexander: right and supported) | 12 |
| True claims removed by v2's own checks (5 left the answer incomplete, 2 left a decline) | 7 |
| Wrong claim removed, leaving a decline (fist-73: the check was right) | 1 |
| Incomplete answer from the generator | 1 |
| Answered an unanswerable item (fist-96) | 1 |

fist-96 gave the 250 ppb investigate threshold and claimed no end-of-life point. Alexander graded it correct, but the
registered rule fails it because it did not decline.

The seven true claims that v2 removed were all caught by checks written on the development manuals:
- the number check: "900 not in source" for a value taken from the question; "7 not in source" for 7¾;
- the table-column check: it misread three rows of this manual's gasket and TDCG tables;
- the wording check: once;
- the quote-block check: once.

On the main test, v2's checks removed true claims on 2 of 33 failures; here they did on 7 of 10. The checks overfit
the manuals they were built on.

**Fixed after the run** (a change after registration, not part of the registered result): footnote markers such as "[4]"
no longer count as numbers; "7¾" reads as 7 3/4; a value taken from the question passes when it falls inside a range
the source gives; a column heading's unit in brackets ("(in inches)") is not needed to name the column. Re-run offline
on every claim recorded (`evals/check_audit.py`), the fix lets through 7 claims v2 removed on FIST (fist-10, 35, 37, 40,
45, 47, 48) and 3 of Opus's. It changes no verdict on the main test or development runs. The one claim it does not
rescue, fist-14, quotes a sentence that starts on the previous page. Those claims would still meet the meaning check, so
what the fix does to the score needs a new run.

**Re-run with the fixes** (v2 at commit 1827159, which also has two later check fixes from another manual; one repeat,
since v2 gives the same answers each time; `results/raw/v2fix-fist.json`). The same 7 answers changed and no other. The
meaning check removed none of the rescued claims.

| Judge | v2 registered | v2 with fixes | v1 | Fixed v2 − v1 (95% interval) |
|---|---|---|---|---|
| phi4 | 0.804 | 0.843 | 0.647 | +0.196 (0.079 to 0.317), p 0.002 |
| mistral | 0.817 | 0.865 | 0.856 | +0.010 (−0.071 to 0.097), p 1.0 |

The two judges still disagree about v1 for the reason above, so the human-corrected comparison is the better guide:
before the fix it had the systems level. The fixed answers have not been graded by a person.

## Other generators (not human-checked)

Correct and supported, phi4 / mistral:

| | v1 R7B | v1 Qwen3.8 | v2 Qwen3.8 | v2 Opus 5.5 |
|---|---|---|---|---|
| Main test | 0.420 / 0.467 | 0.556 / 0.645 | 0.805 / 0.805 | 0.849 / 0.870 |
| FIST | 0.641 / 0.856 | 0.686 / 0.923 | 0.804 / 0.817 | 0.860 / 0.837 |

- v1 with Qwen3.8 (`evals/v1_generator_swap.py`) is the like-for-like comparison, with the same generator in both
  pipelines.
- Opus 5.5 was run through the Batch API (`evals/batch_run.py`, about $14 in total).
- Opus over Qwen3.8 in v2: +5 / +7 points on the main test and +6 / +2 on FIST, none significant.
- Opus wrote claims that v2's checks removed 41 times, against 11 for Qwen3.8, so its score is a floor.
- On FIST, phi4's bias against v1's citations affects these columns as it did the registered one. Judged correct alone,
  regardless of support: v1 R7B 0.875, v1 Qwen 0.952, v2 0.808, Opus 0.856.

## Deviations

- The registration was written after the manual had been parsed.
- The raw files do not record the commit they were run from. They were run at tag `prereg-unseen` for v2, and v1 at tag `v1` through the harness at `prereg`.
- The blind check's selection was written after the judged results were seen. It was fixed before grading.

## Judge prompt version 3

A later judge prompt, tuned on these grades and checked on the main test's, cuts phi4's wrong fails on good v1 answers
here from 23 of 31 to 2. It still fails the 10-point rule on both sets, so the registered judges stay as they are:
[`evals/results/judge-v3/README.md`](../results/judge-v3/README.md).

