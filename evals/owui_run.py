"""Ask the eval questions of a stock Open WebUI knowledge base, with the same generator as v2,
and write a raw file the grader reads (docs/prereg-owui.md).

    OWUI_URL=http://host:port OWUI_API_KEY=... python -m evals.owui_run kb NAME PDF [PDF ...]
    OWUI_URL=... OWUI_API_KEY=... python -m evals.owui_run ask --kb ID --qa FILE --out RAW.json \\
        [--repeats 3] [--limit N]

``kb`` uploads the PDFs, waits for Open WebUI to extract and embed each one with its own
settings, and adds them to a new knowledge base, printing its id. ``--split N`` uploads a PDF
longer than N pages as parts of N pages ("Manual__p041-060.pdf"): Open WebUI's Docling call
gives up after 120 s, which a 114-page manual exceeds. Pages are mapped back to the whole PDF. ``ask`` puts each question to
a fresh conversation with that knowledge base attached. The judge's cited source is the text of
the chunks the answer cites by [id], or of every chunk it was given if it cites none.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

MODEL = "Qwen3.8-Flash-Next-NVFP4-Fast"  # v2's generator, through the same gateway
# v2's generation settings (manualqa/generate.py); everything else is left as Open WebUI has it
PARAMS = {
    "temperature": 0,
    "seed": 0,
    "chat_template_kwargs": {"enable_thinking": False},
}
_PART = re.compile(r"__p(\d{3})-\d{3}\.pdf$")
_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class Client:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.http = requests.Session()
        self.http.headers["Authorization"] = f"Bearer {key}"

    def _ok(self, resp: requests.Response) -> dict:
        resp.raise_for_status()
        return resp.json()

    def upload(self, path: Path) -> str:
        with path.open("rb") as f:
            files = {"file": (path.name, f, "application/pdf")}
            return self._ok(self.http.post(f"{self.url}/api/v1/files/", files=files))[
                "id"
            ]

    def wait(self, file_id: str, poll_s: int = 10, limit_s: int = 7200) -> str:
        for _ in range(limit_s // poll_s):
            got = self._ok(
                self.http.get(f"{self.url}/api/v1/files/{file_id}/process/status")
            )
            if got.get("status") in ("completed", "failed"):
                return got["status"]
            time.sleep(poll_s)
        return "timeout"

    def knowledge(self, name: str, description: str) -> str:
        body = {"name": name, "description": description}
        return self._ok(
            self.http.post(f"{self.url}/api/v1/knowledge/create", json=body)
        )["id"]

    def add(self, kb: str, file_id: str) -> None:
        self._ok(
            self.http.post(
                f"{self.url}/api/v1/knowledge/{kb}/file/add", json={"file_id": file_id}
            )
        )

    def ask(self, kb: str, question: str) -> dict:
        body = {
            "model": MODEL,
            "messages": [{"role": "user", "content": question}],
            "files": [{"type": "collection", "id": kb}],
            "stream": False,
            **PARAMS,
        }
        return self._ok(
            self.http.post(f"{self.url}/api/chat/completions", json=body, timeout=600)
        )


def chunks(sources: list[dict]) -> list[dict]:
    """Every chunk the answer was given, with the [id] the prompt shows it under. Open WebUI
    numbers sources by file, from 1, in order (utils/middleware.py get_source_context), so all
    chunks of one PDF share an id."""
    out, ids = [], {}
    for src in sources or []:
        for text, meta in zip(src.get("document") or [], src.get("metadata") or []):
            meta = meta or {}
            key = meta.get("source") or (src.get("source") or {}).get("id") or "N/A"
            ids.setdefault(key, len(ids) + 1)
            out.append({"text": text, "meta": meta, "id": ids[key]})
    return out


def cited(answer: str, given: list[dict]) -> list[dict]:
    """The chunks under the [id]s the answer cites; all of them if it cites none."""
    ids = {int(n) for m in _CITE.finditer(answer) for n in m.group(1).split(",")}
    return [c for c in given if c["id"] in ids] or given


def split(pdf: Path, pages: int, out_dir: Path) -> list[Path]:
    import pymupdf

    doc = pymupdf.open(pdf)
    if doc.page_count <= pages:
        return [pdf]
    parts = []
    for start in range(0, doc.page_count, pages):
        end = min(start + pages, doc.page_count)
        part = pymupdf.open()
        part.insert_pdf(doc, from_page=start, to_page=end - 1)
        path = out_dir / f"{pdf.stem}__p{start + 1:03d}-{end:03d}.pdf"
        part.save(path)
        parts.append(path)
    return parts


def page_of(meta: dict) -> int | None:
    """The 1-based page in the whole PDF: Open WebUI counts a file's pages from 0."""
    if not str(meta.get("page", "")).isdigit():
        return None
    part = _PART.search(meta.get("name") or "")
    return int(meta["page"]) + (int(part.group(1)) if part else 1)


