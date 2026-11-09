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


def _text(text):
    return Evidence("e", "text", "m", 1, "e", text, [Box(0, 0, 1, 1)])


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


def test_quote_with_ellipsis_matches_each_fragment():
    ev = Evidence(
        "m:p1:b0",
        "text",
        "m.pdf",
        1,
        "m:p1:b0",
        "The datum is located on the firewall of this airplane. It is 100 inches ahead.",
        [Box(0, 0, 1, 1)],
    )
    m = match_quote("The datum is located ... It is 100 inches ahead.", ev)
    assert m is not None
    assert (
        match_quote("The datum is located ... It is 500 miles behind us.", ev) is None
    )


def test_source_is_what_the_quote_matched_not_the_quote():
    ev = _text("Replace with kit 88-20243 when worn")
    m = match_quote("Replace with kit 88-20244 when worn", ev)
    assert m is not None and "88-20243" in m.source and "88-20244" not in m.source


def test_source_reaches_whole_words():
    ev = _text("The relief valve opens at 1250 psi on the bench")
    m = match_quote("relief valve opens at 125", ev)
    assert m is None or "1250" in m.source


def test_ellipsis_fragments_must_be_in_order():
    ev = _text("Remove the filter first. Then clean the housing thoroughly.")
    assert match_quote("Remove the filter ... clean the housing", ev) is not None
    assert match_quote("clean the housing ... Remove the filter", ev) is None


def test_ellipsis_cannot_skip_a_negation():
    ev = _text("Do not operate the generator without a ground rod installed.")
    assert match_quote("Do ... operate the generator", ev) is None
    assert match_quote("Do not operate ... a ground rod installed", ev) is None


def test_ellipsis_source_holds_only_the_fragments():
    ev = _text("Torque is 10 ft-lb. Gap is 3 mm. Pressure is 25 psi.")
    m = match_quote("Torque is 10 ft-lb ... Pressure is 25 psi", ev)
    assert m is not None and "3 mm" not in m.source and "25 psi" in m.source


def test_blank_lines_do_not_shift_the_boxes():
    a, b = Box(0, 0, 1, 0.1), Box(0, 0.5, 1, 0.6)
    ev = Evidence("e", "text", "m", 1, "e", "first line\n\nsecond line", [a, b])
    assert match_quote("second line", ev).boxes == [b]


def test_row_quote_can_be_its_values_without_the_column_names():
    hit = RowHit(
        "t",
        "m.pdf",
        23,
        "t",
        3,
        ["Item", "Spec"],
        ["Lubricating System Capacity", "3.2 qts. (3.0 liters)"],
        [Box(0, 0, 1, 0.1), Box(0, 0.1, 1, 0.2)],
        None,
        None,
        None,
    )
    ev = row_evidence(hit)
    m = match_quote("Lubricating System Capacity 3.2 qts. (3.0 liters)", ev)
    assert m is not None and len(m.boxes) == 2 and "3.2" in m.source


def test_a_values_only_row_match_reports_its_span_in_the_displayed_row():
    hit = RowHit(
        "t",
        "m.pdf",
        23,
        "t",
        3,
        ["Item", "Spec"],
        ["Lubricating System Capacity", "3.2 qts. (3.0 liters)"],
        [Box(0, 0, 1, 0.1), Box(0, 0.1, 1, 0.2)],
        None,
        None,
        None,
    )
    ev = row_evidence(hit)
    m = match_quote("Lubricating System Capacity 3.2 qts.", ev)
    assert m is not None
    assert ev.text[m.span[0] : m.span[1]].startswith("Lubricating")
    assert "3.2" in ev.text[m.span[0] : m.span[1]]
