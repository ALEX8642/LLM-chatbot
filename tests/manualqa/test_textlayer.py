from pathlib import Path

from manualqa.blocks import validate
from manualqa.ocr_detect import needs_ocr
from manualqa.parsers import get_parser

FAA = (
    Path(__file__).resolve().parents[2] / "manuals/FAA_Weight_and_Balance_Handbook.pdf"
)


def parse_faa(manual, pages):
    doc = manual(FAA.name)
    ocr = {p: needs_ocr(doc[p - 1]) for p in pages}
    return get_parser("textlayer").parse(FAA, pages, ocr)


def test_textlayer_finds_known_line(manual):
    (pp,) = parse_faa(manual, [16])
    lines = [ln for b in pp.blocks for ln in b.lines]
    hits = [
        ln
        for ln in lines
        if "aircraft can perform safely" in " ".join(ln.text.lower().split())
    ]
    assert hits and hits[0].box.y1 < 0.5


def test_textlayer_pages_validate(manual):
    pages = parse_faa(manual, [16, 28])
    assert [pp.page for pp in pages] == [16, 28]
    for pp in pages:
        assert validate(pp) == []
        assert (pp.manual, pp.parser) == (FAA.name, "textlayer")
        assert pp.blocks and pp.blocks[0].id == f"{FAA.stem}:p{pp.page}:b0"
