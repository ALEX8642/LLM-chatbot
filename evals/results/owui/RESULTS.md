# v2 against a stock RAG pipeline with the same generator

Registered in [`docs/prereg-owui.md`](../../../docs/prereg-owui.md) (tag `prereg-owui`) before any test or FIST question
was asked.
- **v2:** its registered answers.
- **Stock:** Open WebUI v0.13.0's built-in knowledge-base retrieval as one household runs it, with Docling extraction,
  hybrid search and a reranker, and with the same Qwen3.8 generator at the same settings.
- **Runs:** 3 repeats per system. Raw answers are in `raw/`, judged files and `analysis-v2-vs-owui.json` here.

**In short:** on the main test, v2's pipeline beats the stock one by 27 points with the same generator, and every reading
agrees. On FIST, the manual neither was built on, the two are level. v2's lead comes from work done on the development
manuals (above all their tables), and it did not carry over to a new manual.

## Main test (169 items, primary)

| Reading | v2 | Stock | Difference (95% interval) | McNemar p | Only v2 / only stock |
|---|---|---|---|---|---|
| phi4, prompt v2, majority of 3 (**registered primary**) | 0.805 | 0.533 | **+0.272** (+0.128 to +0.374) | 8×10⁻¹⁰ | 53 / 7 |
| mistral, first repeat | 0.805 | 0.586 | +0.219 (+0.059 to +0.343) | 1×10⁻⁶ | 48 / 11 |
| phi4, prompt v3 (checks long sources fact by fact) | 0.822 | 0.562 | +0.260 (+0.120 to +0.369) | 2×10⁻⁹ | 51 / 7 |
| correct alone, regardless of support (phi4) | 0.834 | 0.627 | +0.207 (+0.052 to +0.331) | 4×10⁻⁷ | 42 / 7 |

**The claim "v2's pipeline beats the stock pipeline with the same generator" holds on the main test.** It meets the
registered rule, and v2 leads on every reading registered in advance, including the ones that correct for phi4's
trouble with long sources. So the result is not that bias.

**By manual and category, phi4, majority of 3** (v1 with Command R7B and v1 with Qwen3.8 for reference):

| | n | v1 R7B | v1 Qwen | Stock | v2 |
|---|---|---|---|---|---|
| Army operator manual | 51 | 0.45 | 0.49 | 0.61 | 0.78 |
| Army parts manual | 61 | 0.30 | 0.46 | 0.46 | 0.75 |
| FAA handbook | 57 | 0.53 | 0.72 | 0.54 | 0.88 |
| Tables | 67 | 0.16 | 0.37 | 0.31 | **0.76** |
| Single page | 56 | 0.52 | 0.55 | 0.61 | 0.80 |
| Unanswerable | 36 | 0.81 | 0.94 | 0.94 | 0.89 |
| Figure / multi-page | 5 / 5 | 0.20 / 0.20 | 0.40 / 0.40 | 0.20 / 0.00 | 0.80 / 0.80 |

Tables carry most of the gap: v2 reads table rows as structured cells, and the stock pipeline gets them as flattened
chunk text. The stock pipeline does a little better than v2 on questions the manuals do not answer.

## FIST 3-30, a manual neither was built on (104 items, secondary)

| Reading | v2 | Stock | Difference (95% interval) | McNemar p |
|---|---|---|---|---|
| phi4, majority of 3 | 0.804 | 0.824 | −0.020 (−0.101 to +0.070) | 0.82 |
| mistral, first repeat | 0.817 | 0.817 | 0.000 (−0.086 to +0.093) | 1.0 |
| phi4, prompt v3 | 0.827 | 0.798 | +0.029 (−0.064 to +0.125) | 0.69 |
| correct alone (phi4) | 0.824 | 0.873 | −0.049 (−0.125 to +0.030) | 0.33 |

Level on every reading. Both systems score 0.87 on single-page items and 0.40 on its 15 tables. v2's tables score here
is below its main-test 0.76: some of that is its checks misfiring on these tables (`evals/unseen/RESULTS.md`; several of
those removals are fixed since). With the fixes, a re-run of v2 scores 0.843 (phi4), still within reach of the stock
pipeline's 0.824.

## A second unseen manual (kept private)

The same comparison was run on a second manual neither system was built on: 80 items, from another publisher and
subject. The manual is copyrighted, so the manual, its items and its outputs are kept out of this repository. It was
registered privately, with the same protocol, before the stock pipeline answered. Its answers ran on Open WebUI 0.13.3:
the owner updated the server during the run, and the retrieval settings were unchanged.

| Reading | v2 | Stock | Difference (95% interval) | p |
|---|---|---|---|---|
| phi4, majority of 3 (primary) | 0.779 | 0.636 | +0.143 (+0.013 to +0.278) | 0.043 |
| mistral | 0.756 | 0.692 | +0.064 (−0.066 to +0.197) | 0.42 |
| phi4, prompt v3 | 0.800 | 0.675 | +0.125 (0.000 to +0.254) | 0.064 |
| correct alone | 0.831 | 0.727 | +0.104 (−0.025 to +0.235) | 0.17 |

v2 leads on every reading, but the pre-stated rule (a lead on the primary alone is "not shown") applies, so it is not
shown. The stock pipeline did worst on that manual's tables (0.49, against v2's 0.63 and v1's 0.76). Against v1 on the
same manual, v2 was level (0.78 against 0.78; with blind Opus grades of the disputed answers, +0.08, not significant).

## Other observations (registered as descriptive)

- **Long manuals fail to upload as is.** Open WebUI's Docling call gives up after 120 s, so the 114-page FAA handbook
  failed whole, and 40-page parts of the parts manual still timed out. The main-test manuals went in as 20-page parts.
- **Retrieval is not repeatable.** All three repeats gave the same answer for only 24 of 169 test items and 24 of 104
  FIST items; v2 gave the same answer every time.
- **Citations:** stock answers cite a source in over 99% of cases. It cites by file, so its cited text is longer than
  v2's: a median of 1,900 characters on the main test and 3,500 on FIST.
- **Time per answer:** about 16 s for stock, about 13 s for v2 (median).
- Nobody graded these answers by hand. The FIST blind check showed phi4 under-credits long citations; that would lower
  the stock pipeline's FIST score, not v2's, so it cannot hide a v2 lead there.

## What this means

The stock pipeline already captures most of what a bigger generator brings:
- **Main test:** it lands about where v1 does with the same Qwen3.8 (0.53 against 0.56), well below v2.
- **FIST:** it lands above v1 with Qwen (0.82 against 0.69) and level with v2.

v2's extra machinery pays off on the manuals it was developed against: their parts tables, figures and multi-page
procedures. It has not yet been shown to pay off on a manual it was not built for.
