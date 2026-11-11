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


def test_units_on_the_same_number_must_agree():
    ev = text_ev("Trip pressure 25 psi (172 kPa)")
    source = "25 psi (172 kPa)"
    assert check_facts("It trips at 172 kPa.", source, ev).ok
    assert check_facts("It trips at 25 psi.", source, ev).ok
    assert not check_facts("It trips at 172 psi.", source, ev).ok
    assert check_facts("It trips at 172 kilopascals.", source, ev).ok


def test_a_number_without_a_printed_unit_takes_the_claims_unit():
    ev = text_ev("Fuel capacity 40")
    assert check_facts("The capacity is 40 gallons.", "Fuel capacity 40", ev).ok


def test_signs_must_not_be_opposite():
    ev = text_ev("Limit +15 at sea level, -5 aloft")
    assert not check_facts("The limit is -15.", "Limit +15", ev).ok
    assert check_facts("The limit is +15.", "Limit +15", ev).ok
    assert check_facts("The limit is 15.", "Limit +15", ev).ok
    assert not check_facts("The limit is minus 15.", "Limit +15", ev).ok
    assert check_facts("Aloft it is -5.", "-5 aloft", ev).ok


def test_a_range_is_not_a_sign():
    ev = text_ev("Set the gap to 10-15 mm")
    assert check_facts("The gap is 10-15 mm.", "10-15 mm", ev).ok


def test_number_words_in_a_claim_are_facts():
    ev = text_ev("Do not crank for more than fifteen seconds")
    source = "more than fifteen seconds"
    assert not check_facts("Crank for no more than thirty seconds.", source, ev).ok
    assert check_facts("Crank for no more than fifteen seconds.", source, ev).ok
    assert check_facts("Crank for no more than 15 seconds.", source, ev).ok


def test_compound_number_words():
    ev = text_ev("Wait 25 minutes")
    assert check_facts("Wait twenty-five minutes.", "Wait 25 minutes", ev).ok
    assert not check_facts("Wait twenty-six minutes.", "Wait 25 minutes", ev).ok


def test_one_is_not_a_number_fact():
    ev = text_ev("Open the valve")
    assert check_facts(
        "One of the steps is to open the valve.", "Open the valve", ev
    ).ok


def test_ocr_letter_o_in_a_number():
    ev = text_ev("Torque to 1O ft-lb")
    assert check_facts("Torque to 10 ft-lb.", "Torque to 1O ft-lb", ev).ok


def test_label_after_the_value_is_checked():
    ev = row()
    bad = check_facts("18265 is the part number.", "18265", ev)
    assert not bad.ok and "FSCM" in bad.reason
    assert check_facts("P14-8969 is the part number.", "P14-8969", ev).ok


def test_label_abbreviation_is_checked():
    ev = row()
    assert not check_facts("The quantity used is 18265.", "18265", ev).ok
    assert check_facts("The quantity used is 1.", "1", ev).ok
    assert not check_facts("The CAGE code is P14-8969.", "P14-8969", ev).ok
    assert check_facts("The CAGE code is 18265.", "18265", ev).ok


def test_item_number_beside_a_labelled_value_passes():
    ev = row()
    assert check_facts("Item 17 has part number P14-8969.", "17; P14-8969", ev).ok


def under_ev(text, under):
    return Evidence(
        "m:p1:b0", "text", "m.pdf", 1, "m:p1:b0", text, [Box(0, 0, 1, 1)], under=under
    )


def test_heading_the_page_sits_under_counts_as_context():
    ev = under_ev("Maximum baggage 130 pounds", "I - Model SR20, (Normal Category)")
    assert check_facts("The SR20 allows 130 pounds.", "130 pounds", ev).ok
    assert not check_facts("The SR22 allows 130 pounds.", "130 pounds", ev).ok


def test_column_heading_counts_as_context():
    hit = RowHit(
        "t",
        "m.pdf",
        24,
        "t",
        3,
        ["Connection", "MEP-802A"],
        ["120/208", "17 amps"],
        [Box(0, 0, 1, 1)] * 2,
        None,
        None,
        None,
    )
    ev = row_evidence(hit)
    assert check_facts("The MEP-802A is rated 17 amps.", "17 amps", ev).ok


def test_range_broken_over_a_line():
    ev = text_ev("OIL PRESSURE [25-\n60 psi]")
    assert check_facts("It reads 25-60 psi.", "OIL PRESSURE [25-\n60 psi]", ev).ok


