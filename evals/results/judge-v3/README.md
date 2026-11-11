# Judge prompt version 3, checked against blind human grades

The local judges were harder on one system than the other: phi4 missed support in v1's whole-page citations. Version 3
(`evals/grade.py`, `evals/prompts.py`) makes three changes:
- A cited source over 3,000 characters is checked one key fact at a time, on the three passages nearest that fact.
- The source check is given the question.
- A reply with the wrong number of facts is asked again.

The correctness step (do the answer's facts match the key facts) is unchanged.

**How it was tested.** `evals/judge_calibrate.py` re-judges only the answers Alexander graded blind and compares them
with his grades.
- **Development set:** the unseen manual's 62 graded answers. The prompt was changed twice after looking at them
  (`dev-fist-phi4-step1.json`, `-step2.json`).
- **Held-out set:** the main test's 100 graded answers, run once on the final code (commit 8bc38ba).
- **Acceptance rule, set beforehand:** the gap between the systems in how often the judge fails an answer he passed is
  10 points or less on both sets.

## Wrongly failed: answers Alexander passed that the judge failed

| | phi4, prompt v2 | phi4, v3 | mistral, v2 | mistral, v3 |
|---|---|---|---|---|
| Main test (held out), v1 | 19 of 31 | **9** of 31 | 10 of 31 | 9 of 31 |
| Main test (held out), v2 | 7 of 42 | **4** of 42 | 6 of 42 | 5 of 42 |
| Gap, main test | 45 points | **19.5** | 18 | 17 |
| Unseen manual (development), v1 | 23 of 31 | **2** of 31 | 0 of 31 | 0 of 31 |
| Unseen manual (development), v2 | 10 of 18 | 8 of 20 | 7 of 20 | 7 of 20 |
| Gap, unseen manual | 19 against v1 | 34 against v2 | 35 against v2 | 35 against v2 |

Wrong passes hardly change: phi4 v3 wrongly passes 3 of 19 v1 and 1 of 8 v2 answers on the main test; on the unseen
manual, 1 v1 answer for each judge.

**Result: version 3 fails the acceptance rule.** It fixes what it was aimed at: phi4's support check now misses about as
often on v1's long citations as on v2's short ones (4 of v1's remaining 9 main-test errors are in the support step).
What is left is the unchanged correctness step, and it goes different ways on the two sets:
- **Main test:** both judges often say v1's long answers leave out a key fact that Alexander found in them.
- **Unseen manual:** every remaining v2 error comes from the correctness step:
  - **Detail the question did not ask for.** Four items list key facts the question does not ask for (fist-08, 28, 36,
    58), and v2's short answers leave them out. Alexander was told not to count such omissions; the judges' rule
    requires every key fact.
  - **Passes that look too generous.** For three answers he passed, the answer looks wrong or incomplete on reading
    (fist-33 gives the compression, 0.10 in, as the final thickness, 0.15 in; fist-48 and fist-90 leave out part of what
    was asked).
  - **A plain judge miss.** phi4 also misses "carbon dioxide" in one answer that states it (fist-44).

Both human-graded sets have now been used, so further tuning against them could not be checked honestly. The judges stay
as registered for the headline. Version 3 is a sensitivity with this warning, and the human-corrected results
(`evals/unseen/RESULTS.md`, `evals/results/TEST.md`) remain the best estimate.