def record(item: dict, reply: dict, seconds: float) -> dict:
    answer = reply["choices"][0]["message"]["content"] or ""
    given = chunks(reply.get("sources") or [])
    use = cited(answer, given)
    pages = sorted({p for c in use if (p := page_of(c["meta"])) is not None})
    return {
        "id": item["id"],
        "answer": answer,
        "cited_pages": pages,
        "cited_text": "\n\n".join(c["text"] for c in use),
        "chunks_given": len(given),
        "cites": bool(_CITE.search(answer)),
        "sources": [
            {"name": c["meta"].get("name"), "page": c["meta"].get("page")}
            for c in given
        ],
        "timings": {"total_s": round(seconds, 2)},
        "error": None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kb")
    k.add_argument("name")
    k.add_argument("pdfs", nargs="+", type=Path)
    k.add_argument("--split", type=int, help="upload PDFs longer than this as parts")
    a = sub.add_parser("ask")
    a.add_argument("--kb", required=True)
    a.add_argument("--qa", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--repeats", type=int, default=3)
    a.add_argument("--limit", type=int)
    args = ap.parse_args(argv)
    client = Client(os.environ["OWUI_URL"], os.environ["OWUI_API_KEY"])

    if args.cmd == "kb":
        kb = client.knowledge(args.name, "LLM-chatbot evaluation (docs/prereg-owui.md)")
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        uploads = [
            part
            for pdf in args.pdfs
            for part in (split(pdf, args.split, tmp) if args.split else [pdf])
        ]
        for pdf in uploads:
            fid = client.upload(pdf)
            status = client.wait(fid)
            print(f"{pdf.name}: {status}", flush=True)
            if status != "completed":
                return 1
            client.add(kb, fid)
        print(f"knowledge base {kb}")
        return 0

    items = [
        json.loads(line) for line in args.qa.read_text().splitlines() if line.strip()
    ]
    items = items[: args.limit] if args.limit else items
    # every answer is saved as it comes, and a restarted run picks up where it stopped
    partial = args.out.with_suffix(".partial.jsonl")
    done = {}
    if partial.exists():
        for line in partial.read_text().splitlines():
            got = json.loads(line)
            done[(got["repeat"], got["row"]["id"])] = got["row"]
    repeats = []
    for r in range(1, args.repeats + 1):
        rows = []
        for n, item in enumerate(items, 1):
            if (r, item["id"]) in done:
                rows.append(done[(r, item["id"])])
                continue
            start = time.perf_counter()
            try:
                reply = client.ask(args.kb, item["question"])
                row = record(item, reply, time.perf_counter() - start)
            except (requests.RequestException, KeyError, ValueError) as e:
                row = {"id": item["id"], "answer": "", "cited_pages": [],
                       "cited_text": "", "error": str(e)[:300]}  # fmt: skip
            rows.append(row)
            with partial.open("a") as f:
                f.write(json.dumps({"repeat": r, "row": row}) + "\n")
            took = row.get("timings", {}).get("total_s")
            print(f"[repeat {r}/{args.repeats}] {n}/{len(items)} {item['id']} {took}s",
                  flush=True)  # fmt: skip
        repeats.append(rows)
    raw = {
        "kind": "raw",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "qa_file": args.qa.name,
        "config": {
            "system": "owui",
            "generator": MODEL,
            "params": PARAMS,
            "kb": args.kb,
        },
        "repeats": repeats,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(raw, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
