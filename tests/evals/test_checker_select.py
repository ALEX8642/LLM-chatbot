from evals.checker_select import metrics, pick_threshold


def rows(sup, uns):
    return [{"supported": True, "score": s} for s in sup] + [
        {"supported": False, "score": s} for s in uns
    ]


def test_threshold_stays_within_the_false_flag_budget():
    data = rows([0.9] * 19 + [0.4], [0.1, 0.5])
    assert pick_threshold(data) == 0.9  # one of 20 supported flagged is exactly 5%


def test_metrics():
    m = metrics(rows([0.9, 0.2], [0.1, 0.8]), 0.5)
    assert m["unsupported_caught"] == 1 and m["false_flags"] == 1
    assert m["recall"] == 0.5 and m["precision"] == 0.5


def test_binary_scores_pick_a_threshold_that_flags_no_on_a_good_checker():
    assert pick_threshold(rows([1.0] * 20, [0.0, 0.0])) == 1.0
