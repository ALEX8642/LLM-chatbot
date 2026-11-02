"""Draw a parse over its rendered page, for checking boxes by eye."""

from __future__ import annotations

from PIL import Image, ImageDraw

from manualqa.blocks import PageParse

KIND_COLOURS = {
    "text": "#1f77b4",
    "heading": "#9467bd",
    "table": "#2ca02c",
    "figure": "#ff7f0e",
    "caption": "#7f7f7f",
    "other": "#8c564b",
}
LINE_COLOUR = "#17becf"
CELL_COLOUR = "#2ca02c"
BANNER = (255, 0, 0)


def draw_overlay(
    image: Image.Image, pp: PageParse, long_edge: int = 1100
) -> Image.Image:
    out = image.convert("RGB")  # a copy; the input stays untouched
    draw = ImageDraw.Draw(out)
    w, h = out.size
    for b in pp.blocks:
        for c in b.cells:
            if c.box is not None:
                draw.rectangle(c.box.to_px(w, h), outline=CELL_COLOUR, width=1)
        for ln in b.lines:
            draw.rectangle(ln.box.to_px(w, h), outline=LINE_COLOUR, width=1)
        x0, y0, x1, y1 = b.box.to_px(w, h)
        colour = KIND_COLOURS.get(b.kind, KIND_COLOURS["other"])
        draw.rectangle((x0, y0, x1, y1), outline=colour, width=3)
        draw.text((x0 + 4, y0 + 4), b.id.rsplit(":", 1)[-1], fill=colour)

    banners = []
    if pp.ocr:
        banners.append(f"OCR: {pp.ocr_reason}")
    if pp.error:
        banners.append(f"ERROR: {pp.error[:80]}")
    for i, text in enumerate(banners):
        top = i * 24
        draw.rectangle((0, top, w, top + 20), fill=BANNER)
        draw.text((6, top + 4), text, fill=(255, 255, 255))

    scale = long_edge / max(w, h)
    if scale != 1:
        out = out.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    return out