def test_number_run_into_its_unit():
    ev = text_ev("SET RATING AT 400HZ")
    assert check_facts("It is for the 400 Hz set.", "RATING AT 400HZ", ev).ok
    ev = text_ev("DRY WT\n800LBLG")
    assert check_facts("The dry weight is 800 lb.", "DRY WT\n800LBLG", ev).ok


def test_hyphenated_measure_is_a_number():
    ev = text_ev("a 60 degree bank on a 3,000 pound airplane")
    source = "a 60 degree bank on a 3,000 pound airplane"
    assert check_facts("A 60-degree bank on a 3,000-pound airplane.", source, ev).ok
    assert not check_facts("A 45-degree bank.", source, ev).ok


def test_a_number_in_a_heading_is_not_evidence():
    ev = under_ev("Ensure load does not exceed rating", "Table 3-1. Troubleshooting")
    assert not check_facts("Limit the load to 3 kW.", "does not exceed rating", ev).ok


def test_a_code_ending_in_a_letter_is_not_its_number():
    ev = text_ev("Oil ML-L-2104C or W-F-800")
    assert not check_facts("Use 2104 grade oil.", "Oil ML-L-2104C or W-F-800", ev).ok


def test_an_identifier_must_match_a_whole_token():
    ev = text_ev("Part number P14-8969, screw MS35338-44, set MEP-802A")
    src = ev.text
    assert not check_facts("The part number is P14-89.", src, ev).ok
    assert not check_facts("Use screw MS35338-4.", src, ev).ok
    assert not check_facts("The set is the MEP-802.", src, ev).ok
    assert check_facts("The part number is P14-8969.", src, ev).ok


def test_in_and_a_before_a_word_are_not_units():
    ev = text_ev("Set the pressure to 15 psi")
    assert check_facts("Set it to 15 in accordance with the table.", "15 psi", ev).ok
    assert not check_facts("Set it to 15 in.", "15 psi", ev).ok


def test_letter_spaced_ocr_digits_match():
    src = "T O R Q U E  2 5  F T - L B\nnext line"
    ev = text_ev(src)
    assert check_facts("Torque to 25 ft-lb.", src, ev).ok


def test_separate_digits_on_an_ordinary_line_stay_apart():
    src = "Items 1 2 and 3 are shown"
    ev = text_ev(src)
    assert not check_facts("Item 12 is shown.", src, ev).ok


def test_wording_keeps_numbers_and_deciding_words():
    from manualqa.facts import check_wording

    src = "crank the engine for more than 20 seconds."
    assert not check_wording("crank the engine for more than 30 seconds", src).ok
    assert not check_wording(
        "The operator must check the oil level before each start",
        "The operator may check the oil level before each start,",
    ).ok
    assert check_wording("must not exceed 225 F", "mustn't exceed 225 F").ok


def test_wording_refuses_a_quote_that_starts_after_a_negation():
    from manualqa.facts import check_wording

    quote = "crank the engine for more than 30 seconds"
    src = "crank the engine for more than 30 seconds."
    assert not check_wording(quote, src, "CAUTION\nDo not ").ok
    assert check_wording(quote, src, "Never mind.\n").ok  # another sentence
    assert check_wording("Do not " + quote, "Do not " + src, "CAUTION\n").ok


def test_wording_tolerates_ocr_spacing_and_a_list_number():
    from manualqa.facts import check_wording

    spaced = "t h e  e n g i n e  s h o u l d  n o t  b e  c r a n k e d"
    assert check_wording("the engine should not be cranked", spaced).ok
    assert check_wording(
        "7. Engine knocks. Step 1. Check", "Engine knocks.\nStep 1. Check"
    ).ok


def test_reviewed_cases_fail_end_to_end_through_quote_and_wording():
    from manualqa.facts import check_wording
    from manualqa.quotes import match_quote

    cases = [  # (block text, quote): each matches the fuzzy quote check
        ("Do not crank the engine for more than 20 seconds.", "crank the engine for more than 30 seconds"),
        ("Do not crank the engine for more than 30 seconds.", "crank the engine for more than 30 seconds"),
        (
            "The operator may check the oil level before each start, and must stop if it is low.",
            "The operator must check the oil level before each start",
        ),
    ]  # fmt: skip
    for text, quote in cases:
        ev = text_ev(text)
        m = match_quote(quote, ev)
        assert m is not None
        assert not check_wording(quote, m.source, ev.text[: m.span[0]]).ok, quote


