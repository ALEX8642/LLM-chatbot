"""Score an Open WebUI raw file (evals/owui_run.py) with the grader of whatever checkout this
runs in, unchanged except that the cited source is the text of the chunks the answer cites
(docs/prereg-owui.md). Takes the same arguments as ``python -m evals.run_eval score``.

    python -m evals.owui_score RAW.json --qa FILE --composed COMPOSED.jsonl --out GRADED.json
"""

from __future__ import annotations

import sys

import evals.grade
import evals.run_eval

_original = evals.grade.cited_source


def cited_source(out: dict, manual: str, blocks: dict, pages: dict) -> str:
    if out.get("cited_text") is not None:
        return out["cited_text"]
    return _original(out, manual, blocks, pages)


if __name__ == "__main__":
    evals.grade.cited_source = cited_source
    sys.argv = [sys.argv[0], "score", *sys.argv[1:]]
    evals.run_eval.main()
