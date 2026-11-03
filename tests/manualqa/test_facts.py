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
