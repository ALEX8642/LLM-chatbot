"""Run v2 with its generator answered from a response cache, so a paid model can be used at
batch prices without changing the pipeline.

Each round runs every unfinished question through the unchanged answer path. A model call
missing from the cache stops that question and is queued; the queue is then answered by the
backend and the round repeats. Each round reaches one call further (answer, then the meaning
checks), so three or four rounds finish every question. The answers are those the live
pipeline gives with the same model responses.

    python -m evals.batch_run --ingest DIR --qa FILE --cache CACHE.jsonl --out RAW.json \\
        --backend anthropic-batch [--model claude-opus-5-5] [--limit N] [--count-only]

Backends: ``anthropic-batch`` (Message Batches API), ``anthropic-live`` (Messages API, for
checks), ``openai-live`` (the GEN_* endpoint, to show the runner matches the live pipeline).
``--count-only`` prices the first round with Anthropic's free token counter and sends nothing.
ANTHROPIC_API_KEY is read from the environment and never written anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# ANTHROPIC_BASE_URL can point at evals/anthropic_stub.py for a free dry run
ANTHROPIC = (
    os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    + "/v1"
)
VERSION = "2026-10-21"  # as in the Message Batches docs
MAX_TOKENS = 2048
# A batch may hold 256 MB; page images make requests large, so batches are cut well below it
BATCH_BYTES = 150_000_000


class Pending(Exception):
    """A model call the cache cannot answer yet."""


def request_key(messages: list[dict], model: str) -> str:
    blob = json.dumps({"model": model, "messages": messages}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class CachedGenerator:
    """The pipeline's generator interface, answered from a cache; misses are queued."""

    def __init__(self, model: str, cache: dict[str, dict]):
        self.model, self.cache = model, cache
        self.pending: dict[str, list[dict]] = {}

    def stream(self, messages: list[dict]):
        key = request_key(messages, self.model)
        hit = self.cache.get(key)
        if hit is None or hit.get("text") is None:
            self.pending[key] = messages
            raise Pending(key)
        yield hit["text"]

    def complete(self, messages: list[dict]) -> str:
        return "".join(self.stream(messages))


def to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    """OpenAI-style chat messages as Anthropic's system text and message list."""
    system, out = [], []
    for m in messages:
        if m["role"] == "system":
            system.append(m["content"])
            continue
        content = m["content"]
        if isinstance(content, str):
            parts = [{"type": "text", "text": content}]
        else:
            parts = []
            for p in content:
                if p["type"] == "text":
                    parts.append({"type": "text", "text": p["text"]})
                elif p["type"] == "image_url":
                    head, data = p["image_url"]["url"].split(",", 1)
                    media = head.split(":", 1)[1].split(";", 1)[0]
                    parts.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media,
                                "data": data,
                            },
                        }
                    )
                else:
                    raise ValueError(f"unsupported content part {p['type']!r}")
        out.append({"role": m["role"], "content": parts})
    return "\n\n".join(system), out


def anthropic_params(messages: list[dict], model: str) -> dict:
    system, msgs = to_anthropic(messages)
    params = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "messages": msgs,
    }
    if system:
        params["system"] = system
    return params


def _text(message: dict) -> str:
    return "".join(
        b.get("text", "") for b in message.get("content", []) if b.get("type") == "text"
    )


