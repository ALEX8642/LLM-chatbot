# Judge calibration labels

55 answers on the original dev items (35 from v1, 20 from v2 run 2), labelled per key fact, for
abstention and, on correct answers, for whether the cited source holds the key facts.

**These are Claude's labels, not human ones,** and were written after seeing Qwen's grades of the same
answers, so they are not blind. They choose among judges; they do not validate the winner. Plan 7's
blind grading session checks the chosen judge against Alexander, per system.

v2 answers are included because the judge must grade both systems' styles, and because the 42 items
give too few unanswerables from v1 alone. Answers whose grade could not be settled from their text were
left out (faa-07, faa-13, op-10 to op-13, parts-06 for v1). Selection rule: `evals/judge_select.py`.
