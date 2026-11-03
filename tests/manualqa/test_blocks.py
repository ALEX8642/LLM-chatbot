from dataclasses import replace

import pytest

from manualqa.blocks import (
    Block,
    Cell,
    Line,
    PageParse,
    dump_pages,
    load_pages,
    validate,
)
from manualqa.geometry import Box


def make_page(blocks=None):
    if blocks is None:
        blocks = [
            Block(
                id="parts:p59:b0",
                kind="table",
                text="P14-8969 18265",
                box=Box(0.1, 0.2, 0.9, 0.6),
                cells=[
                    Cell(0, 0, "PART NUMBER", Box(0.1, 0.2, 0.5, 0.25), header=True),
                    Cell(1, 0, "P14-8969", Box(0.1, 0.25, 0.5, 0.3)),
                    Cell(1, 1, "18265", None),
                ],
            ),
            Block(
                id="parts:p59:b1",
                kind="text",
                text="Air cleaner",
                box=Box(0.1, 0.7, 0.5, 0.75),
                lines=[Line("Air cleaner", Box(0.1, 0.7, 0.5, 0.75))],
            ),
        ]
    return PageParse(
        manual="parts.pdf",
        page=59,
        parser="test",
        width_px=1275,
        height_px=1650,
        dpi=150,
        ocr=False,
        ocr_reason=None,
        blocks=blocks,
        seconds=0.5,
    )


def test_round_trip(tmp_path):
    pp = make_page()
    other = replace(
        make_page([]), page=60, ocr=True, ocr_reason="image_cover", error="E"
    )
    dump_pages([pp, other], tmp_path / "p.jsonl")
    assert load_pages(tmp_path / "p.jsonl") == [pp, other]


def test_validate_accepts_good_page():
    assert validate(make_page()) == []


BAD = [(Box(-0.1, 0, 0.5, 0.5), "outside"), (Box(0.6, 0, 0.5, 0.5), "x0 > x1")]


@pytest.mark.parametrize("bad,needle", BAD)
def test_validate_flags_bad_block_box(bad, needle):
    pp = make_page([Block("b0", "text", "x", bad)])
    problems = validate(pp)
    assert len(problems) == 1 and needle in problems[0]


@pytest.mark.parametrize("bad,needle", BAD)
def test_validate_flags_bad_line_box(bad, needle):
    pp = make_page([Block("b0", "text", "x", Box(0, 0, 1, 1), lines=[Line("x", bad)])])
    problems = validate(pp)
    assert len(problems) == 1 and needle in problems[0]


@pytest.mark.parametrize("bad,needle", BAD)
def test_validate_flags_bad_cell_box(bad, needle):
    pp = make_page(
        [Block("b0", "table", "x", Box(0, 0, 1, 1), cells=[Cell(0, 0, "x", bad)])]
    )
    problems = validate(pp)
    assert len(problems) == 1 and needle in problems[0]


def test_validate_flags_duplicate_ids():
    b = Block("b0", "text", "x", Box(0, 0, 1, 1))
    problems = validate(make_page([b, b]))
    assert len(problems) == 1 and "duplicate id" in problems[0]


def test_validate_flags_table_without_cells():
    problems = validate(make_page([Block("b0", "table", "x", Box(0, 0, 1, 1))]))
    assert len(problems) == 1 and "table without cells" in problems[0]


def test_load_pages_without_new_fields(tmp_path):
    pp = make_page()
    path = tmp_path / "old.jsonl"
    dump_pages([pp], path)
    old = path.read_text().replace(', "text_source": "ocr"', "")
    old = old.replace(', "alt_text": ""', "")
    assert "text_source" not in old and "alt_text" not in old
    path.write_text(old)
    (loaded,) = load_pages(path)
    assert loaded.text_source == "ocr" and loaded.blocks[0].alt_text == ""


def test_round_trip_new_fields(tmp_path):
    pp = replace(make_page(), text_source="text_layer")
    pp.blocks[1].alt_text = "Air cleaner (VL)"
    dump_pages([pp], tmp_path / "p.jsonl")
    assert load_pages(tmp_path / "p.jsonl") == [pp]