class Anthropic:
    def __init__(self, model: str, session=None, ledger: Path | None = None):
        import requests

        self.model, self.ledger = model, ledger
        self.http = session or requests.Session()
        self.http.headers.update(
            {
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": VERSION,
                "content-type": "application/json",
            }
        )

    def _post(self, path: str, body: dict, tries: int = 8) -> dict:
        """POST, waiting out rate limits (429) and overload (529) with backoff."""
        for attempt in range(tries):
            r = self.http.post(f"{ANTHROPIC}{path}", json=body, timeout=300)
            if r.status_code in (429, 529) and attempt < tries - 1:
                wait = float(r.headers.get("retry-after") or 2 ** (attempt + 1))
                time.sleep(min(wait, 120))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"{path}: HTTP {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError(f"{path}: still rate limited after {tries} tries")

    def count(self, pending: dict[str, list[dict]]) -> int:
        total = 0
        for messages in pending.values():
            p = anthropic_params(messages, self.model)
            p.pop("max_tokens"), p.pop("temperature")
            total += self._post("/messages/count_tokens", p)["input_tokens"]
            time.sleep(0.7)  # the counter allows 100 requests a minute
        return total

    def live(self, pending: dict[str, list[dict]]) -> dict[str, dict]:
        out = {}
        for key, messages in pending.items():
            msg = self._post("/messages", anthropic_params(messages, self.model))
            out[key] = {
                "text": _text(msg),
                "usage": msg.get("usage"),
                "stop": msg.get("stop_reason"),
            }
        return out

    def batch(
        self, pending: dict[str, list[dict]], poll_s: int = 60
    ) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for chunk in split_by_size(
            [
                {"custom_id": key, "params": anthropic_params(m, self.model)}
                for key, m in pending.items()
            ]
        ):
            out.update(self._one_batch(chunk, poll_s))
        return out

    def _note(self, entry: dict) -> None:
        if self.ledger is not None:
            with self.ledger.open("a") as f:
                f.write(json.dumps(entry) + "\n")

    def uncollected(self) -> list[str]:
        """Batches submitted by an earlier run whose results were never collected."""
        if self.ledger is None or not self.ledger.exists():
            return []
        entries = [json.loads(x) for x in self.ledger.read_text().splitlines() if x]
        done = {e["id"] for e in entries if e.get("collected")}
        return [e["id"] for e in entries if "submitted" in e and e["id"] not in done]

    def recover(self, poll_s: int = 60) -> dict[str, dict]:
        """Collect batches an interrupted run paid for, so they are never sent twice."""
        out: dict[str, dict] = {}
        for bid in self.uncollected():
            print(f"  collecting batch {bid} from an earlier run", flush=True)
            out.update(self._collect(bid, poll_s))
        return out

    def _one_batch(self, requests_: list[dict], poll_s: int) -> dict[str, dict]:
        bid = self._post("/messages/batches", {"requests": requests_})["id"]
        self._note({"id": bid, "submitted": len(requests_)})
        print(f"  batch {bid}: {len(requests_)} requests submitted", flush=True)
        return self._collect(bid, poll_s)

    def _collect(self, bid: str, poll_s: int) -> dict[str, dict]:
        while True:
            r = self.http.get(f"{ANTHROPIC}/messages/batches/{bid}", timeout=60)
            r.raise_for_status()
            status = r.json()
            if status["processing_status"] == "ended":
                break
            print(f"  batch {bid}: {status['request_counts']}", flush=True)
            time.sleep(poll_s)
        res = self.http.get(status["results_url"], timeout=300)
        res.raise_for_status()
        out, invalid = {}, []
        for line in res.text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            result = row["result"]
            if result["type"] == "succeeded":
                msg = result["message"]
                out[row["custom_id"]] = {
                    "text": _text(msg),
                    "usage": msg.get("usage"),
                    "stop": msg.get("stop_reason"),
                }
                continue
            error = (
                (result.get("error") or {}).get("error") or result.get("error") or {}
            )
            print(f"  {row['custom_id'][:12]}: {result['type']} {error}", flush=True)
            if error.get("type") == "invalid_request_error":
                invalid.append(error.get("message", ""))
        self._note({"id": bid, "collected": True})
        if invalid:  # the same request would fail again: stop rather than resend it
            sys.exit(f"{len(invalid)} invalid requests, first: {invalid[0]}")
        return out  # server errors, cancels and expiries are left out and asked again


def hybrid(batch, live, below: int):
    """Batches for the bulk; a round's last few calls live, so one long answer's claim checks
    (one per round) do not each wait for a batch."""

    def fill(pending: dict[str, list[dict]]) -> dict[str, dict]:
        return live(pending) if len(pending) < below else batch(pending)

    return fill


