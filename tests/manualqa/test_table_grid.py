"""Rows rebuilt from a text layer's own grid. The values are read from the page by hand."""

from pathlib import Path

import pytest

from manualqa.blocks import Block, Cell, Line, load_pages
from manualqa.compose import compose_page
from manualqa.geometry import Box
from manualqa.table_grid import rebuild_from_grid

PARTS = "Army_5kW_Generator_Parts_Manual.pdf"
FIXTURE = Path(__file__).parents[1] / "fixtures" / "paddle-raw-parts-grid.jsonl"


@pytest.fixture(scope="module")
def pages(manual):
    raw = {pp.page: pp for pp in load_pages(FIXTURE)}
    return {n: compose_page(pp, manual(PARTS)[n - 1]) for n, pp in raw.items()}


def rows_of(page):
    b = next(x for x in page.blocks if x.kind == "table")
    rows = {}
    for c in b.cells:
        rows.setdefault(c.row, {})[c.col] = c
    return b, rows


def row_for(rows, item):
    return next(r for r in rows.values() if 0 in r and r[0].text == item)


def column(rows, label):
    header = rows[0]
    return next(i for i, c in header.items() if label in c.text)


def test_p25_item_keeps_its_own_part_number(pages):
    _, rows = rows_of(pages[25])
    pn, desc, fscm = (
        column(rows, "PART"),
        column(rows, "DESCRIPTION"),
        column(rows, "FSCM"),
    )
    r = row_for(rows, "35")
    assert r[pn].text == "88-20005" and "DOOR, OUTPUT" in r[desc].text
    assert r[fscm].text == "30554"
    assert row_for(rows, "36")[pn].text == "88-20245"
    assert row_for(rows, "48")[pn].text == "M24243/1A402"


def test_p25_cage_code_is_under_fscm_not_part_number(pages):
    _, rows = rows_of(pages[25])
    assert row_for(rows, "48")[column(rows, "FSCM")].text == "81349"


def test_wrapped_description_joins_its_row_with_a_taller_box(pages):
    _, rows = rows_of(pages[25])
    desc = column(rows, "DESCRIPTION")
    cell = row_for(rows, "40")[desc]
    assert "MAKE FROM" in cell.text and "HINGE" in cell.text
    next_item = row_for(rows, "41")[desc]
    assert cell.box.y1 <= next_item.box.y0


def test_p21_figure_4_item_51(pages):
    _, rows = rows_of(pages[21])
    r = row_for(rows, "51")
    assert r[column(rows, "PART")].text == "112-95"
    assert r[column(rows, "FSCM")].text == "68505"


def test_p40_heading_stays_out_of_the_data_rows(pages):
    _, rows = rows_of(pages[40])
    desc = column(rows, "DESCRIPTION")
    assert "FIG" in rows[1][desc].text and 0 not in rows[1]
    r = row_for(rows, "1")
    assert "WIRING HARNESS" in r[desc].text and "60HZ" in r[desc].text


def test_every_grid_cell_has_a_box(pages):
    for page in pages.values():
        b, _ = rows_of(page)
        assert all(c.box for c in b.cells if c.text.strip()), page.page


def line(text, x, y):
    return Line(text, Box(x, y, x + 0.08, y + 0.01))


def test_merged_part_and_description_are_split_and_share_the_line_box():
    b = Block("t", "table", "", Box(0, 0, 1, 1))
    lines = [
        *[
            line(t, x, 0.1)
            for t, x in [("NO", 0.1), ("PART", 0.3), ("DESCRIPTION", 0.5), ("QTY", 0.8)]
        ],
        *[
            line(t, x, 0.2)
            for t, x in [("1", 0.1), ("A-1", 0.3), ("BOLT", 0.5), ("2", 0.8)]
        ],
        *[
            line(t, x, 0.3)
            for t, x in [("2", 0.1), ("B1821 .SCREW,CAP", 0.3), ("3", 0.8)]
        ],
        *[
            line(t, x, 0.4)
            for t, x in [("3", 0.1), ("C-3", 0.3), ("NUT", 0.5), ("4", 0.8)]
        ],
    ]
    assert rebuild_from_grid(b, lines) is True
    row = {c.col: c.text for c in b.cells if c.row == 2}
    assert row == {0: "2", 1: "B1821", 2: ".SCREW,CAP", 3: "3"}


def test_a_table_without_a_grid_is_left_alone():
    b = Block("t", "table", "", Box(0, 0, 1, 1), cells=[Cell(0, 0, "kept", None)])
    lines = [line("free", 0.1, 0.1), line("text", 0.33, 0.2), line("here", 0.57, 0.3)]
    assert rebuild_from_grid(b, lines) is False
    assert b.cells[0].text == "kept"


def test_data_lines_off_the_grid_leave_the_table_alone():
    b = Block("t", "table", "", Box(0, 0, 1, 1), cells=[Cell(0, 0, "kept", None)])
    lines = [line(t, x, 0.1) for t, x in [("A", 0.1), ("B", 0.3), ("C", 0.5)]]
    for n, y in enumerate((0.2, 0.3, 0.4, 0.5)):
        lines += [line(str(n), 0.1, y), line("x", 0.2, y), line("y", 0.42, y)]
    assert rebuild_from_grid(b, lines) is False


def _grid_lines(first_col, rest):
    out = [line(t, x, 0.1) for t, x in [("A", 0.1), ("B", 0.3), ("C", 0.5)]]
    for n, (head, cells) in enumerate(zip(first_col, rest)):
        y = 0.2 + 0.1 * n
        out += [line(head, 0.1, y), line(cells[0], 0.3, y), line(cells[1], 0.5, y)]
    return out


def test_a_numeric_table_stays_with_the_parser():
    b = Block("t", "table", "", Box(0, 0, 1, 1), cells=[Cell(0, 0, "kept", None)])
    lines = _grid_lines(["0", "2,000", "4,000"], [("29.92", "15.0")] * 3)
    assert rebuild_from_grid(b, lines) is False


def test_a_table_without_numbered_rows_stays_with_the_parser():
    b = Block("t", "table", "", Box(0, 0, 1, 1), cells=[Cell(0, 0, "kept", None)])
    lines = _grid_lines(["Weight A", "Weight B", "Weight C"], [("100", "BOLT")] * 3)
    assert rebuild_from_grid(b, lines) is False


def test_dotted_description_is_not_a_merged_code():
    b = Block("t", "table", "", Box(0, 0, 1, 1))
    lines = _grid_lines(["1", "2", "3"], [("A-1", ". . WIRING HARNESS")] * 3)
    assert rebuild_from_grid(b, lines) is True
    assert {c.text for c in b.cells if c.row == 1 and c.col == 2} == {
        ". . WIRING HARNESS"
    }


def test_decimal_inside_a_description_is_not_a_merged_code():
    b = Block("t", "table", "", Box(0, 0, 1, 1))
    lines = _grid_lines(["1", "2", "3"], [("A-1", "WASHER .625 OD")] * 3)
    assert rebuild_from_grid(b, lines) is True
    assert {c.text for c in b.cells if c.row == 1 and c.col == 2} == {"WASHER .625 OD"}
