# Item pool

One pool, written before any split, so the split cannot be shaped by what was written where.
`python -m evals.items validate evals/pool` checks every item against the parsed manuals.

## Procedure

Written by Claude from the composed text and page renders, section by section
(`evals/sections.json`), about one item per two pages where the pages allow it:

- **Answerable items** have 1-4 key facts and anchors: exact strings that must appear on a gold page.
- **Unanswerable items** are near misses: on the topic of a named section, asking for something the
  manual does not contain. Their anchors are terms an answer would need, checked absent from the whole
  manual. Absence of a phrase does not prove absence of the fact, so each is also reasoned in its
  reference answer, and the gold-answer session samples them.
- **Rows the parser garbled** (parts p55, p88) are avoided, and so is the fuel/oil chart on operator p56,
  where a reference answer could not be pinned from the text.
- **Facts repeated across sections** are asked once: the altitude derating, and Chapter 10's reruns of
  Chapter 3 and 7 examples, so one fact cannot sit in both dev and test.
- **Index items name the part number**, so one question does not tie a 56-page section to a parts group.

`legacy.jsonl` holds the 42 original dev items, with key facts and anchors added. The rest are
provenance `written_by: Claude`, not yet checked by a person; the gold-answer session covers a sample.

## Gold-answer check (2026-11-04)

Alexander reviewed the 60 sampled test items beside their pages and reported **no wrong answer**; he
notes he is not a subject expert, so an error could have been missed. He reported this in a message, and the
session page stored no per-item answers (`evals/sessions/gold_checks.jsonl` records that). The items
chosen, the marks on the pages and the reference answers were all pre-filled by Claude.

His flags found a defect in how items were written: on a continuation page the heading saying which
assembly or aircraft a table belongs to is on an earlier page, so the shown page cannot prove the answer.
A scan then found 28 such items, now carrying `context_pages` (for people checking; never scored). The scan
is a heuristic, and items were reviewed by hand against it, so a few may remain.

**Answer errors: 0 of 60** (Wilson 95% interval 0-6.0%), from a reviewer who is not a subject expert.
**Items whose shown page could not prove the answer: at least 4 of 60** by the scan (2.6-15.9%). Alexander
reports "quite a few", without a count, so the true number may be higher; the rule treats operator tables whose
rows name themselves as not needing context, and he may not agree. No item's answer was changed.

## Counts

| Manual | single_page | multi_page | table | figure | unanswerable | Total |
|---|---|---|---|---|---|---|
| FAA handbook | 67 | 5 | 31 | 5 | 28 | 136 |
| Operator manual | 46 | 5 | 38 | 8 | 22 | 119 |
| Parts manual | 8 | 4 | 56 | 1 | 20 | 89 |
| **All** | 121 | 14 | 125 | 14 | 70 | **344** |

Multi-page and figure items are few (14 and 14), because many figures in
these manuals are callout drawings with no readable value. The category results for them will be noisy.
