import json

from manualqa.answer import _relocate, answer, answer_stream
from manualqa.retrieve import _block_evidence, retrieve

PARTS = "Army_5kW_Generator_Parts_Manual.pdf"
Q = "What is the part number of the air cleaner filter element, item 17 in figure 15?"


class FakeGen:
    """Replays canned output in small pieces, like a streaming endpoint."""

    model = "fake"

    def __init__(self, lines):
        self.text = "\n".join(json.dumps(x) for x in lines) + "\n"
        self.calls = 0

    def stream(self, messages):
        self.calls += 1
        for i in range(0, len(self.text), 9):
            yield self.text[i : i + 9]

    def complete(self, messages):
        return "".join(self.stream(messages))


def row_id(ctx):
    rows = [e for e in retrieve(Q, PARTS, ctx).evidence if e.kind == "row"]
    return next(e.id for e in rows if "P14-8969" in e.cells)


def claim(text, block, quote):
    return {"claim": text, "block": block, "quote": quote}


def test_verified_claim_has_boxes(ctx):
    rid = row_id(ctx)
    gen = FakeGen([claim("The part number is P14-8969.", rid, "P14-8969")])
    ans = answer(Q, PARTS, ctx, gen)
    assert not ans.abstained
    (c,) = ans.claims
    assert c.status == "verified" and c.boxes and c.page == 59
    assert "P14-8969" in ans.text


def test_wrong_quote_removed_with_reason(ctx):
    rid = row_id(ctx)
    gen = FakeGen([claim("The part number is R28.", rid, "R28")])
    ans = answer(Q, PARTS, ctx, gen)
    (c,) = ans.removed
    assert c.reason == "quote not in cited block" and ans.abstained


def test_cage_trap_removed(ctx):
    rid = row_id(ctx)
    gen = FakeGen(
        [
            claim("The part number of the filter element is 18265.", rid, "18265"),
            claim(
                "The part number of the filter element is P14-8969.", rid, "P14-8969"
            ),
        ]
    )
    ans = answer(Q, PARTS, ctx, gen)
    assert [c.claim for c in ans.claims] == [
        "The part number of the filter element is P14-8969."
    ]
    assert "FSCM" in ans.removed[0].reason


def test_abstains_when_no_claim_survives(ctx):
    gen = FakeGen([{"abstain": "no turbocharger in this manual"}])
    ans = answer("What is the part number of the turbocharger?", PARTS, ctx, gen)
    assert ans.abstained and ans.text.startswith("I could not find the answer")
    assert "59" in ans.text or "61" in ans.text  # lists pages it looked at


def test_unknown_block_dropped_and_counted(ctx):
    rid = row_id(ctx)
    gen = FakeGen(
        [
            claim("Made up.", "no:such:block", "x"),
            claim("The part number is P14-8969.", rid, "P14-8969"),
        ]
    )
    ans = answer(Q, PARTS, ctx, gen)
    assert ans.unknown_blocks == 1 and len(ans.claims) == 1


def test_stream_events_order(ctx):
    rid = row_id(ctx)
    gen = FakeGen(
        [
            claim("The part number is P14-8969.", rid, "P14-8969"),
            claim("The part number of the filter element is 18265.", rid, "18265"),
        ]
    )
    events = list(answer_stream(Q, PARTS, ctx, gen))
    kinds = [e.kind for e in events]
    assert kinds[0] == "retrieved" and kinds[-1] == "done"
    assert kinds.index("claim_shown") < kinds.index("claim_settled")
    shown = [e.claim.claim for e in events if e.kind == "claim_shown"]
    assert "The part number of the filter element is 18265." in shown  # quote matched
    removed = [e.claim.claim for e in events if e.kind == "claim_removed"]
    assert removed == ["The part number of the filter element is 18265."]


def test_history_triggers_one_rewrite(ctx):
    rid = row_id(ctx)
    gen = FakeGen([claim("The part number is P14-8969.", rid, "P14-8969")])
    history = [
        {"role": "user", "content": "Tell me about the air cleaner."},
        {"role": "assistant", "content": "It is in figure 15."},
    ]
    answer("And its filter element?", PARTS, ctx, gen, history=history)
    assert gen.calls == 2  # rewrite + answer


def _nearby_block(ctx):
    other = next(
        i
        for i, b in ctx.blocks.items()
        if ctx.block_page[i] == (PARTS, 59) and b.kind == "other" and b.text.strip()
    )
    return _block_evidence(ctx, other)


def test_a_quote_from_a_table_cited_to_a_nearby_block_moves_to_the_row(ctx):
    moved = _relocate("P14-8969 . .  FILTER ELEMENT", _nearby_block(ctx), ctx)
    assert moved is not None
    ev, match = moved
    assert ev.id == row_id(ctx) and match.boxes


def test_a_short_quote_is_not_moved(ctx):
    assert _relocate("P14-8969", _nearby_block(ctx), ctx) is None


class FakeChecker:
    def __init__(self, score):
        self.score, self.seen = score, []

    def supported(self, claim, premise):
        self.seen.append((claim, premise))
        return self.score


def test_a_claim_the_source_does_not_say_is_removed(ctx):
    rid = row_id(ctx)
    gen = FakeGen([claim("The part number is P14-8969.", rid, "P14-8969")])
    checker = FakeChecker(0.0)
    ans = answer(Q, PARTS, ctx, gen, checker=checker)
    assert ans.abstained and ans.removed[0].reason == "the source does not say this"
    assert len(checker.seen) == 2  # its block, then its page


def test_a_no_on_the_block_can_be_overturned_by_the_page(ctx):
    class PageSaysYes(FakeChecker):
        def supported(self, claim, premise):
            self.seen.append((claim, premise))
            return float(len(self.seen) == 2)

    rid = row_id(ctx)
    gen = FakeGen([claim("The part number is P14-8969.", rid, "P14-8969")])
    ans = answer(Q, PARTS, ctx, gen, checker=PageSaysYes(0.0))
    assert ans.claims[0].status == "verified"


def test_a_supported_claim_is_verified_and_judged_on_its_whole_row(ctx):
    rid = row_id(ctx)
    gen = FakeGen([claim("The part number is P14-8969.", rid, "P14-8969")])
    checker = FakeChecker(1.0)
    ans = answer(Q, PARTS, ctx, gen, checker=checker)
    assert ans.claims[0].status == "verified"
    assert "FILTER ELEMENT" in checker.seen[0][1] and ans.timings["meaning_s"] >= 0


def test_a_claim_that_fails_the_facts_is_not_sent_to_the_checker(ctx):
    rid = row_id(ctx)
    gen = FakeGen([claim("The part number is 99-99999.", rid, "P14-8969")])
    checker = FakeChecker(1.0)
    answer(Q, PARTS, ctx, gen, checker=checker)
    assert checker.seen == []


def test_figure_claims_are_not_sent_to_the_checker(ctx):
    fig = next(
        (i for i, b in ctx.blocks.items() if b.kind == "figure" and b.text.strip()),
        None,
    )
    if fig is None:
        return
    checker = FakeChecker(0.0)
    answer(Q, PARTS, ctx, FakeGen([claim("A figure claim.", fig, "")]), checker=checker)
    assert checker.seen == []
