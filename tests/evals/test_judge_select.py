from evals.items import Item
from evals.judge_select import cohen_kappa, evaluate, pick


def test_kappa_values():
    assert cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert cohen_kappa([1, 0, 1, 0], [0, 1, 0, 1]) == -1.0
    assert abs(cohen_kappa([1, 1, 1, 0], [1, 1, 0, 0]) - 0.5) < 1e-9
    assert cohen_kappa([1, 1], [1, 1]) == 1.0  # no variation, full agreement


def item(id, facts=("A",), category="single_page"):
    return Item(id, "m.pdf", ["s"], category, "q?", [1], "r", list(facts), ["a"])


def row(id, facts, abstained, supported, answer="ans"):
    return {
        "item": id,
        "system": "v1",
        "answer": answer,
        "cited_pages": [1],
        "claims": [],
        "labels": {"facts": facts, "abstained": abstained, "supported": supported},
    }


class Echo:
    """Agrees with the labels; fails on any answer containing BROKEN."""

    model = "echo"

    def __init__(self, truth):
        self.truth = truth

    def ask(self, prompt):
        if "BROKEN" in prompt:
            raise ValueError("no JSON")
        for key, labels in self.truth.items():
            if key in prompt:
                break
        if "KEY FACTS CHECK" in prompt:
            return {
                "abstained": labels["abstained"],
                "facts": [{"present": p} for p in labels["facts"]],
            }
        if "SOURCE CHECK" in prompt:
            return {"supported": labels["supported"]}
        return {"abstained": labels["abstained"]}


def test_evaluate_perfect_judge_and_counts_failures():
    items = {"a": item("a"), "b": item("b"), "u": item("u", (), "unanswerable")}
    rows = [
        row("a", [True], False, True, "answer-a"),
        row("b", [False], False, None, "answer-b"),
        row("u", [], True, None, "answer-u"),
        row("a", [True], False, True, "BROKEN"),
    ]
    truth = {f"answer-{r['item']}": r["labels"] for r in rows[:3]}
    truth["the source"] = rows[0]["labels"]
    got = evaluate(Echo(truth), rows, items, lambda r, i: "the source")
    assert got["kappa_correct"] == 1.0
    assert got["kappa_facts"] == 1.0
    assert got["json_failures"] == 1
    assert got["n"] == 4


def test_pick_follows_the_rule():
    a = {
        "model": "a",
        "kappa_correct": 0.80,
        "kappa_source": 0.5,
        "seconds_per_row": 9,
        "json_failure_rate": 0,
    }
    b = {
        "model": "b",
        "kappa_correct": 0.78,
        "kappa_source": 0.7,
        "seconds_per_row": 9,
        "json_failure_rate": 0,
    }
    c = {
        "model": "c",
        "kappa_correct": 0.95,
        "kappa_source": 0.9,
        "seconds_per_row": 1,
        "json_failure_rate": 0.2,
    }
    assert pick([a, b, c])["model"] == "b"  # c fails on JSON; a and b tie, b has source
    d = {**b, "model": "d", "kappa_source": 0.5, "seconds_per_row": 2}
    assert pick([a, d])["model"] == "d"  # tied twice, faster wins
