from pathlib import Path

from evals.spike.run_spike import _page_list

ROOT = Path(__file__).resolve().parents[2]


def test_all_lists_every_page_of_every_manual():
    pages = _page_list(Path("all"), ROOT / "manuals")
    assert len(pages) == 3 and sum(len(v) for v in pages.values()) == 363
    assert all(v[0] == 1 and v == list(range(1, len(v) + 1)) for v in pages.values())
