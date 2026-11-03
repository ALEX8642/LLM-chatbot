import json

from manualqa.generate import ClaimParser, Generator, build_messages
from manualqa.geometry import Box
from manualqa.retrieve import Evidence

LINE1 = json.dumps({"claim": "Trips at 15 psi.", "block": "b1", "quote": "15 psi"})
LINE2 = json.dumps({"claim": "Shuts down hot.", "block": "b2", "quote": "shut down"})


def feed_in_pieces(parser, text, size):
    out = []
    for i in range(0, len(text), size):
        out.append(parser.feed(text[i : i + size]))
    return out


def test_parser_streams_claims():
    parser = ClaimParser()
    text = LINE1 + "\n" + LINE2 + "\n"
    batches = feed_in_pieces(parser, text, 7)
    done = [c for batch in batches for c in batch]
    assert [c.block for c in done] == ["b1", "b2"]
    first_done = next(i for i, b in enumerate(batches) if b)
    assert (first_done + 1) * 7 >= len(LINE1) + 1  # returned once its line closed
    assert first_done * 7 < len(LINE1) + 1
    assert parser.close() == []


def test_parser_survives_garbage_and_split_lines():
    parser = ClaimParser()
    parser.feed("Here are the claims:\n")
    parser.feed('{"claim": "broken", "block": \n')
    claims = []
    for piece in (LINE1[:10], LINE1[10:30], LINE1[30:]):
        claims += parser.feed(piece)
    claims += parser.close()  # last line without a newline
    assert [c.block for c in claims] == ["b1"]
    assert len(parser.ignored) == 2


def test_parser_abstain():
    parser = ClaimParser()
    parser.feed('{"abstain": "the manual has no torque values"}\n')
    assert parser.abstain == "the manual has no torque values"


def test_parser_accepts_code_fences():
    parser = ClaimParser()
    claims = parser.feed("```json\n" + LINE1 + "\n```\n")
    assert [c.block for c in claims] == ["b1"]


def test_messages_include_images_and_ids(tmp_path):
    img = tmp_path / "p001-gen.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    ev = [
        Evidence(
            "m:p1:b0", "text", "m.pdf", 1, "m:p1:b0", "Use diesel.", [Box(0, 0, 1, 1)]
        ),
        Evidence("m:p2:b3:r4", "row", "m.pdf", 2, "m:p2:b3", "ITEM: 4", []),
    ]
    msgs = build_messages("Which fuel?", [], ev, [img])
    user = msgs[-1]["content"]
    text = " ".join(p["text"] for p in user if p["type"] == "text")
    assert "[m:p1:b0]" in text and "[m:p2:b3:r4]" in text and "Which fuel?" in text
    images = [p for p in user if p["type"] == "image_url"]
    assert images and images[0]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )
    assert msgs[0]["role"] == "system"


class FakeResponse:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)


class FakeSession:
    def __init__(self, lines):
        self.lines, self.sent = lines, None

    def post(self, url, json, headers, stream, timeout):
        self.sent = json
        return FakeResponse(self.lines)


def test_generator_parses_sse():
    chunks = [{"choices": [{"delta": {"content": t}}]} for t in ("Hel", "lo", "")]
    lines = [f"data: {json.dumps(c)}" for c in chunks] + ["", "data: [DONE]"]
    session = FakeSession(lines)
    gen = Generator("http://gateway", "key", "model-x", session=session)
    assert "".join(gen.stream([{"role": "user", "content": "hi"}])) == "Hello"
    assert session.sent["stream"] is True and session.sent["temperature"] == 0
