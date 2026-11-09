import pytest


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
