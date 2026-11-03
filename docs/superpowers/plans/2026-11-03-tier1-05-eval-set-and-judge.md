# Eval Set and Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A frozen, section-split evaluation set (dev ≥ 80 with ≥ 20 unanswerable; hand-written test 150–200 with 30+ near-miss unanswerables), every item mechanically anchored to its source, graded by a local judge from a family no compared generator uses, with v1 and v1 at temperature 0 re-run and re-graded on dev.

**Architecture:** Items live in one pool (`evals/pool/*.jsonl`), each tagged with its manual section and with anchors (exact strings that must appear on its gold pages, or must appear nowhere for an unanswerable). A deterministic splitter assigns whole sections to dev or test, keeping the 42 existing items in dev. Grading (`evals/grade.py`) does normalised exact match for short answers and a key-fact checklist judged per fact, plus "key fact in the cited source" for the primary endpoint. The judge is chosen on a labelled calibration set among local models served by Ollama on the laptop. A private artifact runs the gold-answer session; its confirmed labels come back into the repo before the test set is tagged.

**Tech Stack:** Python 3.12 (stdlib, `rapidfuzz`, `requests`), pytest; Ollama on the laptop for judge candidates; the composed parses from plan 2 (`data/ingest/composed.jsonl`) for anchor checks; an Artifact page with a shared database for the gold session.

**Spec:** `docs/superpowers/specs/2026-11-01-v2-design.md` (Evaluation: Item pool and splits, Grading, Statistics; Human checks 1; Delivery tiers, Tier 1). Roadmap row 5: `docs/superpowers/plans/2026-11-02-tier1-roadmap.md`.

## Global Constraints

- "split into **dev and test by manual section** (so tuning cannot carry over through shared pages), stratified by category, after writing and before any v2 run on test sections. The existing 42 items are dev already."
- "**Dev ≥ 80 items, ≥ 20 unanswerable**"; tier 1: "a hand-written test set of 150–200 split by section; near-miss unanswerables" (30+ in test).
- "Provenance recorded per item (written by Claude, edited by Alexander, paraphrased by which model)."
- "Short factual answers by normalised exact match. Free-form answers against a **key-fact checklist** per reference answer, not a holistic grade."
- "**Primary judge from a different model family than every compared generator** (Qwen and Cohere are generators, so neither judges the headline)"; runs locally. "No pairwise judging." "Length bias checked by regressing judge scores on answer length."
- Primary endpoint: "the answer is correct, and the independent judge finds its key fact in the cited source (a cited page for v1 …; the cited quote's block for v2)."
- "v1 is re-run and re-graded with the new judge; the Qwen-graded numbers in `evals/results/NOTES.md` are history, not the comparison."
- Gold session: "about 60 test items, split by category, before the test set freezes … pre-filled labels are not counted as human until he has confirmed them." "Gold error rate reported with its interval."
- No LAN IPs, host names or keys in anything committed.
- Out of scope (tier 2): templated table items, paraphrase robustness, the fourth manual, counterfactual edits.

## Review Focus

1. **A gold page in a section of the other split** (an item whose pages straddle sections): the splitter links every section an item touches, so they land in the same split. `test_linked_sections_share_a_split` (Task 3).
2. **The same fact asked in dev and test** through different wording or a duplicated page: near-duplicate questions across splits are flagged. `test_near_duplicate_across_splits_flagged` (Task 3).
3. **Judge output that is not valid JSON or skips a fact**: the item is marked `judge_error` and excluded with a count, never scored as wrong. `test_malformed_judge_output_is_judge_error` (Task 4).
4. **Abstention on either side**: an answerable item that abstains scores 0 and is counted as abstained; an unanswerable item is correct only if it abstains. `test_abstention_scoring` (Task 4).
5. **Equivalent answers written differently** (`3.8 times` / `3.8`, `P14-8969` / `p14 8969`, `15 ± 3` / `15 +/- 3`): exact match normalises numbers, case, dashes and ± before comparing. `test_exact_match_normalisation` (Task 4).

---

### Task 1: Sections, item schema and validator

**Files:** create `evals/sections.json`, `evals/items.py`, `tests/evals/test_items.py`; move `evals/qa.jsonl` → `evals/pool/legacy.jsonl` (keep `evals/qa.jsonl` as the dev file the splitter writes, so `run_eval.py --qa` keeps working).

