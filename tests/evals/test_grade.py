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
        ("**88-21063**", "88-21063", True),
        ("`P14-8969`", "P14-8969", True),
        ("It is at 27.4% MAC", "27.4", True),
        ("about 76.0-pound", "76", True),
        ("P15121-37", "37", False),
        ("88-21063-1", "88-21063", False),
        ("88-20260-34", "88-20260", False),
        ("8.0%", "8", True),
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
    g = grade_item(item(), out(), FakeJudge(no_facts, abstained=True))
    assert g["correct"] is False and g["abstained"] is True and g["primary"] is False

    un = item(category="unanswerable", gold_pages=[], key_facts=[], near_miss=True)
    g = grade_item(un, out(), FakeJudge(abstained=True))
    assert g["correct"] is True and g["primary"] is True
    g = grade_item(un, out(), FakeJudge(abstained=False))
    assert g["correct"] is False and g["primary"] is False


def test_judge_decides_abstention_for_every_system_and_recorded_is_kept():
    un = item(category="unanswerable", gold_pages=[], key_facts=[], near_miss=True)
    judge = FakeJudge(abstained=True)
    g = grade_item(un, out("It does not state this.", abstained=False), judge)
    assert g["abstained"] is True and g["correct"] is True
    assert g["recorded_abstained"] is False and judge.calls == ["abstained"]
    g = grade_item(un, out("It does not state this."), FakeJudge(abstained=True))
    assert g["recorded_abstained"] is None

    no_facts = [{"fact": "A", "present": True}, {"fact": "B", "present": True}]
    g = grade_item(item(), out(abstained=True), FakeJudge(no_facts, abstained=False))
    assert (
        g["abstained"] is False and g["correct"] is True
    )  # recorded does not override


def test_a_failed_exact_match_asks_the_judge_about_abstention():
    it = item(exact_answer="P14-8969", key_facts=["P14-8969."])
    judge = FakeJudge(abstained=True)
    g = grade_item(it, out("The manual does not say."), judge)
    assert g["abstained"] is True and judge.calls == ["abstained"]


def test_v2_page_level_source_is_a_separate_sensitivity():
    yes = [{"fact": "A", "present": True}, {"fact": "B", "present": True}]
    judge = FakeJudge(yes, supported=True)
    g = grade_item(item(), out(page_source="pages"), judge)
    assert g["supported_in_pages"] is True and judge.calls == [
        "facts",
        "source",
        "source",
    ]
    g = grade_item(item(), out(), FakeJudge(yes, supported=True))
    assert g["supported_in_pages"] is True  # v1 cites pages, so the same answer
    s = summarize_grades([g])
    assert s["primary_pages"] == 1.0


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
    pages[("m.pdf", 4)] = "page four"
    twice = {"cited_pages": [3, 3, 4, 3]}
    assert cited_source(twice, "m.pdf", blocks, pages) == "page three\npage four"


def test_length_bias_finds_a_planted_slope():
    grades = [{"correct": n > 500, "answer_chars": n} for n in range(100, 1000, 10)]
    b = length_bias(grades)
    assert b["slope_per_100_chars"] > 0
    assert b["ci95"][0] > 0
    flat = [{"correct": i % 2 == 0, "answer_chars": 300} for i in range(50)]
    assert length_bias(flat)["slope_per_100_chars"] == 0.0


def test_a_reply_with_the_wrong_fact_count_is_asked_again():
    class Recount(FakeJudge):
        def ask(self, prompt):
            if "KEY FACTS CHECK" in prompt and "exactly 2 entries" in prompt:
                self.calls.append("recount")
                return {"abstained": False, "facts": [{"present": True}] * 2}
            return super().ask(prompt)

    judge = Recount([{"fact": "A and B", "present": True}])
    g = grade_item(item(), out(), judge)
    assert g["correct"] is True and judge.calls[:2] == ["facts", "recount"]


def test_a_long_source_is_checked_fact_by_fact_on_its_nearest_passages():
    from evals.grade import PASSAGE_CHARS, SUPPORT_CHARS, passages

    filler = [f"line {i} about gaskets and grooves." for i in range(400)]
    lines = filler[:150] + ["The relay alarms within 2 to 3 months."] + filler[150:]
    source = "\n".join(lines)
    assert len(source) > SUPPORT_CHARS
    got = passages(source, "An alarm within 2 to 3 months is expected.", "")
    assert "within 2 to 3 months" in got and len(got) < 4 * PASSAGE_CHARS

    seen = []

    class Reader(FakeJudge):
        def ask(self, prompt):
            if "SOURCE CHECK" in prompt:
                seen.append(prompt)
            return super().ask(prompt)

    yes = [{"fact": "A", "present": True}, {"fact": "B", "present": True}]
    grade_item(item(), out(cited_source=source), Reader(yes))
    assert len(seen) == 2 and all(len(p) < len(source) for p in seen)
    seen.clear()
    grade_item(item(), out(cited_source="short source"), Reader(yes))
    assert len(seen) == 1  # a short source is asked about once, as in prompt version 2
