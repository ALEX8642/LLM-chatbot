import json
from pathlib import Path

import pytest

from evals.items import Item, load_items, pages_text, section_of, validate

ROOT = Path(__file__).resolve().parents[2]
SECTIONS = json.loads((ROOT / "evals" / "sections.json").read_text())
COMPOSED = ROOT / "data" / "ingest" / "composed.jsonl"
PARTS = "Army_5kW_Generator_Parts_Manual.pdf"
OPER = "Army_5kW_Generator_Operator_Manual.pdf"

# a tiny stand-in for the composed text: parts p58/p59, operator p20/p70
TEXT = {
    (PARTS, 58): "FIGURE 15 AIR CLEANER ASSEMBLY",
    (PARTS, 59): "17 PAOZZ PAOZZ 18265 P14-8969 . . FILTER ELEMENT,INTA 1",
    (OPER, 20): "R a d i a t o r ( 9 ) . The radiator acts as a heat exchanger",
    (OPER, 70): "Shut down generator set.",
}


def item(**kw):
    base = dict(
        id="t-01",
        manual=PARTS,
        sections=["parts-g05"],
        category="table",
        question="What is the part number of item 17 in figure 15?",
        gold_pages=[59],
        reference_answer="P14-8969.",
        key_facts=["The part number is P14-8969."],
        anchors=["P14-8969"],
        exact_answer="P14-8969",
        near_miss=False,
        provenance={"written_by": "Claude", "edited_by": None, "date": "2026-11-03"},
    )
    base.update(kw)
    return Item(**base)


def test_sections_cover_every_page_once():
    pages = {}
    for line in (ROOT / "manuals" / "SOURCES.md").read_text().splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 3 and cols[0].endswith(".pdf`"):
            pages[cols[0].strip("`")] = int(cols[2])
    assert set(SECTIONS) == set(pages)
    for manual, secs in SECTIONS.items():
        expect = 1
        for s in secs:
            assert s["first"] == expect, (manual, s["id"])
            assert s["last"] >= s["first"]
            expect = s["last"] + 1
        assert expect == pages[manual] + 1, manual
    assert section_of(SECTIONS, PARTS, 59) == "parts-g05"


def test_valid_item_has_no_problems():
    assert validate([item()], SECTIONS, TEXT) == []


def test_sections_match_gold_pages():
    problems = validate(
        [item(gold_pages=[58, 59], sections=["parts-g04"])], SECTIONS, TEXT
    )
    assert any("parts-g05" in p for p in problems)


def test_anchor_must_be_on_a_gold_page():
    ok = item(gold_pages=[58, 59])
    assert validate([ok], SECTIONS, TEXT) == []
    bad = item(gold_pages=[58])
    assert any("P14-8969" in p for p in validate([bad], SECTIONS, TEXT))


def test_anchor_matches_letter_spaced_text():
    it = item(
        manual=OPER,
        sections=["op-1-2.1"],
        category="single_page",
        gold_pages=[20],
        anchors=["Radiator (9)", "heat exchanger"],
        exact_answer=None,
    )
    assert section_of(SECTIONS, OPER, 20) == "op-1-2.1"
    assert validate([it], SECTIONS, TEXT) == []


def test_unanswerable_anchor_must_be_absent():
    base = dict(
        category="unanswerable",
        gold_pages=[],
        key_facts=[],
        exact_answer=None,
        near_miss=True,
        reference_answer="The manual does not give it.",
    )
    assert validate([item(anchors=["torque"], **base)], SECTIONS, TEXT) == []
    problems = validate([item(anchors=["P14-8969"], **base)], SECTIONS, TEXT)
    assert any("P14-8969" in p for p in problems)
    problems = validate([item(anchors=["torque"], sections=[], **base)], SECTIONS, TEXT)
    assert any("section" in p for p in problems)


def test_answerable_needs_pages_and_one_to_four_key_facts():
    assert validate([item(gold_pages=[])], SECTIONS, TEXT)
    assert validate([item(key_facts=[])], SECTIONS, TEXT)
    assert validate([item(key_facts=["a", "b", "c", "d", "e"])], SECTIONS, TEXT)
    assert validate([item(category="opinion")], SECTIONS, TEXT)


def test_duplicate_ids_rejected():
    assert any("duplicate" in p for p in validate([item(), item()], SECTIONS, TEXT))


@pytest.mark.skipif(not COMPOSED.exists(), reason="needs data/ingest/composed.jsonl")
def test_legacy_items_valid():
    items = load_items(ROOT / "evals" / "pool" / "legacy.jsonl")
    assert len(items) == 42
    assert validate(items, SECTIONS, pages_text(COMPOSED)) == []
