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

## What "verified" means

*As recorded in this M1 replay:* a green check meant the quote fuzzily matched the cited block and every number and
identifier appeared in the quote or its context. Meaning was not compared. On dev then, 146 of 269 verified claims
had no number or identifier, so for them the only test was the quote match.

*Since 2026-11-05 (not in this recording):* numbers and identifiers are checked against the source text the quote
matched, and a generator check asks whether the block, then the page, says what the claim says. See "Fixed since".

## For the review

**Does the promise look true?** On these 10, yes, by eye, from the first claim of each answer (the review checked the other text and table claims by box against line text). These questions were chosen to show the
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
- Time to the finished answer is about 8-16 s here (v1 about 2.4 s); on the 172 dev items p50 is 8.4 s and p95 is 61 s, unexplained.

To replay: `frontend/e2e/run.sh` for the scripted check; for this recording, serve it with
`python -m manualqa.server --replay docs/m1/live-answers.jsonl`, which also needs the page renders.

## Review result (2026-11-04)

An independent review found the promise holds on these answers, and that "verified" is much weaker than it looks.
Claude reproduced these with constructed inputs of the same shape; "dev" counts are the reviewer's, and were not re-derived.

| Severity | Finding | Example that wrongly passes |
|---|---|---|
| High | Claim meaning is never compared to the quote | "You may crank the engine for as long as needed", quote "Do not crank engine in excess" |
| High | Shifted table headers invert the wrong-column check (47+ rows on 6 pages, reviewer's count) | "The part number is 81349" (the CAGE code) passes; the true part number is removed |
| High | Facts are checked against the model's quote, which only fuzzily matches the source (0 on dev) | Claim and quote 88-20244, source 88-20243 |
| High | Column labels are easy to miss | "The quantity used is 30554"; "30554 is the part number" |
| Medium | Units, signs, number words in claims | "172 psi" on "25 psi (172 kPa)"; "-15" on "+15"; "thirty seconds" on "fifteen" |
| Medium | Ellipsis fragments are not ordered or anchored (3 on dev, benign) | "Do ... operate" drops "not" |
| Medium | Boxes can go on the wrong line or row with no warning | p22 blank lines misalign; unans-03; p48 table |
| Low | Figure claims show the same green check as verified ones; the spec wants a neutral mark | `ClaimList.tsx` |

### Fixed since (2026-11-05)

Each of the above now has a regression test except where noted. Column labels are matched after the value and as
abbreviations; facts use the matched source; units, signs, number words, ellipsis order and skipped negations are
checked; numbered item lists are rebuilt from the text layer's grid; blank lines no longer shift boxes; figure claims
show a neutral mark. Claim meaning is checked by the generator, which on real dev claims has so far caught no real
error (`evals/results/NOTES-v2-dev.md`). **Still open:** boxes on OCR pages, and tables whose structure comes from the
parser; figure claims are still not checked against the image; "Verified" remains a strong word for these checks.

None of these were fixed by this review. Most wrong-pass examples are constructed, so they show what the checker
would let through, not how often it happens.