**Interfaces — produces:**
- `evals/sections.json`: `{manual_file: [{"id": str, "title": str, "first": int, "last": int}]}`, contiguous and covering every page once. Sections are TOC units (FAA chapters, operator chapter sections, parts figure groups starting at their first figure page); FAA and operator units longer than 6 pages are cut at bookmark pages into pieces of ≥ 3 pages (the FAA outline is flat). Front matter, appendices, glossary and indexes are sections of their own.
- `Item` (dataclass): `id, manual, sections: list[str], category ∈ {single_page, multi_page, table, figure, unanswerable}, question, gold_pages: list[int], reference_answer, key_facts: list[str], anchors: list[str], exact_answer: str | None, near_miss: bool, provenance: dict ({"written_by", "edited_by", "date"})`.
- `load_items(path) -> list[Item]`, `dump_items(items, path)`, `section_of(sections, manual, page) -> str`.
- `validate(items, sections, pages_text: dict[(manual, page), str]) -> list[str]` (problems, empty when valid).

- [ ] **Step 1: Tests** in `tests/evals/test_items.py`:
  - `test_sections_cover_every_page_once`: for each manual in `manuals/SOURCES.md`, the sections' ranges are contiguous from 1 to its page count.
  - `test_sections_match_gold_pages`: an item's `sections` must equal the sections of its gold pages (answerable) or name one on-topic section (unanswerable); a mismatch → a problem.
  - `test_anchor_must_be_on_a_gold_page`: anchor `"P14-8969"` on parts p59 → valid; on p58 → problem.
  - `test_unanswerable_anchor_must_be_absent`: an unanswerable item's anchors (terms the question needs, e.g. `"torque"`) must not appear on any page of its manual; present → problem. Near-miss unanswerables must name one on-topic section, answerable ones `gold_pages` non-empty and `key_facts` 1–4.
  - `test_legacy_items_valid`: all 42 legacy items, with sections, key facts and anchors added, validate against the real composed text (skipped when `data/ingest/composed.jsonl` is absent).
- [ ] **Step 2:** FAIL → implement → PASS (`pytest tests/evals/test_items.py -q`). Anchor matching uses `manualqa.textnorm.norm` on both sides (case, whitespace, letter spacing).
- [ ] **Step 3:** Add `sections`, `key_facts`, `anchors`, `exact_answer` (where the reference is a single value), `near_miss: false` and `provenance: {"written_by": "Claude", "edited_by": null, "date": "2026-11-01"}` to the 42 legacy items; `test_legacy_items_valid` passes.
- [ ] **Step 4:** Commit `evals: sections, item schema and anchor validator`.

### Task 2: Write the item pool

**Files:** create `evals/pool/faa.jsonl`, `evals/pool/operator.jsonl`, `evals/pool/parts.jsonl`; `evals/pool/README.md` (the writing procedure).

**Interfaces — consumes:** `Item`, `validate` (Task 1); composed text from `data/ingest/composed.jsonl` (copy it from the laptop; `data/` is gitignored).

