import pytest

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


def test_caching_judge_asks_once_per_prompt(monkeypatch):
    from evals.run_eval import CachingJudge, Judge

    calls = []
    monkeypatch.setattr(Judge, "ask", lambda self, p: calls.append(p) or {"ok": p})
    judge = CachingJudge("u", "", "m")
    assert judge.ask("a") == judge.ask("a") == {"ok": "a"}
    judge.ask("b")
    assert calls == ["a", "b"]


def test_network_failures_become_a_judge_error_not_a_crash(monkeypatch):
    from types import SimpleNamespace

    import pytest

    from evals.run_eval import CachingJudge, Judge

    class Down(Exception):
        pass

    def down(self, prompt):
        raise Down

    monkeypatch.setattr(
        "evals.run_eval.requests", SimpleNamespace(RequestException=Down)
    )
    monkeypatch.setattr(Judge, "ask", down)
    monkeypatch.setattr("evals.run_eval.time.sleep", lambda s: None)
    with pytest.raises(ValueError, match="unreachable"):
        CachingJudge("u", "", "m").ask("a")


def test_grading_uses_the_token_limit_the_judge_was_selected_with():
    from evals.run_eval import CachingJudge

    assert CachingJudge("u", "", "m").max_tokens == 1500


@pytest.mark.parametrize(
    "reply,want",
    [
        ('{"supported": true}', {"supported": True}),
        (
            '```json\n{"supported": true}\n```\n\nBecause {x} and {y} hold.',
            {"supported": True},
        ),
        ('Sure: {"a": {"b": 1}} and also {"c": 2}', {"a": {"b": 1}}),
    ],
)
def test_first_json_object_is_read_and_later_text_ignored(reply, want):
    from evals.run_eval import first_json_object

    assert first_json_object(reply) == want


def test_no_json_object_gives_none():
    from evals.run_eval import first_json_object

    assert first_json_object("no object here") is None
    assert first_json_object("{broken") is None


def test_reuse_keeps_good_grades_and_retries_errors():
    from evals.run_eval import reusable_grades

    previous = {
        "repeats": [
            {
                "items": [
                    {
                        "id": "a",
                        "category": "table",
                        "correct": True,
                        "judge_error": None,
                    },
                    {
                        "id": "b",
                        "category": "table",
                        "correct": None,
                        "judge_error": "x",
                    },
                    {"id": "c", "category": "unanswerable", "judge_error": None},
                ]
            }
        ]
    }
    assert set(reusable_grades(previous)) == {(1, "a"), (1, "c")}
    assert set(reusable_grades(previous, "unanswerable")) == {(1, "a")}
