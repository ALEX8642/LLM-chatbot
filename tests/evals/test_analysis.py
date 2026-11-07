import pytest

from evals.analysis import (
    bootstrap_interval,
    clusters,
    compare,
    holm,
    item_scores,
    mcnemar_exact,
    minimum_detectable,
    taxonomy,
)
from evals.items import Item


def item(i, page, question="q?", category="table", section="s"):
    pages = [page] if page else []
    return Item(i, "m", [section], category, question, pages, "r")


def scored(*repeats):
    return {
        "repeats": [
            {"items": [{"id": i, "primary": v} for i, v in r.items()]} for r in repeats
        ]
    }


def test_exact_mcnemar_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 0) == pytest.approx(0.0625)
    assert mcnemar_exact(10, 2) == pytest.approx(0.03857, abs=1e-4)
    assert mcnemar_exact(3, 3) == 1.0


def test_item_score_is_the_majority_of_repeats():
    got = item_scores(
        scored(
            {"a": True, "b": True}, {"a": True, "b": False}, {"a": False, "b": False}
        )
    )
    assert got == {"a": True, "b": False}


def test_a_tie_fails_and_an_ungraded_repeat_does_not_vote():
    s = scored({"a": True}, {"a": False}, {"a": True})
    s["repeats"][2]["items"][0]["judge_error"] = "x"
    assert item_scores(s) == {"a": False}


def test_an_item_never_graded_is_absent():
    s = scored({"a": True})
    s["repeats"][0]["items"][0]["judge_error"] = "x"
    assert item_scores(s) == {}


def test_items_sharing_a_page_share_a_cluster():
    c = clusters([item("a", 1), item("b", 1), item("c", 2)])
    assert c["a"] == c["b"] != c["c"]


def test_part_number_questions_form_one_cluster_only_in_primary():
    items = [item("a", 1, "What is the part number?"), item("b", 2, "Its part number?")]
    assert clusters(items)["a"] == clusters(items)["b"]
    page = clusters(items, "page")
    assert page["a"] != page["b"]


def test_section_clusters_and_unanswerable_items_stand_alone():
    items = [
        item("a", 1, section="x"),
        item("b", 2, section="x"),
        item("u", None, category="unanswerable", section="y"),
    ]
    assert clusters(items, "section")["a"] == clusters(items, "section")["b"]
    primary = clusters(items)
    assert primary["u"] == "u"


def test_interval_holds_the_difference_and_clustering_shrinks_effective_n():
    diffs = {f"i{n}": int(n % 2 == 0) for n in range(100)}
    alone = {i: i for i in diffs}
    wide = bootstrap_interval(diffs, alone, n=2000)
    assert wide["low"] < 0.5 < wide["high"]
    assert wide["effective_n"] == pytest.approx(100, rel=0.2)
    joined = {f"i{n}": f"c{n // 10}" for n in range(100)}
    same = {f"i{n}": int(n // 10 % 2 == 0) for n in range(100)}
    assert bootstrap_interval(same, joined, n=2000)["effective_n"] < 30


def test_compare_counts_discordant_items_and_leaves_out_ungraded():
    a = {"x": True, "y": True, "z": False}
    b = {"x": False, "y": True, "z": True}
    c = {i: i for i in ["x", "y", "z", "w"]}
    got = compare(a, b, c)
    assert (got["a_only"], got["b_only"], got["n"], got["ungraded"]) == (1, 1, 3, 1)
    assert got["difference"] == 0


def test_minimum_detectable_falls_with_more_items():
    assert minimum_detectable(0.3, 100) > minimum_detectable(0.3, 400)
    assert minimum_detectable(0.3, 100) == pytest.approx(2.8 * (0.3 / 100) ** 0.5)


def test_holm():
    got = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert got == {
        "a": pytest.approx(0.03),
        "c": pytest.approx(0.06),
        "b": pytest.approx(0.06),
    }


def test_taxonomy_first_labels():
    table, none = item("a", 5), item("u", None, category="unanswerable")
    assert taxonomy({}, none, None) == "answered an unanswerable question"
    assert taxonomy({"abstained": True}, table, None) == "wrong abstention"
    assert taxonomy({"correct": True, "primary": False}, table, None) == "bad citation"
    assert taxonomy({}, table, {"ranked_pages": [9]}) == "not retrieved"
    assert taxonomy({}, table, {"ranked_pages": [5]}).startswith("wrong answer")
