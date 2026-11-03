from manualqa.geometry import Box
from manualqa.quotes import match_quote
from manualqa.retrieve import Evidence, row_evidence
from manualqa.tables import RowHit

LINES = [
    ("When the air-", Box(0.1, 0.10, 0.5, 0.12)),
    ("cleaner indicator shows red, service the", Box(0.1, 0.12, 0.5, 0.14)),
    ("element. Use only the ﬁlter specified.", Box(0.1, 0.14, 0.5, 0.16)),
    ("Unrelated closing sentence here.", Box(0.1, 0.16, 0.5, 0.18)),
]


def text_ev():
    text = "\n".join(t for t, _ in LINES)
    return Evidence(
        "m:p1:b0", "text", "m.pdf", 1, "m:p1:b0", text, [b for _, b in LINES]
    )


def test_exact_quote_gives_line_boxes():
    m = match_quote("indicator shows red, service the element", text_ev())
    assert m is not None and m.score >= 90
    assert m.boxes == [LINES[1][1], LINES[2][1]]


def test_quote_match_tolerates_extraction_noise():
    ev = text_ev()
    assert match_quote("When the air cleaner indicator shows red", ev)  # hyphenation
    assert match_quote("Use only the filter specified", ev)  # ligature
    assert match_quote("“Use only the filter specified.”", ev)  # curly quotes
    assert match_quote("U s e  o n l y  t h e  f i l t e r", ev)  # letter-spaced


def test_quote_from_other_block_fails():
    assert match_quote("Drain the fuel tank before storage", text_ev()) is None


def row():
    hit = RowHit(
        "parts:p59:b1",
        "parts.pdf",
        59,
        "parts:p59:b1",
        20,
        ["(1) ITEM NO", "(3) FSCM", "(4) PART NUMBER", "(5) DESCRIPTION"],
        ["17", "18265", "P14-8969", ". FILTER ELEMENT,INTA"],
        [
            Box(0.07, 0.5, 0.09, 0.51),
            Box(0.35, 0.5, 0.39, 0.51),
            Box(0.41, 0.5, 0.48, 0.51),
            Box(0.52, 0.5, 0.7, 0.51),
        ],
        None,
        "GROUP 05 FIG 15 AIR CLEANER",
        "15",
    )
    return row_evidence(hit)


def test_row_quote_gives_cell_boxes():
    ev = row()
    m = match_quote("P14-8969", ev)
    assert m is not None and m.boxes == [ev.cell_boxes[2]]
    m2 = match_quote("FSCM: 18265; (4) PART NUMBER: P14-8969", ev)
    assert m2 is not None and m2.boxes == [ev.cell_boxes[1], ev.cell_boxes[2]]


def test_short_quote_needs_exact():
    ev = row()
    assert match_quote("17", ev) is not None
    assert match_quote("71", ev) is None
