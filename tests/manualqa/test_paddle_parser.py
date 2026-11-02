from pathlib import Path

import pytest

from manualqa.blocks import Cell, Line, validate
from manualqa.geometry import Box
from manualqa.ocr_detect import needs_ocr
from manualqa.parsers.paddle_parser import match_cell_boxes

MANUALS = Path(__file__).resolve().parents[2] / "manuals"


def test_match_cell_boxes_by_text_inside():
    cells = [Cell(0, 0, "P14-8969", None), Cell(0, 1, "18265", None)]
    boxes = [Box(0.5, 0.1, 0.6, 0.15), Box(0.1, 0.1, 0.2, 0.15)]
    lines = [
        Line("18265", Box(0.52, 0.11, 0.58, 0.14)),
        Line("P14-8969", Box(0.11, 0.11, 0.19, 0.14)),
    ]
    match_cell_boxes(cells, boxes, lines)
    assert cells[0].box == boxes[1] and cells[1].box == boxes[0]


def test_match_cell_boxes_leaves_unmatched_none():
    cells = [Cell(0, 0, "ROTOR ASSEMBLY", None), Cell(0, 1, "", None)]
    boxes = [Box(0.1, 0.1, 0.2, 0.15), Box(0.3, 0.1, 0.4, 0.15)]
    lines = [Line("something else", Box(0.11, 0.11, 0.19, 0.14))]
    match_cell_boxes(cells, boxes, lines)
    assert [c.box for c in cells] == [None, None]


def test_match_cell_boxes_uses_each_box_once():
    cells = [Cell(0, 0, "4", None), Cell(1, 0, "4", None)]
    boxes = [Box(0.1, 0.1, 0.2, 0.15), Box(0.1, 0.2, 0.2, 0.25)]
    lines = [
        Line("4", Box(0.12, 0.11, 0.18, 0.14)),
        Line("4", Box(0.12, 0.21, 0.18, 0.24)),
    ]
    match_cell_boxes(cells, boxes, lines)
    assert {cells[0].box, cells[1].box} == set(boxes)


def parse(manual, name, page):
    from manualqa.parsers import get_parser

    decision = needs_ocr(manual(name)[page - 1])
    (pp,) = get_parser("paddle").parse(MANUALS / name, [page], {page: decision})
    return pp


@pytest.mark.parsers
def test_paddle_faa16_agrees_with_text_layer(manual):
    from evals.spike.metrics import coord_agreement, coord_offset
    from manualqa.parsers import get_parser

    name = "FAA_Weight_and_Balance_Handbook.pdf"
    pp = parse(manual, name, 16)
    assert validate(pp) == []
    (ref,) = get_parser("textlayer").parse(MANUALS / name, [16], {})
    ref_lines = [ln for b in ref.blocks for ln in b.lines]
    assert coord_agreement(pp, ref_lines) >= 0.6
    assert coord_offset(pp, ref_lines) <= 0.005


@pytest.mark.parsers
def test_paddle_parts59_finds_part_number_cell(manual):
    from evals.spike.metrics import cell_checks

    name = "Army_5kW_Generator_Parts_Manual.pdf"
    pp = parse(manual, name, 59)
    check = {
        "manual": name,
        "page": 59,
        "value": "P14-8969",
        "match": "exact",
        "row_has": "18265",
    }
    assert cell_checks(pp, [check])[0]["passed"]
