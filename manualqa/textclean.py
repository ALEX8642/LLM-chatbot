"""Clean OCR text for matching and display.

PaddleOCR-VL writes symbols and some plain words as LaTeX maths, always with spaces inside
the dollars ("15 $ \\pm $ 3 psi"). Those spans are turned into plain Unicode text; a dollar
amount ("$5") is left alone.
"""

import re

_MATH = re.compile(r"\$ (.+?) \$")
_SYMBOLS = {
    r"\pm": "±",
    r"\times": "×",
    r"\leq": "≤",
    r"\geq": "≥",
    r"\approx": "≈",
    r"\mu": "µ",
    r"\%": "%",
    r"\,": "",
}
_DEGREE = re.compile(r"\^\{?\\circ\}?")
_FRAC = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_WRAPPER = re.compile(r"\\(?:text|mathrm|underline|mathbf|textbf)\{([^{}]*)\}")
_COMMAND = re.compile(r"\\([A-Za-z]+)")


def _plain(maths: str) -> str:
    maths = _DEGREE.sub("°", maths)
    for command, symbol in _SYMBOLS.items():
        maths = maths.replace(command, symbol)
    maths = _FRAC.sub(r"\1/\2", maths)
    while _WRAPPER.search(maths):
        maths = _WRAPPER.sub(r"\1", maths)
    maths = _COMMAND.sub(r"\1", maths)
    maths = re.sub(r"\s*°", "°", maths)
    return maths.replace("{", "").replace("}", "")


def clean_ocr_text(text: str) -> str:
    """LaTeX spans to Unicode; whitespace collapsed. Text without maths is unchanged
    apart from whitespace."""
    return " ".join(_MATH.sub(lambda m: _plain(m.group(1)), text).split())
