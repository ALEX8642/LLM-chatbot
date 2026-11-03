import json

from test_answer import FakeGen, Q, claim, row_id

from evals import run_eval

PARTS = "Army_5kW_Generator_Parts_Manual.pdf"


def test_v2_adapter_record_fields(ctx):
    rid = row_id(ctx)
    gen = FakeGen(
        [
            claim("The part number is P14-8969.", rid, "P14-8969"),
            claim("The part number of the filter element is 18265.", rid, "18265"),
        ]
    )
    run = run_eval.make_v2_adapter(ctx=ctx, gen=gen, config={"generator": "fake"})
    out = run(Q, PARTS)
    for key in ("answer", "ranked_pages", "candidate_pages", "cited_pages", "context"):
        assert key in out
    assert out["cited_pages"] == [59]
    assert out["abstained"] is False and out["unknown_blocks"] == 0
    assert [c["status"] for c in out["claims"]] == ["verified"]
    assert out["removed"][0]["reason"].startswith("value 18265 in column")
    assert rid in out["context"]
    assert out["timings"]["total_s"] >= out["timings"]["retrieval_s"] >= 0
    assert run.config["system"] == "v2" and run.config["generator"] == "fake"
    json.dumps(out)  # the raw file must be JSON
