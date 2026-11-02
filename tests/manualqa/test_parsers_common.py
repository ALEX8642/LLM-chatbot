from manualqa.blocks import Block, Line
from manualqa.geometry import Box
from manualqa.parsers.common import assign_lines, html_table_cells


def block(id, box):
    return Block(id, "text", "", box)


def test_assign_lines_by_centre():
    a = block("a", Box(0, 0, 0.5, 0.5))
    inside = Line("in", Box(0.1, 0.1, 0.3, 0.2))
    outside = Line("out", Box(0.6, 0.6, 0.9, 0.7))
    orphans = assign_lines([a], [inside, outside])
    assert a.lines == [inside] and orphans == [outside]


def test_assign_lines_centre_decides_not_overlap():
    a = block("a", Box(0, 0, 0.5, 0.5))
    straddling = Line("x", Box(0.4, 0.1, 0.8, 0.2))  # centre 0.6 is outside a
    assert assign_lines([a], [straddling]) == [straddling] and a.lines == []


def test_assign_lines_prefers_smallest_block():
    outer = block("outer", Box(0, 0, 1, 1))
    inner = block("inner", Box(0.1, 0.1, 0.4, 0.4))
    line = Line("x", Box(0.15, 0.15, 0.3, 0.2))
    assign_lines([outer, inner], [line])
    assert inner.lines == [line] and outer.lines == []


def test_html_table_cells_spans():
    cells = html_table_cells(
        "<table><tr><th colspan=2>A</th><th>B</th></tr>"
        "<tr><td rowspan=2>x</td><td>y</td><td>z</td></tr>"
        "<tr><td>w</td><td>v</td></tr></table>"
    )
    assert [(c.row, c.col, c.text, c.header) for c in cells] == [
        (0, 0, "A", True),
        (0, 2, "B", True),
        (1, 0, "x", False),
        (1, 1, "y", False),
        (1, 2, "z", False),
        (2, 1, "w", False),
        (2, 2, "v", False),
    ]
    assert all(c.box is None for c in cells)


def test_html_table_cells_thead_and_whitespace():
    cells = html_table_cells(
        "<html><body><table><thead><tr><td> PART <br/>NUMBER </td></tr></thead>"
        "<tbody><tr><td>P14-8969</td></tr></tbody></table></body></html>"
    )
    assert [(c.row, c.text, c.header) for c in cells] == [
        (0, "PART NUMBER", True),
        (1, "P14-8969", False),
    ]


def test_html_table_cells_empty():
    assert html_table_cells("") == []
