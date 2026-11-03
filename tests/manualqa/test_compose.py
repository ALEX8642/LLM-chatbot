from manualqa.blocks import validate
from manualqa.compose import compose_page
from manualqa.geometry import render_page
from manualqa.parsers.textlayer import text_layer_lines
from manualqa.textclean import clean_ocr_text

FAA = "FAA_Weight_and_Balance_Handbook.pdf"
OP = "Army_5kW_Generator_Operator_Manual.pdf"


def composed(raw_pages, manual, name, page):
    return compose_page(raw_pages[(name, page)], manual(name)[page - 1])


def test_trusted_page_uses_text_layer_lines(raw_pages, manual):
    pp = composed(raw_pages, manual, FAA, 16)
    assert pp.text_source == "text_layer"
    page = manual(FAA)[15]
    _, frame = render_page(page)
    layer = {ln.text for ln in text_layer_lines(page, frame)}
    lines = [ln for b in pp.blocks for ln in b.lines]
    assert lines and all(ln.text in layer for ln in lines)


def test_flagged_page_keeps_ocr_lines(raw_pages, manual):
    pp = composed(raw_pages, manual, OP, 51)
    assert pp.text_source == "ocr"
    assert any("exhaust" in b.text.lower() for b in pp.blocks)


def test_block_text_is_its_lines(raw_pages, manual):
    for name, page in ((FAA, 16), (OP, 51)):
        for b in composed(raw_pages, manual, name, page).blocks:
            if b.kind != "table":
                assert b.text == "\n".join(ln.text for ln in b.lines)


def test_alt_text_keeps_parser_text(raw_pages, manual):
    raw = raw_pages[(FAA, 16)]
    pp = composed(raw_pages, manual, FAA, 16)
    raw_heading = next(b for b in raw.blocks if b.kind == "heading")
    heading = next(b for b in pp.blocks if b.box == raw_heading.box)
    assert heading.alt_text == clean_ocr_text(raw_heading.text)
    assert "Responsibility" in heading.text


def test_composed_pages_validate(raw_pages, manual):
    for (name, page), raw in raw_pages.items():
        pp = compose_page(raw, manual(name)[page - 1])
        assert validate(pp) == []
        assert [b.id for b in pp.blocks] == [
            f"{name.removesuffix('.pdf')}:p{page}:b{i}" for i in range(len(pp.blocks))
        ]
