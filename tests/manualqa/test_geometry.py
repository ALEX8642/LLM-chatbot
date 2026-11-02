import pymupdf
import pytest

from manualqa.geometry import Box, render_page

CASES = [(r, c) for r in (0, 90, 180, 270) for c in (None, (50, 60, 562, 752))]


def make_page(rotation, cropbox):
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    if cropbox is not None:
        page.set_cropbox(pymupdf.Rect(cropbox))
    page.set_rotation(rotation)
    return page


def append_stream(page, data: bytes):
    """Append a raw content stream (PDF user space) to the page, bypassing PyMuPDF's
    coordinate helpers so the test's truth does not come from code under test."""
    doc = page.parent
    xref = doc.get_new_xref()
    doc.update_object(xref, "<<>>")
    doc.update_stream(xref, data)
    contents = page.get_contents()
    refs = " ".join(f"{x} 0 R" for x in contents + [xref])
    doc.xref_set_key(page.xref, "Contents", f"[{refs}]")


def dark_bbox(img):
    gray = img.convert("L")
    mask = gray.point(lambda v: 255 if v < 64 else 0)
    x0, y0, x1, y1 = mask.getbbox()
    return (x0, y0, x1, y1)


@pytest.mark.parametrize("rotation,cropbox", CASES)
def test_extraction_rect_lands_on_rendered_pixels(rotation, cropbox):
    # "topleft" is PyMuPDF's extraction space (get_text, get_drawings): unrotated,
    # relative to the crop box. (page.draw_rect is not used: on rotated and cropped
    # pages it does not draw where get_drawings later reports.)
    page = make_page(rotation, cropbox)
    append_stream(page, b"0 0 0 rg 100 300 100 100 re f")
    rect = page.get_drawings()[0]["rect"]
    img, frame = render_page(page, dpi=150)
    box = frame.from_pdf_topleft(*rect)
    assert box.to_px(*img.size) == pytest.approx(dark_bbox(img), abs=2)


@pytest.mark.parametrize("rotation,cropbox", CASES)
def test_user_space_rect_lands_on_rendered_pixels(rotation, cropbox):
    page = make_page(rotation, cropbox)
    append_stream(page, b"0 0 0 rg 100 300 100 100 re f")
    img, frame = render_page(page, dpi=150)
    box = frame.from_pdf_user(100, 300, 200, 400)
    assert box.to_px(*img.size) == pytest.approx(dark_bbox(img), abs=2)


def test_frame_size_is_the_pixmap_size():
    page = make_page(0, (0.3, 0.3, 300.7, 400.9))
    img, frame = render_page(page, dpi=150)
    assert (frame.width_px, frame.height_px) == img.size


def test_from_px_is_resolution_independent():
    page = make_page(90, None)
    _, frame = render_page(page, dpi=150)
    a = frame.from_px(100, 200, 300, 400, 1000, 2000)
    b = frame.from_px(200, 400, 600, 800, 2000, 4000)
    assert a == b == Box(0.1, 0.1, 0.3, 0.2)


def test_box_iou():
    assert Box(0, 0, 0.5, 0.5).iou(Box(0, 0, 0.5, 0.5)) == 1
    assert Box(0, 0, 0.5, 0.5).iou(Box(0.5, 0.5, 1, 1)) == 0
    assert Box(0, 0, 0.4, 0.4).iou(Box(0.2, 0, 0.6, 0.4)) == pytest.approx(1 / 3)