def split_by_size(requests_: list[dict], limit: int = BATCH_BYTES) -> list[list[dict]]:
    """Requests in batches under the size limit, in order."""
    chunks, current, size = [], [], 0
    for req in requests_:
        n = len(json.dumps(req))
        if current and size + n > limit:
            chunks.append(current)
            current, size = [], 0
        current.append(req)
        size += n
    return chunks + ([current] if current else [])


def openai_live(pending: dict[str, list[dict]]) -> dict[str, dict]:
    from manualqa.generate import Generator

    gen = Generator.from_env()
    return {
        key: {"text": gen.complete(m), "usage": None, "stop": None}
        for key, m in pending.items()
    }


def load_cache(path: Path) -> dict[str, dict]:
    cache = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                cache[row["key"]] = row
    return cache


def append_cache(path: Path, model: str, answers: dict[str, dict]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for key, a in answers.items():
            f.write(
                json.dumps({"key": key, "model": model, **a}, ensure_ascii=False) + "\n"
            )


def run_rounds(
    qa: list[dict],
    run: Callable[[str, str], dict],
    gen: CachedGenerator,
    fill: Callable[[dict], dict],
    cache_path: Path,
    max_rounds: int = 60,
    count: Callable[[dict], int] | None = None,
) -> list[dict] | None:
    """Rows in question order once every question finishes; None if only counting."""
    done: dict[str, dict] = {}
    for rnd in range(1, max_rounds + 1):
        gen.pending.clear()
        for item in qa:
            if item["id"] in done:
                continue
            try:
                done[item["id"]] = {
                    "id": item["id"],
                    **run(item["question"], item["manual"]),
                    "error": None,
                }
            except Pending:
                pass
        print(
            f"round {rnd}: {len(done)}/{len(qa)} finished, {len(gen.pending)} calls queued",
            flush=True,
        )
        if not gen.pending:
            return [done[item["id"]] for item in qa]
        if count is not None:
            print(f"first-round input tokens: {count(gen.pending)}", flush=True)
            return None
        answers = fill(dict(gen.pending))
        gen.cache.update(answers)
        append_cache(cache_path, gen.model, answers)
    sys.exit(f"stopped after {max_rounds} rounds with calls still queued")


def main(argv: list[str] | None = None) -> int:
    from evals.run_eval import load_qa, make_v2_adapter, sha256_file

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ingest", type=Path, required=True)
    ap.add_argument("--qa", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--backend",
        choices=["anthropic-batch", "anthropic-live", "openai-live"],
        required=True,
    )
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--count-only", action="store_true")
    ap.add_argument(
        "--live-below",
        type=int,
        default=10,
        help="answer rounds with fewer queued calls live instead of as a batch",
    )
    args = ap.parse_args(argv)

    qa = load_qa(args.qa)[: args.limit] if args.limit else load_qa(args.qa)
    model = os.environ["GEN_MODEL"] if args.backend == "openai-live" else args.model
    gen = CachedGenerator(model, load_cache(args.cache))
    run = make_v2_adapter(
        args.ingest, gen=gen, config={"generator": model, "batch_runner": args.backend}
    )
    count = fill = None
    if args.backend == "openai-live":
        fill = openai_live
    else:
        client = Anthropic(model, ledger=args.cache.with_suffix(".batches.jsonl"))
        recovered = client.recover()
        if recovered:
            gen.cache.update(recovered)
            append_cache(args.cache, model, recovered)
        if args.backend == "anthropic-batch":
            fill = hybrid(client.batch, client.live, args.live_below)
        else:
            fill = client.live
        count = client.count if args.count_only else None
    rows = run_rounds(qa, run, gen, fill, args.cache, count=count)
    if rows is None:
        return 0
    usage = [r for r in gen.cache.values() if r.get("usage")]
    raw = {
        "kind": "raw",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "qa_file": args.qa.name,
        "qa_sha256": sha256_file(args.qa),
        "config": dict(run.config),
        "usage": {
            "calls": len(usage),
            "input_tokens": sum(r["usage"].get("input_tokens", 0) for r in usage),
            "output_tokens": sum(r["usage"].get("output_tokens", 0) for r in usage),
        },
        "repeats": [rows],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(raw, indent=2))
    print(f"wrote {args.out}: {raw['usage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
