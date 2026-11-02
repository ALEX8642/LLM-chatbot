from dataclasses import astuple
from pathlib import Path
from types import SimpleNamespace

import pytest

from manualqa.blocks import validate
from manualqa.ocr_detect import needs_ocr
from manualqa.parsers.docling_parser import docling_box_to_norm

MANUALS = Path(__file__).resolve().parents[2] / "manuals"


def bbox(left, t, r, b, origin):
    return SimpleNamespace(
        l=left, t=t, r=r, b=b, coord_origin=SimpleNamespace(value=origin)
    )


def test_docling_box_bottomleft():
    box = docling_box_to_norm(bbox(61.2, 712.8, 306, 633.6, "BOTTOMLEFT"), 612, 792)
    assert astuple(box) == pytest.approx((0.1, 0.1, 0.5, 0.2))


def test_docling_box_topleft():
    box = docling_box_to_norm(bbox(61.2, 79.2, 306, 158.4, "TOPLEFT"), 612, 792)
    assert astuple(box) == pytest.approx((0.1, 0.1, 0.5, 0.2))


def parse(manual, name, page):
    from manualqa.parsers import get_parser

    pdf = MANUALS / name
    decision = needs_ocr(manual(name)[page - 1])
    (pp,) = get_parser("docling").parse(pdf, [page], {page: decision})
    return pp


@pytest.mark.parsers
def test_docling_faa16_agrees_with_text_layer(manual):
    from evals.spike.metrics import coord_agreement, coord_offset
    from manualqa.parsers import get_parser

    name = "FAA_Weight_and_Balance_Handbook.pdf"
    pp = parse(manual, name, 16)
    assert validate(pp) == []
    (ref,) = get_parser("textlayer").parse(MANUALS / name, [16], {})
    ref_lines = [ln for b in ref.blocks for ln in b.lines]
    # glyph-tight boxes vs PyMuPDF's ascent/descent line boxes: IoU ~0.65 when correct
    assert coord_agreement(pp, ref_lines) >= 0.6
    assert coord_offset(pp, ref_lines) <= 0.005  # under half a text line


@pytest.mark.parsers
def test_docling_letter_spaced_page_is_ocrd(manual):
    pp = parse(manual, "Army_5kW_Generator_Operator_Manual.pdf", 51)
    assert pp.ocr is True
    assert any("exhaust" in b.text.lower() for b in pp.blocks)
