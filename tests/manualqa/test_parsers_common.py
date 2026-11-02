from manualqa.blocks import Block, Line
from manualqa.geometry import Box
from manualqa.parsers.common import assign_lines


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
