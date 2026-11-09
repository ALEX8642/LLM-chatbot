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


def test_unknown_reranker_is_refused():
    import pytest

    from manualqa.retrieve import make_reranker

    with pytest.raises(ValueError):
        make_reranker("nope:x")


def test_http_reranker_takes_its_endpoint_from_the_environment(monkeypatch):
    from manualqa.retrieve import HttpReranker, make_reranker

    monkeypatch.setenv("RERANK_BASE_URL", "http://rerank.example/")
    monkeypatch.setenv("RERANK_API_KEY", "k")
    r = make_reranker("http:Qwen/Qwen3-Reranker-4B")
    assert isinstance(r, HttpReranker) and r.name == "Qwen/Qwen3-Reranker-4B"
    assert r._url == "http://rerank.example" and r._key == "k"


def test_qwen_reranker_keeps_the_end_of_its_prompt_when_a_document_is_cut():
    from manualqa.retrieve import QwenReranker

    class Encoded(dict):
        def to(self, device):
            return self

    class Tok:
        def encode(self, text, add_special_tokens=False):
            return [1] * 3 if text == QwenReranker.PREFIX else [2] * 2

        def __call__(self, texts, max_length, **kw):
            return {"input_ids": [[9] * max_length for _ in texts]}

        def pad(self, ids, **kw):
            return Encoded(ids)

    r = QwenReranker.__new__(QwenReranker)
    r.tokenizer, r.device, r.max_length = Tok(), "cpu", QwenReranker.MAX_LENGTH
    r._prefix, r._suffix = [1] * 3, [2] * 2
    ids = r._encode("q", ["x" * 99999])["input_ids"][0]
    assert ids[-2:] == [2, 2] and ids[:3] == [1, 1, 1]
    assert len(ids) == QwenReranker.MAX_LENGTH


def test_qwen_reranker_scores_stay_with_their_texts_when_batched_by_length():
    import pytest

    torch = pytest.importorskip("torch")

    from manualqa.retrieve import QwenReranker

    class Model:
        def __call__(self, input_ids=None, **kw):
            # the "yes" logit is the document's length, so longer scores higher
            logits = torch.zeros(len(input_ids), 1, 2)
            logits[:, 0, 1] = input_ids.sum(dim=1).float()
            return type("O", (), {"logits": logits})()

    r = QwenReranker.__new__(QwenReranker)
    r.torch, r.model, r.batch_size, r.no, r.yes = torch, Model(), 2, 0, 1
    r._encode = lambda q, texts: {"input_ids": torch.tensor([[len(t)] for t in texts])}
    got = r.score("q", ["aaa", "a", "aaaaa", "aa"])
    assert sorted(range(4), key=lambda i: got[i]) == [1, 3, 0, 2]


def test_gpu_allocator_setting_is_a_default_not_an_override():
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:64"}
    code = "import manualqa, os; print(os.environ['PYTORCH_CUDA_ALLOC_CONF'])"
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )
    assert out.stdout.strip() == "max_split_size_mb:64"


def test_search_reuses_its_client_and_a_rebuild_releases_it(tmp_path, monkeypatch):
    from fakes import FakeEmbedder

    from manualqa import index
    from manualqa.chunks import Chunk

    chunks = [
        Chunk("c1", "m", [1], "text", "", "fuel filter element"),
        Chunk("c2", "m", [2], "text", "", "oil pressure"),
    ]
    opened = []
    real = index._client
    monkeypatch.setattr(index, "_client", lambda p: opened.append(p) or real(p))
    monkeypatch.setattr(index, "_OPEN", {})
    emb = FakeEmbedder()
    index.build_index(chunks, tmp_path / "q", emb)
    first = index.search("fuel filter", tmp_path / "q", emb, k=1)
    index.search("oil pressure", tmp_path / "q", emb, k=1)
    assert len(opened) == 2  # one for the build, one kept for every search
    index.build_index(chunks, tmp_path / "q", emb)  # must not hit the lock
    assert (
        index.search("fuel filter", tmp_path / "q", emb, k=1)[0][0].id == first[0][0].id
    )