- [ ] **Step 1: Write the procedure first** (`evals/pool/README.md`): items are written by Claude from the composed text and page renders, section by section, before any split; per section about 1 item per 2 pages, mixing categories where the pages allow (tables on parts and specification pages, figures where a value is read from a drawing, multi-page where an answer needs two pages of one section); every answerable item gets 1–4 key facts and anchors copied verbatim from the page; every section gets at least one near-miss unanswerable (on the section's topic, asking for something the manual does not contain, checked by absent anchors). No questions about front matter, indexes or blank pages.
- [ ] **Step 2: Write** about 260 new items so that the pool holds ≥ 300 including the 42 legacy items, ≥ 70 unanswerable of which ≥ 55 near-miss. Validate after each manual: `python -m evals.items validate evals/pool` → `0 problems`.
- [ ] **Step 3:** Print the pool table (items per manual × category, unanswerable, near-miss) into `evals/pool/README.md`; commit `evals: item pool (N items, written by Claude)`.

### Task 3: Section split

**Files:** create `evals/split.py`, `tests/evals/test_split.py`; writes `evals/qa.jsonl` (dev), `evals/test.jsonl`, `evals/split.json` (section → split, seed, counts).

**Interfaces — produces:** `split(items, sections, seed: int, forced_dev: set[str]) -> dict[str, str]` (section id → `"dev"` | `"test"`); `near_duplicates(dev, test, threshold=90) -> list[tuple[str, str]]` (rapidfuzz `token_set_ratio` on normalised questions).

- [ ] **Step 1: Tests:**
  - `test_forced_sections_stay_dev`: sections of the legacy items are dev.
  - `test_targets_met`: on the real pool, dev ≥ 80 items and ≥ 20 unanswerable; test hand-written items 150–200 with ≥ 30 near-miss unanswerables; per category, the test share is within 15 points of the pool share.
  - `test_no_page_in_both_splits`: no gold page of a test item lies in a dev section (by construction; asserted).
  - `test_linked_sections_share_a_split`: an item spanning sections A and B → A and B get the same split, and forcing A to dev takes B with it.
  - `test_near_duplicate_across_splits_flagged`: two questions differing only in word order across splits → flagged.
  - `test_split_is_deterministic`: same seed → same assignment.
- [ ] **Step 2:** FAIL → implement → PASS. Algorithm: link sections that share an item (union-find) into units; start with the units holding forced dev sections; add further units to dev in seeded random order, taking a unit only while it moves dev toward its targets (items, unanswerable, per-category shares) without exceeding 110 dev items; everything else is test. If test exceeds 200 hand-written items, drop seeded-random answerable items from the largest test category back to the pool's `reserve` (recorded in `split.json`), never unanswerables.
- [ ] **Step 3:** Run `python -m evals.split --seed 20261103`; resolve every flagged near-duplicate by rewriting or dropping one of the pair; commit the split files `evals: section split (dev N, test M)`.

### Task 4: Grading: exact match, key-fact checklist, source support

**Files:** create `evals/grade.py`, `evals/prompts.py`, `tests/evals/test_grade.py`; modify `evals/run_eval.py` (`score --grader keyfacts --judge-url --judge-model`, keep the old grader as `--grader legacy` for history).

**Interfaces — produces:**
- `normalise(s: str) -> str` (case, Unicode dashes → `-`, `±`/`+/-` → `±`, collapse spaces, strip trailing punctuation, numbers like `3.80` → `3.8`).
- `exact_match(answer: str, exact: str) -> bool` (normalised `exact` occurs in the normalised answer as a whole token sequence).
- `grade_item(item: Item, out: dict, judge) -> dict` with `correct: bool | None`, `facts: list[{"fact", "present"}]`, `supported_in_source: bool | None`, `abstained: bool`, `primary: bool | None`, `judge_error: str | None`, `answer_chars: int`.
- `length_bias(scored) -> {"slope_per_100_chars", "ci95"}` (OLS of `correct` on answer length, bootstrap interval).
- Prompts in `evals/prompts.py`: `KEY_FACTS` (question, key facts, answer → JSON `{"abstained": bool, "facts": [{"fact": str, "present": bool}]}`) and `SOURCE_SUPPORT` (key facts, cited source text → JSON `{"supported": bool, "missing": [str]}`). Cited source = text of the cited pages for v1, of the cited quotes' blocks for v2 (from the output's `claims`).

- [ ] **Step 1: Tests** (`FakeJudge` returning canned JSON):
  - `test_exact_match_normalisation`: `exact_match("The load factor is 3.80 times", "3.8")`, `("p14 8969", "P14-8969")` after dash/space normalisation, `("15 +/- 3 psi", "15 ± 3")` → True; `("13.8", "3.8")` → False.
  - `test_correct_needs_every_key_fact`: facts `[present, present]` → correct; `[present, absent]` → not correct.
  - `test_primary_needs_source_support`: correct + supported → primary True; correct + unsupported → primary False.
  - `test_abstention_scoring`: answerable + abstained → correct False, abstained True; unanswerable + abstained → correct True; unanswerable + answered → correct False (no judge call for facts).
  - `test_malformed_judge_output_is_judge_error`: judge returns `"not json"` or omits a fact → `judge_error` set, `correct` None; `summarize` excludes it and reports `judge_errors: 1`.
  - `test_exact_items_skip_the_judge_for_correctness`: an item with `exact_answer` is graded by `exact_match`; the judge is still asked for source support.
- [ ] **Step 2:** FAIL → implement → PASS (`pytest tests/evals -q`).
- [ ] **Step 3:** Commit `evals: key-fact grading, source support, length bias`.

### Task 5: Choose the judge

**Files:** create `evals/calibration/calib.jsonl`, `evals/calibration/README.md`, `evals/judge_select.py`, `docs/decisions/003-judge.md`.

