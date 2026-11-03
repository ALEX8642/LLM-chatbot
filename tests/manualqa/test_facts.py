from manualqa.facts import check_facts
from manualqa.geometry import Box
from manualqa.retrieve import Evidence, row_evidence
from manualqa.tables import RowHit


def text_ev(text):
    return Evidence("m:p1:b0", "text", "m.pdf", 1, "m:p1:b0", text, [Box(0, 0, 1, 1)])


def row():
    hit = RowHit(
        "parts:p59:b1",
        "parts.pdf",
        59,
        "parts:p59:b1",
        20,
        ["(1) ITEM NO", "(3) FSCM", "(4) PART NUMBER", "(5) DESCRIPTION", "(6) QTY"],
        ["17", "18265", "P14-8969", ". FILTER ELEMENT,INTA", "1"],
        [Box(0, 0, 0.1, 0.1)] * 5,
        None,
        None,
        "15",
    )
    return row_evidence(hit)


def test_numbers_must_be_in_quote():
    ev = text_ev("Trip pressure 15 ± 3 psi (103.4 ± 20.7 kPa)")
    ok = check_facts("The switch trips at 15 ± 3 psi.", "15 ± 3 psi", ev)
    assert ok.ok
    bad = check_facts("The switch trips at 25 psi.", "15 ± 3 psi", ev)
    assert not bad.ok and "25" in bad.reason


def test_thousands_separator_and_leading_zero_equivalent():
    ev = text_ev("Takeoff and Landing: 3050 lbs. Fuel: .55 gal per hour")
    assert check_facts("Maximum takeoff weight is 3,050 lb.", "3050 lbs", ev).ok
    assert check_facts("It burns 0.55 gallons an hour.", ".55 gal", ev).ok


def test_identifiers_must_be_in_quote():
    ev = row()
    assert check_facts("Its part number is P14-8969.", "P14-8969", ev).ok
    bad = check_facts("Its part number is P14-8970.", "P14-8969", ev)
    assert not bad.ok and "p14-8970" in bad.reason.lower()


def test_right_row_wrong_column_fails():
    ev = row()
    quote = "FSCM: 18265; (4) PART NUMBER: P14-8969"
    bad = check_facts("The part number of the filter element is 18265.", quote, ev)
    assert not bad.ok
    assert "FSCM" in bad.reason and "PART NUMBER" in bad.reason
    assert check_facts(
        "The part number of the filter element is P14-8969.", quote, ev
    ).ok


def test_each_fact_checked_against_its_own_column():
    ev = row()
    quote = "FSCM: 18265; (4) PART NUMBER: P14-8969"
    claim = "Part number P14-8969 is made by CAGE 18265."
    assert check_facts(claim, quote, ev).ok


def test_claim_without_facts_passes():
    ev = text_ev("Service the air cleaner element when the indicator shows red.")
    claim = "Service the air cleaner when its indicator shows red."
    assert check_facts(claim, "indicator shows red", ev).ok


def test_context_from_question_on_cited_page_passes():
    r = check_facts(
        "The maximum baggage for the Cirrus SR20 is 130 pounds.",
        "Maximum baggage for this model is 130 pounds",
        text_ev("Maximum baggage for this model is 130 pounds"),
        question="What is the SR20 maximum baggage?",
        page_text="Cirrus SR20 data sheet. Maximum baggage for this model is 130 pounds",
    )
    assert r.ok


def test_borrowed_subject_not_on_cited_page_fails():
    r = check_facts(
        "The new useful load for the Cessna 172S is 1,216.62 pounds.",
        "NEW USEFUL LOAD 1,216.62",
        text_ev("NEW USEFUL LOAD 1,216.62"),
        question="What is the useful load of a Cessna 172S?",
        page_text="Sample alteration. NEW USEFUL LOAD 1,216.62",
    )
    assert not r.ok and "172s" in r.reason


def test_value_on_page_but_not_in_question_or_quote_fails():
    r = check_facts(
        "The limit is 30 psi.",
        "the limit is stated below",
        text_ev("the limit is stated below"),
        question="What is the limit?",
        page_text="the limit is stated below. Other table: 30 psi",
    )
    assert not r.ok and "30" in r.reason


def test_fact_elsewhere_in_the_row_passes():
    assert check_facts(
        "The part number for the filter element (Item 17) is P14-8969.",
        "P14-8969",
        row(),
    ).ok


def test_cage_trap_still_caught_with_row_context():
    r = check_facts("The part number is 18265.", "18265", row())
    assert not r.ok and "FSCM" in r.reason


def test_number_words_match_digits():
    assert check_facts(
        "Crank for no more than 15 seconds.",
        "Do not crank engine in excess of fifteen seconds.",
        text_ev("Do not crank engine in excess of fifteen seconds."),
    ).ok


def test_ocr_spaced_identifier_matches():
    assert check_facts(
        "Perform the PMCS in Table 2-4.",
        "in accordance with TABLE 2 - 4",
        text_ev("in accordance with TABLE 2 - 4"),
    ).ok
