from evals.retrieval_select import EMBEDDERS, RERANKERS, choose, page_metrics

SMALL_E, SMALL_R = "st:Qwen/Qwen3-Embedding-0.6B", "st:BAAI/bge-reranker-v2-m3"
BIG_E, BIG_R = "st:Qwen/Qwen3-Embedding-4B", "qwen:Qwen/Qwen3-Reranker-4B"


def test_a_small_gain_does_not_justify_a_larger_model():
    results = {(SMALL_E, SMALL_R): {"hit": 0.90}, (BIG_E, BIG_R): {"hit": 0.91}}
    assert choose(results) == (SMALL_E, SMALL_R)


def test_a_real_gain_does():
    results = {(SMALL_E, SMALL_R): {"hit": 0.90}, (BIG_E, BIG_R): {"hit": 0.93}}
    assert choose(results) == (BIG_E, BIG_R)


def test_all_candidates_have_a_size():
    assert len(EMBEDDERS) == 3 and len(RERANKERS) == 3


def test_page_metrics():
    assert page_metrics([3, 5, 7], [5]) == {"hit": 1.0, "rr": 0.5, "all": 1.0}
    assert page_metrics([3, 5], [5, 9]) == {"hit": 1.0, "rr": 0.5, "all": 0.0}
    assert page_metrics([3], [9]) == {"hit": 0.0, "rr": 0.0, "all": 0.0}
