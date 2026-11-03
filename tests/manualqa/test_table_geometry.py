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
