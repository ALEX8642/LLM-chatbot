import pytest

from evals.grade import (
    cited_source,
    exact_match,
    grade_item,
    length_bias,
    normalise,
    summarize_grades,
)
from evals.items import Item


class FakeJudge:
    """Canned replies by prompt marker, recording every call."""

    def __init__(self, facts=None, supported=True, abstained=False):
        self.facts, self.supported, self.abstained = facts, supported, abstained
        self.calls = []

    def ask(self, prompt):
        if "KEY FACTS CHECK" in prompt:
            self.calls.append("facts")
            if isinstance(self.facts, Exception):
                raise self.facts
            return {"abstained": self.abstained, "facts": self.facts}
        if "SOURCE CHECK" in prompt:
            self.calls.append("source")
            return {"supported": self.supported, "missing": []}
        self.calls.append("abstained")
        return {"abstained": self.abstained}


def item(**kw):
    base = dict(
        id="x",
        manual="m.pdf",
        sections=["s"],
        category="single_page",
        question="q?",
        gold_pages=[1],
        reference_answer="r",
        key_facts=["A", "B"],
        anchors=["a"],
    )
    base.update(kw)
    return Item(**base)


def out(answer="It is so.", **kw):
    return {"answer": answer, "cited_source": "the source", **kw}


@pytest.mark.parametrize(
    "answer,exact,want",
    [
        ("The load factor is 3.80 times its weight", "3.8", True),
        ("p14 8969", "P14-8969", True),
        ("The part number is P14‑8969.", "P14-8969", True),
        ("15 +/- 3 psi", "15 ± 3 psi", True),
        ("3050 pounds", "3,050 lb", True),
        ("13.8", "3.8", False),
        ("88-20243", "88-2024", False),
        ("about 12 months or so", "12 months", True),
    ],
)
def test_exact_match_normalisation(answer, exact, want):
    assert exact_match(answer, exact) is want


def test_normalise_is_idempotent():
    once = normalise("  Trip at 15 +/- 3.50 LBS. ")
    assert normalise(once) == once


def test_correct_needs_every_key_fact():
    yes = [{"fact": "A", "present": True}, {"fact": "B", "present": True}]
    no = [{"fact": "A", "present": True}, {"fact": "B", "present": False}]
    assert grade_item(item(), out(), FakeJudge(yes))["correct"] is True
    assert grade_item(item(), out(), FakeJudge(no))["correct"] is False


def test_primary_needs_source_support():
    yes = [{"fact": "A", "present": True}, {"fact": "B", "present": True}]
    g = grade_item(item(), out(), FakeJudge(yes, supported=True))
    assert g["correct"] and g["supported_in_source"] and g["primary"] is True
    g = grade_item(item(), out(), FakeJudge(yes, supported=False))
    assert g["correct"] and g["supported_in_source"] is False and g["primary"] is False


def test_abstention_scoring():
    no_facts = [{"fact": "A", "present": False}, {"fact": "B", "present": False}]
    g = grade_item(item(), out(abstained=True), FakeJudge(no_facts))
    assert g["correct"] is False and g["abstained"] is True and g["primary"] is False

    un = item(category="unanswerable", gold_pages=[], key_facts=[], near_miss=True)
    judge = FakeJudge()
    g = grade_item(un, out(abstained=True), judge)
    assert g["correct"] is True and g["primary"] is True
    g = grade_item(un, out(abstained=False), judge)
    assert g["correct"] is False and g["primary"] is False
    assert judge.calls == []  # the run recorded abstention, nothing to ask


def test_abstention_asked_when_the_system_does_not_record_it():
    un = item(category="unanswerable", gold_pages=[], key_facts=[], near_miss=True)
    judge = FakeJudge(abstained=True)
    assert grade_item(un, out(), judge)["correct"] is True
    assert judge.calls == ["abstained"]


def test_malformed_judge_output_is_judge_error():
    g = grade_item(item(), out(), FakeJudge(ValueError("judge returned no JSON")))
    assert g["judge_error"] and g["correct"] is None and g["primary"] is None
    skipped = [{"fact": "A", "present": True}]  # B was left out
    g = grade_item(item(), out(), FakeJudge(skipped))
    assert g["judge_error"] and g["correct"] is None
    s = summarize_grades([g, grade_item(item(id="y"), out(), FakeJudge(skipped))])
    assert s["judge_errors"] == 2 and s["n_graded"] == 0


def test_exact_items_skip_the_judge_for_correctness():
    it = item(exact_answer="P14-8969", key_facts=["P14-8969."])
    judge = FakeJudge()
    g = grade_item(it, out("The part is P14-8969."), judge)
    assert g["correct"] is True and judge.calls == ["source"]
    judge = FakeJudge()
    g = grade_item(it, out("The part is 18265."), judge)
    assert g["correct"] is False and g["primary"] is False


def test_summary_counts_primary_over_graded_items():
    yes = [{"fact": "A", "present": True}, {"fact": "B", "present": True}]
    no = [{"fact": "A", "present": False}, {"fact": "B", "present": True}]
    gs = [
        grade_item(item(id="a"), out(), FakeJudge(yes)),
        grade_item(item(id="b"), out(), FakeJudge(no)),
    ]
    s = summarize_grades(gs)
    assert s["correct"] == 0.5 and s["primary"] == 0.5 and s["n_graded"] == 2


def test_cited_source_uses_blocks_for_claims_and_pages_otherwise():
    blocks = {"m:p1:b0": "row table text", "m:p2:b1": "other block"}
    pages = {("m.pdf", 3): "page three"}
    v2 = {
        "claims": [{"block": "m:p1:b0:r20"}, {"block": "m:p2:b1"}],
        "cited_pages": [1],
    }
    assert cited_source(v2, "m.pdf", blocks, pages) == "row table text\nother block"
    v1 = {"cited_pages": [3]}
    assert cited_source(v1, "m.pdf", blocks, pages) == "page three"
    assert cited_source({"cited_pages": []}, "m.pdf", blocks, pages) == ""


def test_length_bias_finds_a_planted_slope():
    grades = [{"correct": n > 500, "answer_chars": n} for n in range(100, 1000, 10)]
    b = length_bias(grades)
    assert b["slope_per_100_chars"] > 0
    assert b["ci95"][0] > 0
    flat = [{"correct": i % 2 == 0, "answer_chars": 300} for i in range(50)]
    assert length_bias(flat)["slope_per_100_chars"] == 0.0
