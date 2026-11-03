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
