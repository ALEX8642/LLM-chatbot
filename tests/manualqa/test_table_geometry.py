from dataclasses import astuple

import pytest

from manualqa.blocks import Block, Cell, Line
from manualqa.compose import compose_page
from manualqa.geometry import Box
from manualqa.table_geometry import place_cells, row_boxes

H = 0.02  # line height
PARTS = "Army_5kW_Generator_Parts_Manual.pdf"


def line(text, col, vrow):
    x0, y0 = 0.1 + 0.2 * col, 0.1 + 0.03 * vrow
    return Line(text, Box(x0, y0, x0 + 0.15, y0 + H))


def table(rows):
    cells = [
        Cell(r, c, t, None) for r, row in enumerate(rows) for c, t in enumerate(row)
    ]
    return Block("t:p1:b0", "table", "", Box(0, 0, 1, 1), cells=cells)


def box_of(block, row, col):
    return next(c.box for c in block.cells if (c.row, c.col) == (row, col))


def test_place_cells_simple_grid():
    block = table([["1", "P14-8969", "FILTER"], ["2", "R28", "CAP"]])
    lines = [
        line(t, c, r)
        for r, row in enumerate([["1", "P14-8969", "FILTER"], ["2", "R28", "CAP"]])
        for c, t in enumerate(row)
    ]
    place_cells(block, lines)
    for ln, cell in zip(lines, sorted(block.cells, key=lambda c: (c.row, c.col))):
        assert cell.box == ln.box


def test_place_cells_repeated_values_stay_in_their_row():
    rows = [[str(i), "PAOZZ", "68505"] for i in (1, 2, 3)]
    block = table(rows)
    lines = [line(t, c, r) for r, row in enumerate(rows) for c, t in enumerate(row)]
    place_cells(block, lines)
    for r in range(3):
        for c in range(3):
            assert box_of(block, r, c) == line(rows[r][c], c, r).box


def test_place_cells_wrapped_description():
    block = table([["1", "HOSE,PREFORMED AIR FILTER"], ["2", "NUT"]])
    lines = [
        line("1", 0, 0),
        line("HOSE,PREFORMED AIR", 1, 0),
        line("FILTER", 1, 1),
        line("2", 0, 2),
        line("NUT", 1, 2),
    ]
    place_cells(block, lines)
    wrapped = box_of(block, 0, 1)
    assert wrapped.y0 == lines[1].box.y0 and wrapped.y1 == lines[2].box.y1
    assert box_of(block, 1, 1) == lines[4].box


def test_place_cells_missing_row_does_not_shift():
    rows = [["1", "68505"], ["2", "68505"], ["3", "68505"], ["4", "68505"]]
    block = table(rows)
    seen = [0, 1, 3]  # the OCR missed row 3 (index 2)
    lines = [line(t, c, v) for v, r in enumerate(seen) for c, t in enumerate(rows[r])]
    place_cells(block, lines)
    assert box_of(block, 2, 0) is None and box_of(block, 2, 1) is None
    assert box_of(block, 3, 1) == line("68505", 1, 2).box


def test_row_boxes_union():
    rows = [["1", "P14-8969"], ["2", "R28"]]
    block = table(rows)
    place_cells(
        block, [line(t, c, r) for r, row in enumerate(rows) for c, t in enumerate(row)]
    )
    boxes = row_boxes(block)
    assert astuple(boxes[0]) == pytest.approx((0.1, 0.1, 0.45, 0.1 + H))
    assert set(boxes) == {0, 1}


def test_parts_p59_rows(raw_pages, manual):
    pp = compose_page(raw_pages[(PARTS, 59)], manual(PARTS)[58])
    t = next(b for b in pp.blocks if b.kind == "table")
    part = next(c for c in t.cells if c.text == "P14-8969")
    cage = next(c for c in t.cells if c.row == part.row and c.text == "18265")
    assert part.box is not None and cage.box is not None
    assert abs(part.box.center[1] - cage.box.center[1]) < 0.005
    layer = next(ln for ln in t.lines if ln.text.strip() == "P14-8969")
    assert part.box.iou(layer.box) > 0.9