**Interfaces — consumes:** `grade_item` (Task 4); v1 dev outputs (`evals/results/raw/v1.json`, repeat 0).

- [ ] **Step 1: Calibration labels.** 40 v1 answers on dev items (all categories, ≥ 8 unanswerable, mixed right/wrong), each labelled by Claude per key fact (`present`), `abstained` and `supported_in_source`, with a one-line reason. Provenance `labelled_by: "Claude"`; `README.md` states these are not human labels and that plan 7's blind session checks the chosen judge against Alexander.
- [ ] **Step 2: Candidates** (local, Ollama on the laptop's 16 GB GPU, none from the Qwen or Cohere families): `gpt-oss:20b` (Apache-2.0), `phi4:14b` (MIT), `gemma3:12b` (Gemma terms: use restrictions; note as a con), `mistral-small3.2:24b` (Apache-2.0; drop it if it does not fit in VRAM; check `api/ps` `size_vram`). Pin each model's digest.
- [ ] **Step 3:** `python -m evals.judge_select --calib evals/calibration/calib.jsonl --models …` reports per model: Cohen's kappa against the labels on per-fact presence, on item correctness and on source support; abstention agreement; JSON failure rate; length-bias slope; seconds per item. Rule: highest kappa on item correctness; ties (within 0.05) go to source-support kappa, then speed. A model with JSON failures > 5% is out.
- [ ] **Step 4:** Write decision 003 (table, the rule, the winner and its digest, cons and licence notes, the second-best kept as the "per judge" column); commit `evals: judge chosen (decision 003)`.

### Task 6: v1 and v1 at temperature 0, re-run and re-graded on dev

**Files:** modify `evals/run_eval.py` (v1 adapter `--v1-temperature FLOAT`, passed into the v1 app's generator options; recorded in the run config); create `evals/results/raw/v1-dev80.json`, `evals/results/raw/v1-t0-dev80.json`, scored files and `evals/results/NOTES.md` section "Re-graded with the new judge".

- [ ] **Step 1: Test** `test_v1_temperature_reaches_generator`: with a stubbed v1 app, `make_v1_adapter(..., temperature=0)` passes `temperature: 0` in the generator options; without the flag nothing is set (v1 as shipped).
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** On the laptop (v1 stores up, Command R7B in Ollama, sleep disabled): generate v1 as shipped and v1 at temperature 0 on the new dev set, 3 repeats each; grade with the chosen judge (`--grader keyfacts`) and with the second judge; record correctness, primary endpoint, abstention, judge errors and the spread across repeats. Cross-check 20 graded items with a Claude subagent, reported as an extra and labelled as such (spec, Grading).
- [ ] **Step 4:** Update NOTES.md (the old Qwen-graded numbers stay as history, labelled so); commit `evals: v1 and v1-t0 re-run and re-graded on dev`; push.

### Task 7: Gold-answer session and freeze

**Files:** create `evals/sessions/gold/index.html` (artifact source), `evals/sessions/gold_export.py`, `evals/gold_checks.jsonl`; modify `evals/test.jsonl` with confirmed corrections; tag `eval-test-frozen`.

- [ ] **Step 1: Sample** 60 test items, stratified by category (including ≥ 10 near-miss unanswerables), seeded; record the IDs.
- [ ] **Step 2: Build the session artifact** (load the `artifact-design` and `artifact-capabilities` skills first; private; shared database for results): one item per screen with the question, reference answer, key facts and anchors pre-filled, the gold page render(s) beside it (unanswerables: the section's pages); keys `y` correct, `e` edit (inline fields), `n` wrong (reason), `←/→` move; progress saved per item so the session can stop and resume; about 30–45 minutes.
- [ ] **Step 3:** Send Alexander the link and wait for him to finish (this is the only step that waits on him).
- [ ] **Step 4:** `gold_export.py` reads the artifact's database into `evals/gold_checks.jsonl` (item ID, verdict, edits, timestamp); apply edits to `evals/test.jsonl` with `provenance.edited_by = "Alexander"`; re-run `validate`; report the gold error rate (wrong + edited answers / checked) with a Wilson 95% interval in `evals/pool/README.md`.
- [ ] **Step 5:** Commit `evals: gold-answer session (60 items checked by Alexander)`; tag `eval-test-frozen`; push with the tag; dispatch the **M2 review** (fresh reviewer, most capable model) on the pool procedure, a random 30-item sample against the pages, the split, decision 003 and the v1 re-grade.
