# Registration: v2 against v1 on a manual neither was built on

**Registered at tag `prereg-unseen`, after the items were frozen (tag `unseen-items-frozen`) and before either system
answered a question on this manual.** Everything after the tag that changes a result is reported as a deviation.

## Why

The main test (`docs/prereg.md`) held out sections, not manuals: test and dev share three manuals, and dev steered v2's
checks. This asks whether v2's lead holds on a manual from another publisher and subject that nobody looked at while
building either system.

## Question

On FIST 3-30, *Transformer Maintenance* (Bureau of Reclamation, 2000), does v2 give more answers that are correct and
supported by what they cite than v1?

## Items

`evals/unseen/fist.jsonl`: 104 items (92 answerable: 75 single page, 15 table, 2 multi-page; 12 unanswerable near misses),
written by Claude from the PDF's text layer on 2026-11-10 before the manual was parsed or answered. Sha256 begins
`1c7842343fda9bab`. Nobody checked them before the run; Alexander is asked to check a sample afterwards (below).

## Primary

As registered for the main test, unchanged:

- **Endpoint (binary, per item):** the answer is correct and the judge finds its key facts in the cited source (a cited
  page for v1, the cited block for v2). An unanswerable item passes when the system abstains.
- **Judge:** `phi4:14b`, grader prompt version 2. **Repeats:** 3 per system; an item's score is the majority of its graded
  repeats, a tie fails; ungraded items are left out of the pair and counted.
- **Test:** exact McNemar, two-sided, 5%, discordant counts printed. **Interval:** paired bootstrap of the difference,
  95%, 10,000 draws, seed 20261106, resampling clusters of items that share a gold page (`evals/analysis.py`, primary
  clusters; no part-number questions here).
- **The claim "v2 is better on an unseen manual"** needs both McNemar p < 0.05 and an interval above zero.

## Secondary and descriptive

- v2 against v1, judged by `mistral-small3.2:24b` on the first repeat (Holm with the primary is not applied: one
  secondary, reported as a check).
- v2's score here against its score on the main test (0.805): reported side by side with each interval, no test. This is
  the out-of-sample drop, and the number this registration exists for.
- By category (single page, table, unanswerable); abstention; removed claims per answer; time per answer.
- Every v2 miss labelled as in the main test.

## Systems, fixed before the run

- **v2:** the code at this tag. It includes changes made after the main test (the wording check on quotes, the
  container work), none tuned on this manual. Parse: PaddleOCR-VL through `evals/spike/run_spike.py`, one resuming run restarted by a watchdog after 10 minutes
  without a saved page (the start-up hang in decision 001): all 87 pages parsed, no errors, 6 restarts. A first attempt in
  10-page runs hit that hang on almost every start and was abandoned before ingest; its 37 finished pages were kept, being
  the same parser on the same pages. Ingest: `manualqa.ingest` with the locked dependencies. Generator Qwen3.8 through the same
  gateway as the main test; embedder Qwen3-Embedding-0.6B; reranker Qwen3-Reranker-4B.
- **v1:** unchanged code at tag `v1`, run through the harness at tag `prereg` as in the main test, with Command R7B on
  Ollama. Its own ingest script indexes only this manual, into a separate Qdrant and OpenSearch, so its original indexes
  are untouched.
- **Source text for grading:** this manual's v2 `composed.jsonl`, sha256 recorded in `evals/unseen/README.md` at this
  tag.
- **Environment:** the laptop's 16 GB GPU, as before.

## Expectation

v2 should stay ahead, by less than on the main test, because its checks were tuned on the three development manuals and
this manual's tables and garbled cover pages are new to it. A guess, not a threshold: v2 0.60-0.75, v1 0.30-0.45.

## Running it

1. Tag `prereg-unseen`. Run v2 and v1, 3 repeats each, with the code at the tag. A run ended by a failure is rerun whole
   and the failure reported.
2. Judge all repeats with phi4, the first repeat with mistral. Commit raw and judge outputs, then run the analysis.
3. Afterwards: Alexander checks a sample of items and answers blind, as in the main test; a defect found after the run
   gets the registered result first and the fixed one beside it, labelled.

## Known limits

- One manual, 104 items: an interval of roughly ±10-15 points is expected.
- Claude wrote the items; nobody checked them before the run.
- Both systems' generators differ (Command R7B and Qwen3.8), as in the main test.
