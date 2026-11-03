import json
from pathlib import Path

from manualqa import ingest
from manualqa.chunks import load_chunks
from manualqa.tables import TableStore

ROOT = Path(__file__).resolve().parents[2]


def test_ingest_fixtures_end_to_end(tmp_path):
    out = tmp_path / "ingest"
    code = ingest.main(
        [
            "--raw",
            str(ROOT / "tests/fixtures/paddle-raw.jsonl"),
            "--manuals",
            str(ROOT / "manuals"),
            "--out",
            str(out),
            "--skip-index",
        ]
    )
    assert code == 0
    summary = json.loads((out / "summary.json").read_text())
    assert summary["pages"] == 6
    assert summary["text_source"] == {"text_layer": 3, "ocr": 3}
    assert summary["chunks"] == len(load_chunks(out / "chunks.jsonl")) > 0
    assert summary["tables"] == 2 and summary["rows"] > 30
    assert 0.9 < summary["row_boxes"] / summary["rows"] <= 1
    assert (out / "pages/Army_5kW_Generator_Parts_Manual/p059.jpg").exists()
    hits = TableStore(out / "tables.sqlite").lookup_table(query="P14-8969")
    assert hits and hits[0].page == 59
