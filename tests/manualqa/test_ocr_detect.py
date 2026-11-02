import pytest

from manualqa.ocr_detect import needs_ocr

OP = "Army_5kW_Generator_Operator_Manual.pdf"
PARTS = "Army_5kW_Generator_Parts_Manual.pdf"
FAA = "FAA_Weight_and_Balance_Handbook.pdf"


@pytest.mark.parametrize(
    "pdf,page,reason",
    [
        (OP, 51, "letter_spaced"),
        (OP, 70, "letter_spaced"),
        (OP, 57, "image_cover"),
        (PARTS, 58, "image_cover"),
        (FAA, 31, "vector_text"),
        (FAA, 1, "image_cover"),
        (FAA, 16, None),
        (OP, 22, None),
        (PARTS, 20, None),
    ],
)
def test_needs_ocr(manual, pdf, page, reason):
    d = needs_ocr(manual(pdf)[page - 1])
    assert (d.ocr, d.reason) == (reason is not None, reason)
