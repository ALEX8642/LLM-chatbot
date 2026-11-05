from manualqa.retrieve import retrieve

PARTS = "Army_5kW_Generator_Parts_Manual.pdf"


def test_retrieve_returns_row_evidence_for_part_number(ctx):
    result = retrieve("What is part P14-8969?", PARTS, ctx)
    first = result.evidence[0]
    assert first.kind == "row" and "P14-8969" in first.cells
    assert first.header and first.boxes and first.id.endswith(f":r{first.row}")


def test_item_in_figure_lookup(ctx):
    result = retrieve("What is item 17 in figure 15?", PARTS, ctx)
    rows = [e for e in result.evidence if e.kind == "row"]
    assert any("P14-8969" in e.cells for e in rows)
    assert result.table_hits >= 1


def test_page_images_distinct_and_capped(ctx):
    result = retrieve("air cleaner filter element radiator", PARTS, ctx)
    pages = [p.name for p in result.page_images]
    assert 1 <= len(pages) <= 3 and len(set(pages)) == len(pages)
    assert all(p.exists() and p.name.endswith("-gen.jpg") for p in result.page_images)


def test_text_evidence_boxes_are_line_boxes(ctx):
    result = retrieve(
        "Who is responsible for weight and balance control?",
        "FAA_Weight_and_Balance_Handbook.pdf",
        ctx,
    )
    texts = [e for e in result.evidence if e.kind == "text"]
    assert texts
    block = ctx.blocks[texts[0].block_id]
    assert texts[0].boxes == [ln.box for ln in block.lines]
    assert texts[0].text == block.text


def test_evidence_ids_unique(ctx):
    result = retrieve("What is item 17 in figure 15?", PARTS, ctx)
    ids = [e.id for e in result.evidence]
    assert len(ids) == len(set(ids))


def test_figure_evidence_has_the_figures_box_not_its_line_boxes():
    from types import SimpleNamespace

    from manualqa.blocks import Block, Line
    from manualqa.geometry import Box
    from manualqa.retrieve import _block_evidence

    whole, line = Box(0.1, 0.1, 0.9, 0.5), Box(0.2, 0.2, 0.3, 0.25)
    lines = [Line("4.2 kW", line), Line("JP4", line)]
    fig = Block("m:p1:b0", "figure", "4.2 kW JP4", whole, lines)
    text = Block("m:p1:b1", "text", "4.2 kW JP4", whole, lines)
    ctx = SimpleNamespace(
        blocks={fig.id: fig, text.id: text},
        block_page={fig.id: ("m.pdf", 1), text.id: ("m.pdf", 1)},
        under={},
    )
    assert _block_evidence(ctx, fig.id).boxes == [whole]
    assert _block_evidence(ctx, text.id).boxes == [line, line]


def test_titles_carry_over_to_a_continuation_page():
    from manualqa.blocks import Block, PageParse
    from manualqa.geometry import Box
    from manualqa.retrieve import titles_by_page

    box = Box(0, 0, 1, 1)

    def page(n, *blocks):
        return PageParse(
            "m",
            n,
            "p",
            100,
            100,
            72,
            False,
            None,
            [Block(f"b{i}", kind, text, box) for i, (kind, text) in enumerate(blocks)],
            0.0,
        )

    pages = [
        page(1, ("heading", "I - Model SR20"), ("caption", "Figure 1.")),
        page(2, ("table", "rows")),
        page(3, ("heading", "II - Model SR22")),
        page(4),
    ]
    t = titles_by_page(pages)
    assert t[("m", 2)] == "I - Model SR20; Figure 1."
    assert t[("m", 3)] == "I - Model SR20; II - Model SR22; Figure 1."
    assert t[("m", 4)] == "II - Model SR22; Figure 1."
