import pytest

from manualqa.textclean import clean_ocr_text


@pytest.mark.parametrize(
    "raw,clean",
    [
        ("15 $ \\pm $ 3 psi", "15 ± 3 psi"),
        ("$ 0^{\\circ} \\pm 0.5^{\\circ} $", "0° ± 0.5°"),
        ("at $ 32\\,^{\\circ}F $", "at 32°F"),
        ("$ \\frac{1}{12} $ gallon", "1/12 gallon"),
        ("2-10.2 $ \\underline{\\text{Stopping}} $", "2-10.2 Stopping"),
        ("$ Aileron: Up $ 12.5", "Aileron: Up 12.5"),
        ("$ 2 \\times 4 \\leq 9 $", "2 × 4 ≤ 9"),
        ("no maths here", "no maths here"),
        ("costs $5 and $6", "costs $5 and $6"),
    ],
)
def test_clean_ocr_text(raw, clean):
    assert clean_ocr_text(raw) == clean


def test_literal_backslash_n_from_table_html_becomes_a_space():
    assert clean_ocr_text("...WASHER\\nUOC: ENY") == "...WASHER UOC: ENY"
