from manualqa.blocks import Block, Cell, Line, PageParse
from manualqa.chunks import MAX_CHARS, chunk_manual, dump_chunks, load_chunks
from manualqa.geometry import Box

MID = Box(0.1, 0.3, 0.9, 0.35)


def blk(i, kind, text, box=MID, page=1, cells=(), lines=None):
    lines = (
        lines if lines is not None else [Line(t, box) for t in text.split("\n") if t]
    )
    return Block(f"m:p{page}:b{i}", kind, text, box, lines=lines, cells=list(cells))


def page(n, blocks):
    return PageParse("m.pdf", n, "test", 100, 100, 150, False, None, blocks, 0.0)


def test_heading_starts_chunk():
    chunks = chunk_manual(
        [
            page(
                1,
                [
                    blk(0, "heading", "Fuel"),
                    blk(1, "text", "Use diesel."),
                    blk(2, "heading", "Oil"),
                    blk(3, "text", "Use 15W-40."),
                ],
            )
        ]
    )
    assert [(c.heading, c.text) for c in chunks] == [
        ("Fuel", "Fuel\nUse diesel."),
        ("Oil", "Oil\nUse 15W-40."),
    ]
    assert chunks[0].block_ids == ["m:p1:b0", "m:p1:b1"]


def test_text_chunk_size_limit():
    para = "word " * 100  # 500 chars
    blocks = [blk(0, "heading", "Long")] + [
        blk(i, "text", para.strip()) for i in range(1, 8)
    ]
    chunks = chunk_manual([page(1, blocks)])
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHARS for c in chunks)
    assert all(c.heading == "Long" for c in chunks)


def table_block(nrows):
    cells = [Cell(0, 0, "ITEM", None), Cell(0, 1, "PART NUMBER", None)]
    for r in range(1, nrows + 1):
        cells += [Cell(r, 0, str(r), None), Cell(r, 1, f"P-{r:03d}", None)]
    return blk(0, "table", "", Box(0.1, 0.1, 0.9, 0.9), cells=cells, lines=[])


def test_table_chunk_repeats_header():
    chunks = chunk_manual([page(1, [table_block(60)])])
    assert [c.kind for c in chunks] == ["table"] * 3
    assert all(c.text.splitlines()[0] == "ITEM | PART NUMBER" for c in chunks)
    assert "P-060" in chunks[-1].text


def test_figure_with_text_becomes_chunk():
    plate = blk(0, "figure", "MODEL MEP-802A\n5KW 60HZ", Box(0.1, 0.1, 0.9, 0.5))
    caption = blk(
        1, "caption", "Figure 2-10. Set Rating Plate", Box(0.1, 0.52, 0.9, 0.55)
    )
    bare = blk(2, "figure", "", Box(0.1, 0.6, 0.9, 0.9), lines=[])
    chunks = chunk_manual([page(1, [plate, caption, bare])])
    figures = [c for c in chunks if c.kind == "figure"]
    assert len(figures) == 1
    assert "MEP-802A" in figures[0].text and "Rating Plate" in figures[0].text


def test_chunks_skip_running_headers():
    top = blk(0, "other", "ARMY TM 9-6115-641-10", Box(0.6, 0.02, 0.9, 0.05))
    foot = blk(2, "other", "2-21", Box(0.8, 0.95, 0.9, 0.97))
    chunks = chunk_manual([page(1, [top, blk(1, "text", "Start the engine."), foot])])
    assert all("ARMY TM" not in c.text and "2-21" not in c.text for c in chunks)
    assert any("Start the engine." in c.text for c in chunks)


def test_chunk_ids_stable_and_round_trip(tmp_path):
    pages = [page(1, [blk(0, "heading", "Fuel"), blk(1, "text", "Use diesel.")])]
    a, b = chunk_manual(pages), chunk_manual(pages)
    assert [c.id for c in a] == [c.id for c in b] and len({c.id for c in a}) == len(a)
    dump_chunks(a, tmp_path / "c.jsonl")
    assert load_chunks(tmp_path / "c.jsonl") == a


def test_running_headers_at_real_positions():
    # parts p59: header bottom at y=0.09, page number "15-1" at y=0.885
    top = blk(0, "other", "ARMY TM 9-6115-641-24P", Box(0.7, 0.07, 0.95, 0.09))
    num = blk(2, "other", "15-1", Box(0.48, 0.875, 0.52, 0.89))
    body = blk(1, "text", "Install the filter.", Box(0.1, 0.4, 0.9, 0.45))
    chunks = chunk_manual([page(1, [top, body, num])])
    text = "\n".join(c.text for c in chunks)
    assert "ARMY TM" not in text and "15-1" not in text and "Install" in text
