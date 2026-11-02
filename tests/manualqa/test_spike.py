import json
from pathlib import Path

import pytest

from evals.spike import run_spike
from evals.spike.metrics import cell_checks, coord_agreement, ocr_cer
from evals.spike.report import summarise
from manualqa import parsers
from manualqa.blocks import Block, Cell, Line, PageParse
from manualqa.geometry import Box

FAA = "FAA_Weight_and_Balance_Handbook.pdf"
MANUALS = Path(__file__).resolve().parents[2] / "manuals"


def page(blocks):
    return PageParse("m.pdf", 1, "test", 100, 100, 150, False, None, blocks, 0.0)


def text_page(lines):
    return page([Block("m:p1:b0", "text", "", Box(0, 0, 1, 1), lines=lines)])


REF = [
    Line("Weight and balance", Box(0.1, 0.1, 0.5, 0.15)),
    Line("Center of gravity", Box(0.1, 0.2, 0.5, 0.25)),
]


def test_coord_agreement_identical_lines_is_one():
    assert coord_agreement(text_page(REF), REF) == 1.0


def test_coord_agreement_no_text_match_is_none():
    other = [Line("Something else entirely", Box(0.1, 0.1, 0.5, 0.15))]
    assert coord_agreement(text_page(other), REF) is None


def test_coord_agreement_shifted_box():
    shifted = [Line(ln.text, Box(0.3, ln.box.y0, 0.7, ln.box.y1)) for ln in REF]
    assert coord_agreement(text_page(shifted), REF) == pytest.approx(1 / 3)


def test_ocr_cer_ignores_whitespace_and_case():
    pp = page([Block("m:p1:b0", "text", "T h i s  S E C T I O N", Box(0, 0, 1, 1))])
    assert ocr_cer(pp, "This section") == 0.0


def test_ocr_cer_empty_is_none():
    assert ocr_cer(page([]), "This section") is None


def table_page(rows):
    cells = [
        Cell(r, c, text, Box(0, 0, 0.1, 0.1) if c == 0 else None)
        for r, row in enumerate(rows)
        for c, text in enumerate(row)
    ]
    return page([Block("m:p1:b0", "table", "", Box(0, 0, 1, 1), cells=cells)])


def check(value, match="exact", row_has=None):
    return {
        "manual": "m.pdf",
        "page": 1,
        "value": value,
        "match": match,
        "row_has": row_has,
    }


def test_cell_check_exact_with_row():
    pp = table_page([["P14-8969", "18265"], ["R280", "78225"]])
    results = cell_checks(pp, [check("P14-8969", row_has="18265"), check("R28")])
    assert [r["passed"] for r in results] == [True, False]
    assert results[0]["cell_has_box"] is True


def test_cell_check_row_must_match():
    pp = table_page([["P14-8969", "99999"], ["X", "18265"]])
    assert not cell_checks(pp, [check("P14-8969", row_has="18265")])[0]["passed"]


def test_cell_check_contains_normalises():
    pp = table_page([["Trip pressure", "15 ± 3 PSI"]])
    assert cell_checks(pp, [check("15 ± 3 psi", match="contains")])[0]["passed"]


def test_cell_check_ignores_other_pages():
    pp = table_page([["P14-8969"]])
    other = dict(check("P14-8969"), page=2)
    assert cell_checks(pp, [other]) == []


def run(tmp_path, parser, pages):
    pages_file = tmp_path / "pages.json"
    pages_file.write_text(json.dumps({FAA: pages}))
    code = run_spike.main(
        [
            "--parser",
            parser,
            "--pages",
            str(pages_file),
            "--manuals",
            str(MANUALS),
            "--expectations",
            str(tmp_path / "none.json"),
            "--out",
            str(tmp_path / "out"),
            "--docs",
            str(tmp_path / "docs"),
        ]
    )
    assert code == 0
    return json.loads((tmp_path / "docs" / parser / "metrics.json").read_text())


def test_runner_textlayer_two_pages(tmp_path):
    metrics = run(tmp_path, "textlayer", [16, 1])
    lines = (tmp_path / "out/textlayer/parses.jsonl").read_text().splitlines()
    assert len(lines) == 2
    stem = Path(FAA).stem
    for n in (16, 1):
        assert (tmp_path / f"docs/textlayer/{stem}-p{n:03d}.jpg").exists()
    by_page = {p["page"]: p for p in metrics["pages"]}
    assert by_page[16]["coord_agreement"] == 1.0
    assert by_page[1]["ocr"] is True
    assert by_page[1]["coord_agreement"] is None


class Flaky:
    name = "flaky"

    def parse(self, pdf, pages, ocr):
        if pages == [16]:
            raise RuntimeError("boom")
        return parsers.get_parser("textlayer").parse(pdf, pages, ocr)


def test_runner_keeps_going_after_parser_error(tmp_path, monkeypatch):
    monkeypatch.setitem(parsers.PARSERS, "flaky", Flaky)
    metrics = run(tmp_path, "flaky", [16, 19])
    by_page = {p["page"]: p for p in metrics["pages"]}
    assert by_page[16]["error"] == "RuntimeError: boom"
    assert by_page[16]["blocks"] == 0
    assert by_page[19]["error"] is None and by_page[19]["blocks"] > 0
    table = summarise([metrics])
    row = next(ln for ln in table.splitlines() if ln.startswith("| flaky"))
    assert row.split("|")[3].strip() == "1"  # errors column
