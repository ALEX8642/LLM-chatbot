"""Text normalisation used by every text comparison."""

import unicodedata


def norm(text: str) -> str:
    """NFKC, case-folded, whitespace runs (including NBSP) collapsed to one space."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())
