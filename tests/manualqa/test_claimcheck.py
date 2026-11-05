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