def test_short_token_of_a_split_cell_is_placed():
    b = table([["208 VOLTS", "L1"], ["120 VOLTS", "L3"]])
    place_cells(
        b,
        [
            line("208", 0, 0),
            line("VOLTS", 1, 0),
            line("L1", 2, 0),
            line("120", 0, 1),
            line("VOLTS", 1, 1),
            line("L3", 2, 1),
        ],
    )
    assert box_of(b, 0, 0).y0 == pytest.approx(0.1)
    assert box_of(b, 1, 0).y0 == pytest.approx(0.13)
    assert box_of(b, 1, 0).x1 > 0.4  # both words


def test_one_character_inside_a_longer_number_still_does_not_match():
    b = table([["68505", "x"]])
    place_cells(b, [line("5", 0, 0), line("x", 1, 0)])
    assert box_of(b, 0, 0) is None


def test_a_row_cannot_take_a_neighbour_with_the_same_words():
    # row 1's text also fits the lines of row 0, which row 0 has already used
    b = table([["L3-L1 3 PHASE", "208 VOLTS"], ["L3-L1 1PHASE", "240 VOLTS"]])
    place_cells(
        b,
        [
            line("L3-L1 3 PHASE", 0, 0),
            line("208 VOLTS", 1, 0),
            line("L3-L1 1PHASE", 0, 1),
            line("240 VOLTS", 1, 1),
        ],
    )
    assert box_of(b, 1, 1).y1 - box_of(b, 1, 1).y0 == pytest.approx(H)
    assert box_of(b, 1, 1).y0 == pytest.approx(0.13)


def test_a_different_digit_is_not_a_fuzzy_match():
    b = table([["L3-L1 1PHASE"]])
    place_cells(b, [line("L3-L1 3 PHASE", 0, 0)])
    assert box_of(b, 0, 0) is None


def test_a_line_is_used_once_in_a_row():
    b = table([["WASHER", "WASHER"]])
    place_cells(b, [line("WASHER", 0, 0), line("WASHER", 1, 0)])
    assert box_of(b, 0, 0).x0 == pytest.approx(0.1)
    assert box_of(b, 0, 1).x0 == pytest.approx(0.3)


def test_operator_p48_every_row_lands_on_its_own_line(manual):
    """Table 2-5, checked by hand against the page: the table the gold check flagged."""
    from pathlib import Path

    from manualqa.blocks import load_pages

    fixture = Path(__file__).parents[1] / "fixtures" / "paddle-raw-p48.jsonl"
    (raw,) = load_pages(fixture)
    composed = compose_page(raw, manual(raw.manual)[47])
    t = next(b for b in composed.blocks if b.kind == "table")
    cell = {c.text: c for c in t.cells if c.col == 0 or "PHASE" in c.text}
    # y-centres read from the page render, as a fraction of page height
    for text, y in [
        ("L1-L2 3 PHASE", 0.605),
        ("L2-L3 3 PHASE", 0.621),
        ("L3-L1 3 PHASE", 0.637),
        ("L3-LO 3 PHASE", 0.653),
        ("L3-LO 1PHASE", 0.675),
        ("L3-L1 1PHASE", 0.701),
        ("L3-LO 1 PHASE", 0.717),
        ("L1-LO 1 PHASE", 0.748),
    ]:
        assert cell[text].box is not None, text
        assert cell[text].box.center[1] == pytest.approx(y, abs=0.006), text
    volts = {(c.row): c for c in t.cells if "VOLTS" in c.text}
    assert volts[4].text == "120 VOLTS"
    assert volts[4].box.center[1] == pytest.approx(0.653, abs=0.006)
    assert volts[6].text == "240 VOLTS"
    assert volts[6].box.center[1] == pytest.approx(0.701, abs=0.006)


def test_a_line_merging_two_cells_still_fits_the_description():
    b = table([["CONNECTOR BODY, RECE", "1"]])
    place_cells(b, [line(". . . CONNECTOR BODY, RECE 1", 0, 0)])
    assert box_of(b, 0, 0) is not None
