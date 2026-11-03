"""Writes the recording the frontend's end-to-end check replays (frontend/e2e/run.sh).

Skipped unless MANUALQA_E2E_OUT names an output directory. The answers come from the real
answer path over the fixture ingest, with a scripted generator: one answer with a verified
parts-row claim and the CAGE-code trap (removed by the fact check), and one abstention.
"""

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_answer import FakeGen, Q, claim, row_id

from manualqa.server import create_app

ROOT = Path(__file__).resolve().parents[2]
PARTS = "Army_5kW_Generator_Parts_Manual.pdf"
ABSTAIN_Q = "What is the torque for the cylinder head bolts?"
OUT = os.environ.get("MANUALQA_E2E_OUT")


@pytest.mark.skipif(not OUT, reason="set MANUALQA_E2E_OUT to write the e2e recording")
def test_write_e2e_recording(ctx):
    out = Path(OUT)
    rec = out / "rec"
    answered = FakeGen(
        [
            claim("The part number is P14-8969.", row_id(ctx), "P14-8969"),
            claim(
                "The part number of the filter element is 18265.", row_id(ctx), "18265"
            ),
        ]
    )
    # the UI sends the second question as a follow-up, with the first turn as history
    first = [
        {"role": "user", "content": Q},
        {"role": "assistant", "content": "The part number is P14-8969."},
    ]
    for gen, question, history in [
        (answered, Q, []),
        (FakeGen([]), ABSTAIN_Q, first),
    ]:
        app = create_app(ctx, gen, recordings=rec, manuals=ROOT / "manuals")
        r = TestClient(app).post(
            "/api/ask",
            json={"question": question, "manual": PARTS, "history": history},
        )
        assert r.status_code == 200
    (log,) = rec.glob("*.jsonl")
    shutil.copy(log, out / "recording.jsonl")
    shutil.copytree(Path(ctx.root) / "pages", out / "pages", dirs_exist_ok=True)
