import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_answer import FakeGen, Q, claim, row_id

from manualqa.server import create_app

ROOT = Path(__file__).resolve().parents[2]
PARTS = "Army_5kW_Generator_Parts_Manual.pdf"


def events(response):
    out = []
    for frame in response.text.split("\n\n"):
        if not frame.strip():
            continue
        lines = dict(line.split(": ", 1) for line in frame.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture
def client(ctx, tmp_path):
    gen = FakeGen(
        [
            claim("The part number is P14-8969.", row_id(ctx), "P14-8969"),
            claim(
                "The part number of the filter element is 18265.", row_id(ctx), "18265"
            ),
        ]
    )
    app = create_app(ctx, gen, recordings=tmp_path / "rec", manuals=ROOT / "manuals")
    return TestClient(app), gen, tmp_path / "rec"


def ask(client, **extra):
    body = {"question": Q, "manual": PARTS, "history": [], **extra}
    return client.post("/api/ask", json=body)


def test_ask_streams_events_in_order(client):
    c, _, _ = client
    resp = ask(c)
    assert resp.headers["content-type"].startswith("text/event-stream")
    kinds = [k for k, _ in events(resp)]
    assert kinds[0] == "retrieved" and kinds[-1] == "done"
    assert kinds.index("claim_shown") < kinds.index("claim_settled")
    assert "claim_removed" in kinds


def test_event_payload_has_boxes(client):
    c, _, _ = client
    settled = [d for k, d in events(ask(c)) if k == "claim_settled"]
    (s,) = settled
    assert s["page"] == 59 and s["status"] == "verified"
    assert s["boxes"] and set(s["boxes"][0]) == {"x0", "y0", "x1", "y1"}
    done = [d for k, d in events(ask(c)) if k == "done"][0]
    assert done["abstained"] is False and done["removed"] == 1


def test_pages_served(client):
    c, _, _ = client
    resp = c.get("/api/pages/Army_5kW_Generator_Parts_Manual/59")
    assert resp.status_code == 200 and resp.headers["content-type"] == "image/jpeg"
    assert c.get("/api/pages/Army_5kW_Generator_Parts_Manual/999").status_code == 404
    assert c.get("/api/pages/..%2Fsecrets/1").status_code == 404


def test_manuals_listed(client):
    c, _, _ = client
    manuals = {m["file"]: m for m in c.get("/api/manuals").json()}
    assert PARTS in manuals
    assert "Repair Parts" in manuals[PARTS]["title"]


def test_answer_recorded(client):
    c, _, rec = client
    ask(c)
    (log,) = list(rec.glob("*.jsonl"))
    entry = json.loads(log.read_text().splitlines()[-1])
    assert entry["question"] == Q and entry["manual"] == PARTS
    assert entry["events"][-1]["event"] == "done"


def test_follow_up_sends_history(client):
    c, gen, _ = client
    history = [
        {"role": "user", "content": "Tell me about the air cleaner."},
        {"role": "assistant", "content": "It is in figure 15."},
    ]
    resp = ask(c, history=history)
    retrieved = [d for k, d in events(resp) if k == "retrieved"][0]
    assert retrieved["standalone_question"]  # the rewritten question is reported
    assert gen.calls == 2
