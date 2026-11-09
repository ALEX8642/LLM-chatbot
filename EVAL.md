# How v2 was evaluated

The result is in the [README](README.md); every number below links to where it was produced. Dev results:
[`evals/results/NOTES-v2-dev.md`](evals/results/NOTES-v2-dev.md). Test results: [`evals/results/TEST.md`](evals/results/TEST.md).

## The question

Does v2 give more answers that are correct **and** supported by what they cite than v1, on questions not used to build it?
The design ([spec](docs/superpowers/specs/2026-11-01-v2-design.md)) set this before any v2 code existed.

## Items

- **Three public manuals** (FAA handbook; Army generator operator and parts manuals), [`manuals/SOURCES.md`](manuals/SOURCES.md).
- **Written by Claude** from the pages, each tied to its source mechanically: answerable items carry exact strings that
  must appear on a gold page; unanswerable items carry terms checked absent from the whole manual. Near-misses ask for
  something plausible the manual lacks. [`evals/pool/README.md`](evals/pool/README.md).
- **Split by manual section,** so no test item's gold page lies in a dev section: 172 dev, 169 test, the test set frozen
  at tag `eval-test-frozen` before any system saw it.
- **Gold check:** Alexander, not a subject expert, checked 60 test items' answers and key facts before the freeze, and
  found at least 4 needed context from another page.

## Grading

- **Judge:** `phi4:14b`, run locally, from a family no compared system uses (decision
  [003](docs/decisions/003-judge.md)); `mistral-small3.2:24b` as a second judge. No paid APIs.
- **Key facts, not impressions:** each item has 1–4 key facts. The judge checks each fact against the answer, then
  against the source the answer cites.
- **Primary endpoint:** correct, with its key facts in the cited source (v1: its cited pages; v2: its cited blocks). An
  unanswerable item passes when the system declines.

## Registration

Before the test run, [`docs/prereg.md`](docs/prereg.md) fixed the endpoint, the contrast (v2 against v1), the judge, 3
repeats with a majority score, the tests (exact McNemar and a clustered paired bootstrap, both required), the secondary
contrasts, the exploratory list and the analysis code ([`evals/analysis.py`](evals/analysis.py)), and was tagged `prereg`.

## Checks after the run

- **Blind human grading:** 100 answers from 50 items, both systems, identity hidden, order shuffled
  ([`evals/sessions/blind_grades.jsonl`](evals/sessions/blind_grades.jsonl)). It triggered the registered judge-validity
  warning: the judge misses support in v1's whole-page citations more often than in v2's. Details and an estimate
  allowing for it are in [`TEST.md`](evals/results/TEST.md).
- **Misses:** every v2 failure labelled ([`v2-misses.jsonl`](evals/results/test/v2-misses.jsonl)).
- **Public benchmark:** v2's retrieval on ViDoRe V3's industrial manuals, NDCG@10, with its standing at the time checked
  ([decision 005](docs/decisions/005-external-benchmark.md)).

## Deviations

- v2's first test attempt hung with a GPU driver event and was rerun whole, as registered.
- After the run, v2's search was changed to keep its index open (speed only); the registered results come from the code
  at `prereg`.

## What this does not show

- Any manual neither system was tuned near: test and dev share manuals.
- Expert agreement: the human checks are by one non-expert.
- Answer quality on a public benchmark: the published answer scores use a paid judge.
- That the meaning check helps: it removed nothing on test.
- Independence of authorship: Claude wrote the items, the code and the labels; the registration, the split and the human
  checks are the guard against that.

## Reproducing

Raw generations and judge outputs are committed (`evals/results/raw/`, `evals/results/test/`), so the analysis re-runs
without GPUs: `python -m evals.analysis --items evals/test.jsonl --a evals/results/test/v2-test-phi4.json --b
evals/results/test/v1-test-phi4.json`. Regenerating needs a 16 GB GPU for retrieval and an OpenAI-compatible endpoint
for the generator.
