# M1 review package

The core promise: an answer whose claims light up their source on the page beside it.

`live-answers.jsonl` is 10 live answers recorded through the server (Qwen3.8 generator, default embedder
and reranker, the full ingest of the three manuals), on questions from the original dev set. Numbered
screenshots are those answers replayed through the built frontend, with the first claim clicked.

| # | Question | Result |
|---|---|---|
| 01 | Air cleaner filter part number | Verified; item, part number and description boxed in row 17 |
| 02 | Voltage regulator part number | Two verified claims, one per alternator |
| 03 | Battery cover part number and quantity | Two verified claims |
| 04 | Rating plate kW on JP4 | Read from figure; plate boxed; **same claim twice** |
| 05 | Rating plate capacity at 8,000 ft | Read from figure; plate boxed; **same claim twice** |
| 06 | Cranking limit (letter-spaced scan) | Verified; "fifteen seconds" passage boxed |
| 07 | Switch positions to start | Four verified claims |
| 08 | Net weight and CG, worked example | Two verified claims |
| 09 | Sample loading problem | Three verified claims across pages 50 and 54 |
| 10 | SR20 crosswind (not in the manual) | Abstains and lists the pages it looked at |

## For the review

**Does the promise look true?** On these 10, yes, by eye. These questions were chosen to show the
behaviours, and were part of the set the checker was tuned on, so this shows the feature works, not how
often. The numbers are in `evals/results/NOTES-v2-dev.md`.

**Are removed claims sensible?** No live answer here had a claim removed.
`scripted-cage-trap.png` shows the display: its answers come from a **scripted generator** run through the
real answer path (`tests/manualqa/test_e2e_recording.py`), not from a live model. Live removals are listed
in the notes: most in run 1 were wrong removals, now mostly fixed.

**Known problems to judge:**

- Figure claims are not fact-checked against pixels. On dev, faa-14 reads the wrong value from a graph and
  is shown with the same confidence as a right one, with only the "read from figure" label.
- Identical claims from two near-identical figures show as a repeated line (04, 05).
- Highlights are per line, so a box can include a neighbouring word (06: "Allow").
- Claims can be true yet not answer the question (unans-03 in the notes); nothing checks relevance.
- Time to the finished answer is about 8-16 s here (v1 about 2.4 s).

To replay: `frontend/e2e/run.sh` for the scripted check; for this recording, serve it with
`python -m manualqa.server --replay docs/m1/live-answers.jsonl`, which also needs the page renders.
