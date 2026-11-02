from manualqa.textnorm import norm


def test_norm_unicode_case_and_spaces():
    assert norm("15 ± 3 PSI") == "15 ± 3 psi"


def test_norm_ligature_and_newlines():
    assert norm("ﬁlter  element\n") == "filter element"
