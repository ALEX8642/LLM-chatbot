from manualqa.claimcheck import PREMISE_CHARS, LLMChecker, premise_for
from manualqa.geometry import Box
from manualqa.retrieve import Evidence


class Reply:
    def __init__(self, text):
        self.text, self.messages = text, None

    def complete(self, messages):
        self.messages = messages
        return self.text


def ev(text, under=""):
    return Evidence("e", "text", "m", 1, "e", text, [Box(0, 0, 1, 1)], under=under)


def test_yes_and_no():
    assert LLMChecker(Reply(" Yes.")).supported("c", "p") == 1.0
    assert LLMChecker(Reply("no")).supported("c", "p") == 0.0


def test_an_unclear_reply_is_not_support():
    assert LLMChecker(Reply("The excerpt says yes")).supported("c", "p") == 0.0


def test_the_prompt_holds_claim_and_premise():
    gen = Reply("yes")
    LLMChecker(gen).supported("THE CLAIM", "THE PREMISE")
    text = gen.messages[0]["content"]
    assert "THE CLAIM" in text and "THE PREMISE" in text


def test_premise_is_the_block_with_its_heading():
    assert premise_for(ev("body", "Table 3-1")) == "(Table 3-1)\nbody"
    assert premise_for(ev("body")) == "body"


def test_a_long_block_is_cut_around_the_quote():
    text = "a" * 5000 + "QUOTE" + "b" * 5000
    out = premise_for(ev(text), (5000, 5005))
    assert "QUOTE" in out and len(out) == PREMISE_CHARS


def test_premise_holds_what_comes_before():
    out = premise_for(ev("Step 1. Check filter", "Table 3-1"), lead_in="Black smoke.")
    assert out == "(Table 3-1)\nBlack smoke.\nStep 1. Check filter"


def test_a_row_is_judged_with_the_rows_above_it(ctx):
    from manualqa.retrieve import lead_in, row_evidence

    hits = ctx.tables.lookup_table(query="P14-8969", limit=1)
    text = lead_in(ctx, row_evidence(hits[0]))
    assert text and "P14-8969" not in text


def test_a_block_is_judged_with_the_text_before_it():
    from types import SimpleNamespace

    from manualqa.blocks import Block
    from manualqa.retrieve import lead_in

    box = Box(0, 0, 1, 1)
    stem = Block("a", "text", "To self-test the panel:", box)
    step = Block("b", "text", "Place switch to RUN.", box)
    page = SimpleNamespace(
        blocks={"a": stem, "b": step}, page_blocks={("m", 1): ["a", "b"]}
    )
    e = Evidence("b", "text", "m", 1, "b", step.text, [box])
    assert lead_in(page, e) == "To self-test the panel:"
