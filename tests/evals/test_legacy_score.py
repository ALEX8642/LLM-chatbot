from evals.run_eval import score_item, summarize


class BrokenJudge:
    """Answers correctness, then rambles instead of JSON for faithfulness."""

    def ask(self, prompt):
        if "faithful" in prompt.lower() and "correctness" not in prompt.lower():
            raise ValueError("judge returned no JSON: 'The assistant...'")
        return {"correctness": "correct", "abstained": False, "reason": "ok"}


class SilentJudge:
    def ask(self, prompt):
        raise ValueError("judge returned no JSON: ''")


GOLD = {
    "category": "table",
    "manual": "m.pdf",
    "gold_pages": [3],
    "question": "q",
    "reference_answer": "r",
}
ITEM = {
    "id": "x",
    "answer": "It is 5.",
    "ranked_pages": [3],
    "candidate_pages": [3],
    "cited_pages": [3],
    "context": "c",
    "timings": {"total_s": 1.0},
}


def test_judge_failure_is_recorded_not_raised():
    s = score_item(dict(ITEM), GOLD, BrokenJudge())
    assert s["correctness"] == "correct"
    assert "faithfulness" not in s
    assert s["judge_error"].startswith("judge returned no JSON")


def test_judge_error_items_left_out_of_correctness():
    ok = score_item(dict(ITEM), GOLD, BrokenJudge())
    bad = score_item(dict(ITEM, id="y"), GOLD, SilentJudge())
    assert bad["correctness"] is None and bad["judge_error"]
    out = summarize([ok, bad])
    assert out["correctness"] == 1.0  # the unjudged item is not counted as wrong
    assert out["judge_errors"] == 2
