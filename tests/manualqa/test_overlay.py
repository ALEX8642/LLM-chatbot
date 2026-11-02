from PIL import Image, ImageColor

from manualqa.blocks import Block, PageParse
from manualqa.geometry import Box
from manualqa.overlay import draw_overlay


def page_with_block(kind="text", box=Box(0.1, 0.1, 0.5, 0.5), ocr=False, error=None):
    return PageParse(
        manual="m.pdf",
        page=1,
        parser="test",
        width_px=1000,
        height_px=1000,
        dpi=150,
        ocr=ocr,
        ocr_reason="letter_spaced" if ocr else None,
        blocks=[Block("m:p1:b0", kind, "x", box)],
        seconds=0.0,
        error=error,
    )


def test_overlay_draws_block_outline_and_leaves_inside_clear():
    img = Image.new("RGB", (1000, 1000), "white")
    out = draw_overlay(img, page_with_block(), long_edge=1000)
    assert out.getpixel((100, 300)) == ImageColor.getrgb("#1f77b4")
    assert out.getpixel((300, 300)) == (255, 255, 255)


def test_overlay_colours_by_kind():
    img = Image.new("RGB", (1000, 1000), "white")
    out = draw_overlay(img, page_with_block(kind="table"), long_edge=1000)
    assert out.getpixel((100, 300)) == ImageColor.getrgb("#2ca02c")


def test_overlay_resizes_long_edge():
    img = Image.new("RGB", (1275, 1650), "white")
    out = draw_overlay(img, page_with_block(), long_edge=1100)
    assert max(out.size) == 1100


def has_red_in_top_rows(out, rows=20):
    return any(
        out.getpixel((x, y)) == (255, 0, 0)
        for y in range(rows)
        for x in range(0, out.width, 5)
    )


def test_overlay_marks_ocr_pages():
    img = Image.new("RGB", (1000, 1000), "white")
    assert has_red_in_top_rows(draw_overlay(img, page_with_block(ocr=True), 1000))
    assert not has_red_in_top_rows(draw_overlay(img, page_with_block(), 1000))


def test_overlay_marks_errors():
    img = Image.new("RGB", (1000, 1000), "white")
    out = draw_overlay(img, page_with_block(error="RuntimeError: boom"), 1000)
    assert has_red_in_top_rows(out)


def test_overlay_does_not_modify_input():
    img = Image.new("RGB", (1000, 1000), "white")
    draw_overlay(img, page_with_block(), long_edge=1000)
    assert img.getpixel((100, 300)) == (255, 255, 255)
