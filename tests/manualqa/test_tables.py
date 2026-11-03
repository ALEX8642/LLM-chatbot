import pytest

from manualqa.blocks import Block, Cell, PageParse
from manualqa.compose import compose_page
from manualqa.geometry import Box
from manualqa.tables import TableStore, derive_table

PARTS = "Army_5kW_Generator_Parts_Manual.pdf"


@pytest.fixture(scope="module")
def parts_pages(raw_pages, manual):
    return [
        compose_page(raw_pages[(PARTS, n)], manual(PARTS)[n - 1])
        for n in (58, 59, 60, 61)
    ]


@pytest.fixture
def store(tmp_path, parts_pages):
    s = TableStore(tmp_path / "tables.sqlite")
    for pp in parts_pages:
        s.add_page(pp)
    return s


def test_header_and_group_parts_p59(parts_pages):
    table = next(b for b in parts_pages[1].blocks if b.kind == "table")
    info = derive_table(table)
    assert any("part number" in label.lower() for label in info.header)
    item17 = next(c.row for c in table.cells if c.col == 0 and c.text == "17")
    group = next(g for r, g in sorted(info.groups.items()) if r <= item17)
    assert "FIG 15" in group


def test_lookup_by_item_in_figure(store):
    hits = store.lookup_table(columns={"item": "17"}, figure="15")
    assert len(hits) == 1
    assert "P14-8969" in hits[0].cells and "18265" in hits[0].cells
    assert hits[0].row_box is not None and hits[0].figure == "15"


def test_lookup_by_part_number(store):
    hits = store.lookup_table(query="P14-8969")
    assert hits and "P14-8969" in hits[0].cells


def test_lookup_returns_header_with_row(store):
    (hit,) = store.lookup_table(columns={"item": "16"}, figure="16")
    assert len(hit.header) == len(hit.cells) == len(hit.cell_boxes)
    assert "R28" in hit.cells and hit.page == 61


def test_no_hit_returns_empty(store):
    assert store.lookup_table(columns={"item": "999"}) == []


def synthetic_page(page, rows):
    cells = [
        Cell(r, c, t, None) for r, row in enumerate(rows) for c, t in enumerate(row)
    ]
    block = Block(f"m:p{page}:b0", "table", "", Box(0, 0, 1, 1), cells=cells)
    return PageParse("m.pdf", page, "test", 100, 100, 150, False, None, [block], 0.0)


def test_group_carries_across_pages(tmp_path):
    s = TableStore(tmp_path / "t.sqlite")
    s.add_page(
        synthetic_page(
            1,
            [
                ["ITEM", "PART NUMBER"],
                ["", "GROUP 01 FIG 4 ALTERNATOR ASSEMBLY"],
                ["1", "105-269"],
            ],
        )
    )
    s.add_page(synthetic_page(2, [["ITEM", "PART NUMBER"], ["2", "105-311"]]))
    (hit,) = s.lookup_table(query="105-311")
    assert hit.figure == "4" and hit.page == 2


def test_lookup_by_block_returns_all_rows_in_order(store, parts_pages):
    table = next(b for b in parts_pages[1].blocks if b.kind == "table")
    hits = store.lookup_table(block_id=table.id, limit=1000)
    assert [h.row for h in hits] == sorted(h.row for h in hits)
    assert len(hits) >= 18 and all(h.page == 59 for h in hits)