# Claims v2's checks wrongly removed on the unseen manual (FIST 3-30), and the traps they must
# still catch.


def gasket_row():
    hit = RowHit(
        "fist:p37:b4",
        "fist.pdf",
        37,
        "fist:p37:b4",
        4,
        ["Standard groove depth (in inches)", "Recommended gasket thickness (in inches)",
         "Available to compress (in inches)", "Available compression (percent)"],
        ["1/4", "3/8", "1/8", "33"],
        [Box(0, 0, 0.1, 0.1)] * 4,
        None,
        None,
        "",
    )  # fmt: skip
    return row_evidence(hit)


def test_a_heading_unit_in_brackets_is_not_needed_to_name_the_column():
    ev, quote = (
        gasket_row(),
        "Standard groove depth (in inches): 1/4; Recommended gasket thickness (in inches): 3/8",
    )
    claim = "For a standard groove depth of 1/4 inch, the recommended gasket thickness is 3/8 inch."
    assert check_facts(claim, quote, ev).ok
    bad = "For a standard groove depth of 3/8 inch, the recommended gasket thickness is 1/4 inch."
    assert not check_facts(bad, quote, ev).ok


def test_a_vulgar_fraction_after_a_whole_number():
    src = "the outer diameter would be 8 inches minus ¼ inch, or 7¾ inches."
    assert check_facts("Cut the outer diameter to 7 3/4 inches.", src, text_ev(src)).ok
    assert not check_facts("Cut the outer diameter to 73 inches.", src, text_ev(src)).ok


def test_a_value_from_the_question_inside_a_range_the_source_gives():
    src = "Condition 3; 701-1,800"
    q = "A transformer has 900 ppm of dissolved hydrogen. Which condition is it in?"
    claim = "A hydrogen level of 900 ppm places the transformer in Condition 3."
    assert check_facts(claim, src, text_ev(src), question=q).ok
    assert not check_facts(claim, src, text_ev(src), question="Which condition?").ok
    outside = "A hydrogen level of 2,000 ppm places the transformer in Condition 3."
    assert not check_facts(
        outside, src, text_ev(src), question=q.replace("900", "2,000")
    ).ok


def test_a_footnote_reference_is_not_a_number_of_the_source():
    from manualqa.facts import check_wording

    source = "Reverse two phase leads if this is encountered.[4]"
    assert check_wording("Reverse two phase leads if this is encountered.", source).ok
    assert not check_wording(
        "Reverse two phase leads within 5 minutes.",
        "Reverse two phase leads within 4 minutes.",
    ).ok


# Parse and notation cases the checks misread: glued table cells, "4112 x2176", "10-tap".


def test_a_dimension_written_without_a_space_is_two_numbers():
    src = "Full Resolution: M4060 4112 x2176"
    assert check_facts("The resolution is 4112 x 2176.", src, text_ev(src)).ok
    assert not check_facts("The resolution is 4112 x 2178.", src, text_ev(src)).ok
    hex_src = "Write 0x0010 to the register."
    assert not check_facts(
        "Write 0x0011 to the register.", hex_src, text_ev(hex_src)
    ).ok


def test_a_hyphenated_count_is_its_number():
    src = 'This "ten tap" configuration outputs 8-bit/pixel.'
    q = "How many bits per pixel in 10-tap mode?"
    claim = "In 10-tap mode the camera outputs 8 bits per pixel."
    assert check_facts(claim, src, text_ev(src), question=q, page_text=src).ok
    assert not check_facts(
        claim.replace("10-tap", "12-tap"), src, text_ev(src), q, src
    ).ok


def test_a_quote_is_not_widened_into_a_cell_the_parse_glued_on():
    from manualqa.facts import check_wording
    from manualqa.quotes import match_quote

    for text, quote in [
        ("Mass; Medium Case: 72gXL Case: ~ 163g", "XL Case: ~ 163g"),
        ("Input; +10 to +36 Volts DC (+10%/- 10%)+9 to +56 Volts", "+10 to +36 Volts DC (+10%/- 10%)"),
    ]:  # fmt: skip
        ev = text_ev(text)
        m = match_quote(quote, ev)
        assert m is not None and check_wording(quote, m.source, ev.text[: m.span[0]]).ok
    ev = text_ev("The limit is 300 psi.")
    m = match_quote("The limit is 30", ev)
    assert m is None or not check_wording("The limit is 30", m.source).ok
