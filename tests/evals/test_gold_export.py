from evals.items import Item
from evals.sessions.gold_export import apply_checks, wilson


def item(id):
    return Item(
        id,
        "m.pdf",
        ["s"],
        "table",
        "q",
        [1],
        "r",
        ["f"],
        ["a"],
        provenance={"written_by": "Claude", "edited_by": None},
    )


def test_edits_applied_and_error_rate_counts_wrong_and_edited():
    items = [item("a"), item("b"), item("c"), item("d")]
    checks = [
        {"id": "a", "verdict": "correct"},
        {"id": "b", "verdict": "edited", "reference_answer": "new", "key_facts": ["n"]},
        {"id": "c", "verdict": "wrong", "reason": "bad"},
        {"id": "d", "verdict": "correct"},
    ]
    r = apply_checks(items, checks)
    assert items[1].reference_answer == "new" and items[1].key_facts == ["n"]
    assert items[1].provenance["edited_by"] == "Alexander"
    assert items[0].provenance["edited_by"] is None
    assert (
        items[2].reference_answer == "r"
    )  # a wrong item is flagged, not silently changed
    assert r["gold_error_rate"] == 0.5 and r["wrong"] == ["c"] and r["edited"] == ["b"]


def test_wilson_interval():
    low, high = wilson(3, 60)
    assert 0.01 < low < 0.05 and 0.09 < high < 0.15
    assert wilson(0, 60)[0] == 0.0 and 0 < wilson(0, 60)[1] < 0.07
