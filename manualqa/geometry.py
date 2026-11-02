"""The one coordinate system.

Every box in v2 is page-normalised: [0, 1] on both axes, origin at the top-left of the
page as rendered (after CropBox and rotation). This module is the only place that knows
about PDF origins, the CropBox and page rotation.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf
from PIL import Image


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)

    def iou(self, other: Box) -> float:
        w = min(self.x1, other.x1) - max(self.x0, other.x0)
        h = min(self.y1, other.y1) - max(self.y0, other.y0)
        inter = max(0.0, w) * max(0.0, h)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def to_px(self, width: int, height: int) -> tuple[int, int, int, int]:
        return (
            round(self.x0 * width),
            round(self.y0 * height),
            round(self.x1 * width),
            round(self.y1 * height),
        )


def _norm_box(x0: float, y0: float, x1: float, y1: float) -> Box:
    def clamp(v: float) -> float:
        return min(1.0, max(0.0, v))

    return Box(
        clamp(min(x0, x1)), clamp(min(y0, y1)), clamp(max(x0, x1)), clamp(max(y0, y1))
    )


def _user_to_display(page: pymupdf.Page) -> tuple[float, ...]:
    # PyMuPDF's page.transformation_matrix ignores the crop box offset on rotated
    # pages; MuPDF's pdf_page_transform is what rendering uses.
    pdf_page = pymupdf.mupdf.pdf_page_from_fz_page(page.this)
    ctm = pymupdf.mupdf.FzMatrix()
    pymupdf.mupdf.pdf_page_transform(pdf_page, pymupdf.mupdf.FzRect(), ctm)
    return (ctm.a, ctm.b, ctm.c, ctm.d, ctm.e, ctm.f)


@dataclass(frozen=True)
class PageFrame:
    """A page as rendered: maps PDF coordinates and pixels to normalised boxes."""

    width_px: int
    height_px: int
    dpi: int
    # unrotated top-left page space -> displayed page space (points)
    _display: tuple[float, float, float, float, float, float]
    # raw PDF user space -> displayed page space (MuPDF's own page transform)
    _user: tuple[float, float, float, float, float, float]
    _width_pt: float
    _height_pt: float

    @classmethod
    def from_page(cls, page: pymupdf.Page, width_px: int, height_px: int, dpi: int):
        return cls(
            width_px=width_px,
            height_px=height_px,
            dpi=dpi,
            _display=tuple(page.rotation_matrix),
            _user=_user_to_display(page),
            _width_pt=page.rect.width,
            _height_pt=page.rect.height,
        )

    def _from_display_rect(self, r: pymupdf.Rect) -> Box:
        return _norm_box(
            r.x0 / self._width_pt,
            r.y0 / self._height_pt,
            r.x1 / self._width_pt,
            r.y1 / self._height_pt,
        )

    def from_pdf_topleft(self, x0: float, y0: float, x1: float, y1: float) -> Box:
        """PyMuPDF's extraction space (``get_text``, ``get_drawings``): unrotated,
        origin at the top-left of the crop box."""
        r = pymupdf.Rect(x0, y0, x1, y1) * pymupdf.Matrix(self._display)
        return self._from_display_rect(r)

    def from_pdf_user(self, x0: float, y0: float, x1: float, y1: float) -> Box:
        """Raw PDF user space: MediaBox origin, y axis up."""
        r = pymupdf.Rect(x0, y0, x1, y1) * pymupdf.Matrix(self._user)
        return self._from_display_rect(r)

    def from_px(
        self, x0: float, y0: float, x1: float, y1: float, width_px: int, height_px: int
    ) -> Box:
        """Pixels on any render of this page, at any resolution."""
        return _norm_box(x0 / width_px, y0 / height_px, x1 / width_px, y1 / height_px)


def render_page(page: pymupdf.Page, dpi: int = 150) -> tuple[Image.Image, PageFrame]:
    """Render the page as displayed; the frame's size is the pixmap's actual size."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img, PageFrame.from_page(page, pix.width, pix.height, dpi)
