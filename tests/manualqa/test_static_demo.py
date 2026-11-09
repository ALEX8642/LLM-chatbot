import json
from pathlib import Path

import pytest

from manualqa.static_demo import build, pages_used

ROOT = Path(__file__).resolve().parents[2]
PARTS = "Army_5kW_Generator_Parts_Manual.pdf"


def entry(question, history=(), pages=(59,), claim_page=58):
    events = [
        {"event": "retrieved", "data": {"pages": list(pages)}, "t": 0.0},
        {"event": "claim_settled", "data": {"page": claim_page}, "t": 1.0},
        {"event": "done", "data": {"pages": list(pages)}, "t": 2.0},
    ]
    return {
        "question": question,
        "manual": PARTS,
        "history": list(history),
        "events": events,
    }


def test_pages_used_takes_claim_pages_and_listed_pages():
    assert pages_used(entry("q")["events"]) == {58, 59}


def test_build_writes_answers_manuals_and_only_the_pages_shown(tmp_path):
    replay = tmp_path / "replay.jsonl"
    follow_up = entry("and?", history=[{"role": "user", "content": "q"}], pages=(3,))
    replay.write_text("\n".join(json.dumps(e) for e in [entry("q"), follow_up]))
    out = tmp_path / "site"
    assert build(replay, out, ROOT / "manuals") == {PARTS: [58, 59]}
    answers = json.loads((out / "answers.json").read_text())
    assert [a["question"] for a in answers] == ["q"] and "history" not in answers[0]
    (manual,) = json.loads((out / "manuals.json").read_text())
    assert manual["file"] == PARTS and manual["pages"] > 100
    stem = out / "pages" / "Army_5kW_Generator_Parts_Manual"
    assert sorted(p.name for p in stem.iterdir()) == ["p058.jpg", "p059.jpg"]


def test_a_manual_missing_from_sources_is_an_error(tmp_path):
    replay = tmp_path / "replay.jsonl"
    replay.write_text(json.dumps({**entry("q"), "manual": "Unknown.pdf"}))
    with pytest.raises(ValueError, match="Unknown.pdf"):
        build(replay, tmp_path / "site", ROOT / "manuals")
