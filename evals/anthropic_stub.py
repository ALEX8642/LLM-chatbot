"""A local stand-in for Anthropic's Messages, token-count and Message Batches endpoints,
answered by the OpenAI-compatible GEN_* endpoint, for a free dry run of evals/batch_run.py.

    uvicorn evals.anthropic_stub:app --port 8099
    ANTHROPIC_BASE_URL=http://127.0.0.1:8099 ANTHROPIC_API_KEY=stub python -m evals.batch_run ...

It accepts Anthropic-format requests, converts them back to OpenAI format (system text,
base64 image blocks), and returns Anthropic-format results, so the runner's submit, poll,
result and conversion code all run as they would against the real service.
"""

from __future__ import annotations

import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI(title="anthropic stub")
_batches: dict[str, dict] = {}


def _to_openai(params: dict) -> list[dict]:
    system = params.get("system")
    if isinstance(system, list):  # text blocks, as sent with --prompt-cache
        system = "".join(b["text"] for b in system)
    messages = [{"role": "system", "content": system}] if system else []
    for m in params["messages"]:
        parts = []
        for b in m["content"]:
            if b["type"] == "text":
                parts.append({"type": "text", "text": b["text"]})
            elif b["type"] == "image":
                src = b["source"]
                url = f"data:{src['media_type']};base64,{src['data']}"
                parts.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": m["role"], "content": parts})
    return messages


def _answer(params: dict) -> dict:
    from manualqa.generate import Generator

    if "temperature" in params or not params.get("max_tokens"):  # as Opus 5.5 does
        raise ValueError(
            "temperature: Extra inputs are not permitted; max_tokens required"
        )
    text = Generator.from_env().complete(_to_openai(params))
    chars = sum(len(str(m)) for m in params["messages"])
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": chars // 4, "output_tokens": len(text) // 4},
    }


@app.post("/v1/messages")
def messages(params: dict) -> dict:
    return _answer(params)


@app.post("/v1/messages/count_tokens")
def count_tokens(params: dict) -> dict:
    return {"input_tokens": sum(len(str(m)) for m in params["messages"]) // 4}


def _process(bid: str) -> None:
    batch = _batches[bid]
    for req in batch["requests"]:
        try:
            result = {"type": "succeeded", "message": _answer(req["params"])}
        except Exception as e:  # reported per request, as the real service does
            result = {"type": "errored", "error": {"message": str(e)}}
        batch["results"].append({"custom_id": req["custom_id"], "result": result})
    batch["status"] = "ended"


@app.post("/v1/messages/batches")
def create(body: dict) -> dict:
    ids = [r["custom_id"] for r in body["requests"]]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "custom_id values must be unique")
    bid = f"msgbatch_stub_{uuid.uuid4().hex[:12]}"
    _batches[bid] = {
        "requests": body["requests"],
        "results": [],
        "status": "in_progress",
    }
    threading.Thread(target=_process, args=(bid,), daemon=True).start()
    return {"id": bid, "processing_status": "in_progress"}


@app.get("/v1/messages/batches/{bid}")
def status(bid: str) -> dict:
    b = _batches[bid]
    done = len(b["results"])
    return {
        "id": bid,
        "processing_status": b["status"],
        "request_counts": {"processing": len(b["requests"]) - done, "succeeded": done},
        "results_url": f"http://127.0.0.1:8099/v1/messages/batches/{bid}/results",
    }


@app.get("/v1/messages/batches/{bid}/results", response_class=PlainTextResponse)
def results(bid: str) -> str:
    import json

    return "\n".join(json.dumps(r) for r in _batches[bid]["results"])
