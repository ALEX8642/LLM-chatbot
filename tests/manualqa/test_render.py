from pathlib import Path

from PIL import Image

from manualqa.geometry import render_page
from manualqa.render import GEN_LONG_EDGE, render_manual

FAA = (
    Path(__file__).resolve().parents[2] / "manuals/FAA_Weight_and_Balance_Handbook.pdf"
)


def test_render_sizes(tmp_path, manual):
    out = render_manual(FAA, tmp_path, pages=[16])
    display, gen = out[16]
    width, _ = render_page(manual(FAA.name)[15], dpi=150)[0].size
    assert Image.open(display).width == width
    assert max(Image.open(gen).size) == GEN_LONG_EDGE == 1000
    assert display.name == "p016.jpg" and gen.name == "p016-gen.jpg"


def test_render_skips_existing(tmp_path):
    display, _ = render_manual(FAA, tmp_path, pages=[16])[16]
    before = display.stat().st_mtime_ns
    render_manual(FAA, tmp_path, pages=[16])
    assert display.stat().st_mtime_ns == before
