"""HTTP API for the UI: answers as server-sent events, page renders, manuals, and a
replay mode that serves recorded answers without any model.

    uv run python -m manualqa.server --ingest data/ingest [--replay FILE] [--port 8000]
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pymupdf
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from manualqa.answer import AnswerEvent, answer_stream
from manualqa.render import render_manual
from manualqa.textnorm import norm

REPLAY_GAP_S = 0.3
MAX_QUESTION_CHARS, MAX_TURN_CHARS, MAX_TURNS = 2000, 8000, 20
_ONE_AT_A_TIME = threading.Lock()  # one GPU, one table store connection


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_TURN_CHARS)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    manual: str
    history: list[Turn] = Field(default=[], max_length=MAX_TURNS)


def _payload(event: AnswerEvent) -> dict:
    if event.claim is not None:
        return asdict(event.claim)
    if event.answer is not None:
        a = event.answer
        return {
            "text": a.text,
            "abstained": a.abstained,
            "abstain_reason": a.abstain_reason,
            "removed": len(a.removed),
            "pages": a.retrieval.ranked_pages,
            "timings": {k: round(v, 3) for k, v in a.timings.items()},
        }
    return event.data


def _frame(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def read_manuals(manuals: Path) -> list[dict]:
    """Manuals from the table in manuals/SOURCES.md: file, title, pages."""
    out = []
    sources = manuals / "SOURCES.md"
    for line in sources.read_text().splitlines() if sources.exists() else []:
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 3 and cols[0].startswith("`") and cols[0].endswith(".pdf`"):
            title = re.sub(r"[*_]", "", cols[1])
            out.append(
                {"file": cols[0].strip("`"), "title": title, "pages": int(cols[2])}
            )
    return out


def _replay_key(manual: str, question: str, history: list) -> tuple:
    return manual, norm(question), len(history)


def create_app(
    ctx,
    gen,
    recordings: Path,
    manuals: Path = Path("manuals"),
    replay: Path | None = None,
    pages_dir: Path | None = None,
    checker=None,
    record: bool = True,
) -> FastAPI:
    app = FastAPI(title="manualqa")
    catalogue = read_manuals(Path(manuals))
    pages_root = (
        Path(pages_dir) if pages_dir else (Path(ctx.root) / "pages" if ctx else None)
    )
    recorded: dict[tuple, list[dict]] = {}
    if replay:
        for line in Path(replay).read_text().splitlines():
            if line.strip():
                entry = json.loads(line)
                key = _replay_key(entry["manual"], entry["question"], entry["history"])
                recorded[key] = entry["events"]
        files = {k[0] for k in recorded}
        catalogue = [m for m in catalogue if m["file"] in files]
    stems = {Path(m["file"]).stem for m in catalogue}
    app.state.pages_root = pages_root

    @app.get("/api/manuals")
    def manuals_list() -> list[dict]:
        return catalogue

    @app.get("/api/pages/{stem}/{page}")
    def page_image(stem: str, page: int) -> FileResponse:
        path = pages_root / stem / f"p{page:03d}.jpg" if pages_root else None
        if stem not in stems or path is None:
            raise HTTPException(404, "no such page")
        if not path.exists():  # a fresh clone has the manuals but no renders yet
            pdf = Path(manuals) / f"{stem}.pdf"
            with pymupdf.open(pdf) as doc:
                count = len(doc)
            if not 1 <= page <= count:
                raise HTTPException(404, "no such page")
            render_manual(pdf, pages_root, [page])
        return FileResponse(path, media_type="image/jpeg")

    def live(req: AskRequest):
        history = [t.model_dump() for t in req.history]
        log = []
        try:
            with _ONE_AT_A_TIME:
                for event in answer_stream(
                    req.question, req.manual, ctx, gen, history, checker
                ):
                    data = _payload(event)
                    log.append(
                        {"event": event.kind, "data": data, "t": time.monotonic()}
                    )
                    yield _frame(event.kind, data)
        except Exception as e:  # the client must not keep showing unchecked claims
            data = {"message": f"The answer failed before it was checked ({e})."}
            log.append({"event": "error", "data": data, "t": time.monotonic()})
            yield _frame("error", data)
        if not record:
            return
        start = log[0]["t"] if log else 0
        for e in log:
            e["t"] = round(e["t"] - start, 3)
        recordings.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with (recordings / f"{day}.jsonl").open("a", encoding="utf-8") as f:
            entry = {
                "question": req.question,
                "manual": req.manual,
                "history": history,
                "events": log,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def replayed(req: AskRequest):
        events = recorded.get(_replay_key(req.manual, req.question, req.history))
        if events is None:
            yield _frame(
                "done",
                {
                    "text": "This question is not in the recording.",
                    "replay_miss": True,
                    "abstained": True,
                },
            )
            return
        previous = 0.0
        for e in events:
            time.sleep(min(REPLAY_GAP_S, max(0.0, e.get("t", 0) - previous)))
            previous = e.get("t", 0)
            yield _frame(e["event"], e["data"])

    @app.post("/api/ask")
    def ask(req: AskRequest) -> StreamingResponse:
        stream = replayed(req) if replay else live(req)
        return StreamingResponse(stream, media_type="text/event-stream")

    return app


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ingest", type=Path, default=Path("data/ingest"))
    ap.add_argument("--manuals", type=Path, default=Path("manuals"))
    ap.add_argument("--recordings", type=Path, default=Path("data/recordings"))
    ap.add_argument("--replay", type=Path)
    ap.add_argument("--embedder", default="st:Qwen/Qwen3-Embedding-0.6B")
    ap.add_argument("--reranker", default="qwen:Qwen/Qwen3-Reranker-4B")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument(
        "--no-record", action="store_true", help="do not keep questions and answers"
    )
    args = ap.parse_args(argv)
    ctx = gen = checker = None
    if not args.replay:
        from manualqa.claimcheck import LLMChecker
        from manualqa.generate import Generator
        from manualqa.index import make_embedder
        from manualqa.retrieve import IngestContext, make_reranker

        ctx = IngestContext.load(
            args.ingest,
            make_embedder(args.embedder),
            make_reranker(args.reranker, batch_size=2),
        )
        gen = Generator.from_env()
        checker = LLMChecker(gen)
    app = create_app(
        ctx,
        gen,
        args.recordings,
        args.manuals,
        args.replay,
        pages_dir=args.ingest / "pages",
        checker=checker,
        record=not args.no_record,
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
