"""Evaluation harness: generate answers with v2, then grade them with a local judge.

    python -m evals.run_eval generate --system v2 --ingest data/ingest --qa evals/test.jsonl \
        --repeats 3 --out evals/results/raw/v2-test.json
    python -m evals.run_eval score evals/results/raw/v2-test.json --qa evals/test.jsonl \
        --out evals/results/test/v2-test-phi4.json

The judge is any OpenAI-compatible endpoint: LLM_BASE_URL, LLM_API_KEY and LLM_JUDGE_MODEL
come from the environment. The generator for v2 comes from GEN_BASE_URL, GEN_API_KEY and
GEN_MODEL. v1 was run with the version of this file at tag `prereg`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_QA = EVAL_DIR / "qa.jsonl"
K_VALUES = (1, 5, 10)
MAX_CONSECUTIVE_ERRORS = 3

# -------------------------
# Shared helpers
# -------------------------


def load_qa(path: Path) -> List[Dict[str, Any]]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dedupe_pages(pages: List[Optional[int]]) -> List[int]:
    """Keep the first occurrence of each page, preserving rank order."""
    seen, out = set(), []
    for p in pages:
        if p is None or p in seen:
            continue
        seen.add(p)
        out.append(int(p))
    return out


def git_describe(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "describe", "--tags", "--always", "--dirty"],
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    idx = (len(s) - 1) * q
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


# -------------------------
# System adapters
# -------------------------
# An adapter takes (question, manual filename) and returns a dict with:
#   answer          final text
#   ranked_pages    pages of the final ranked documents, best first
#   candidate_pages pages of a wider pre-rerank list, if the system has one
#   cited_pages     pages the system cites to the user
#   context         the excerpts text actually passed to the model
#   timings         {"total_s": ..., "llm_s": ...}


def make_v2_adapter(
    ingest_dir: Optional[Path] = None,
    embedder: str = "st:Qwen/Qwen3-Embedding-0.6B",
    reranker: str = "qwen:Qwen/Qwen3-Reranker-4B",
    ctx: Any = None,
    gen: Any = None,
    config: Optional[Dict[str, Any]] = None,
    meaning_check: bool = True,
) -> Callable[..., Dict[str, Any]]:
    """v2 (the manualqa package) over an ingested corpus. The generator comes from
    GEN_BASE_URL / GEN_API_KEY / GEN_MODEL; only the model name is recorded."""
    from dataclasses import asdict

    from manualqa.answer import answer
    from manualqa.claimcheck import LLMChecker
    from manualqa.generate import Generator
    from manualqa.index import make_embedder
    from manualqa.prompts import PROMPT_VERSION
    from manualqa.retrieve import IngestContext, make_reranker

    if ctx is None:
        ctx = IngestContext.load(
            Path(ingest_dir), make_embedder(embedder), make_reranker(reranker, 2)
        )
    gen = gen or Generator.from_env()
    checker = LLMChecker(gen) if meaning_check else None
    summary = Path(ctx.root) / "summary.json"

    def run(question: str, manual: str) -> Dict[str, Any]:
        ans = answer(question, manual, ctx, gen, checker=checker)
        timings = {k: round(v, 3) for k, v in ans.timings.items()}
        return {
            "answer": ans.text,
            "ranked_pages": ans.retrieval.ranked_pages,
            "candidate_pages": ans.retrieval.candidate_pages,
            "cited_pages": dedupe_pages([c.page for c in ans.claims]),
            "context": "\n\n".join(
                f"[{e.id}] (page {e.page}) {e.text}" for e in ans.retrieval.evidence
            ),
            "timings": timings,
            "claims": [asdict(c) for c in ans.claims],
            "removed": [asdict(c) for c in ans.removed],
            "abstained": ans.abstained,
            "abstain_reason": ans.abstain_reason,
            "unknown_blocks": ans.unknown_blocks,
            "ignored_lines": ans.ignored_lines,
            "page_images": [p.name for p in ans.retrieval.page_images],
            "table_hits": ans.retrieval.table_hits,
        }

    run.config = {
        "system": "v2",
        "generator": getattr(gen, "model", None),
        "embedder": getattr(ctx.embedder, "name", None),
        "reranker": getattr(ctx.reranker, "name", None),
        "prompt_version": PROMPT_VERSION,
        "meaning_check": "llm" if meaning_check else None,
        "ingest_summary_sha256": sha256_file(summary) if summary.exists() else None,
        **(config or {}),
    }
    run.llm_url = None
    return run


ADAPTERS = {
    "v2": lambda a: make_v2_adapter(Path(a.ingest), a.embedder, a.reranker),
}


def cmd_generate(args) -> None:
    qa = load_qa(Path(args.qa))
    if args.limit:
        qa = qa[: args.limit]
    run = ADAPTERS[args.system](args)
    config = dict(run.config)

    runs = []
    consecutive_errors = 0
    for r in range(args.repeats):
        items = []
        for i, item in enumerate(qa, 1):
            try:
                out = run(item["question"], item["manual"])
                out["error"] = None
                consecutive_errors = 0
            except Exception as e:  # isolated failures are recorded, not hidden
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    sys.exit(
                        f"aborting: {consecutive_errors} consecutive errors, last: {e!r}"
                        " (is a dependency down?). No results written."
                    )
                out = {
                    "answer": "",
                    "ranked_pages": [],
                    "candidate_pages": [],
                    "cited_pages": [],
                    "context": "",
                    "timings": {},
                    "error": repr(e),
                }
            items.append({"id": item["id"], **out})
            print(
                f"[repeat {r + 1}/{args.repeats}] {i}/{len(qa)} {item['id']}"
                f" {out['timings'].get('total_s', 0) or 0:.1f}s"
                + (f" ERROR {out['error']}" if out["error"] else ""),
                flush=True,
            )
        runs.append(items)

    raw = {
        "kind": "raw",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "qa_file": str(Path(args.qa).name),
        "qa_sha256": sha256_file(Path(args.qa)),
        "config": config,
        "repeats": runs,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(raw, indent=2))
    print(f"wrote {args.out}")


# -------------------------
# Judge
# -------------------------

def first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """The first complete JSON object in a reply; models often keep talking after it."""
    decoder = json.JSONDecoder()
    for start, ch in enumerate(text):
        if ch == "{":
            try:
                value, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    return None


def reusable_grades(
    previous: Dict[str, Any], regrade_category: Optional[str] = None
) -> Dict[Any, Dict[str, Any]]:
    """(repeat, id) -> grade, for grades of an earlier run with no judge error."""
    return {
        (r, g["id"]): g
        for r, repeat in enumerate(previous["repeats"], 1)
        for g in repeat["items"]
        if not g["judge_error"] and g["category"] != regrade_category
    }


class Judge:
    def __init__(self, base_url: str, api_key: str, model: str, seed: int = 0):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.model = model
        self.seed = seed
        self.max_tokens = 600

    def ask(self, prompt: str) -> Dict[str, Any]:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "seed": self.seed,
            "max_tokens": self.max_tokens,
        }
        for attempt in range(3):
            r = requests.post(self.url, json=body, headers=self.headers, timeout=180)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"] or ""
            parsed = first_json_object(text)
            if parsed is not None:
                return parsed
            time.sleep(2 * (attempt + 1))
        raise ValueError(f"judge returned no JSON: {text[:200]!r}")


# -------------------------
# Scoring
# -------------------------

class CachingJudge(Judge):
    """Repeats of one answer get one judge call; the judge is fixed at temperature 0."""

    RETRY_WAITS_S = (10, 30, 60, 120, 300)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.replies: Dict[str, Dict[str, Any]] = {}
        self.max_tokens = 1500  # as in judge selection; 600 cuts off long JSON replies

    def ask(self, prompt: str) -> Dict[str, Any]:
        if prompt not in self.replies:
            self.replies[prompt] = self._ask_with_retries(prompt)
        return self.replies[prompt]

    def _ask_with_retries(self, prompt: str) -> Dict[str, Any]:
        for wait in self.RETRY_WAITS_S:
            try:
                return super().ask(prompt)
            except requests.RequestException:  # a network drop must not lose the run
                time.sleep(wait)
        raise ValueError("judge unreachable after retries")


def cmd_score_keyfacts(args) -> None:
    from evals.grade import (
        cited_source,
        grade_item,
        length_bias,
        page_source,
        summarize_grades,
    )
    from evals.items import load_items
    from manualqa.blocks import load_pages
    from evals.prompts import PROMPT_VERSION

    raw = json.loads(Path(args.raw).read_text())
    items = {i.id: i for i in load_items(Path(args.qa))}
    blocks, pages = {}, {}
    for pp in load_pages(Path(args.composed)):
        pages[(pp.manual, pp.page)] = "\n".join(b.text for b in pp.blocks)
        blocks.update({b.id: b.text for b in pp.blocks})
    judge = CachingJudge(
        os.environ["LLM_BASE_URL"],
        os.environ.get("LLM_API_KEY", ""),
        os.environ["LLM_JUDGE_MODEL"],
    )
    reuse = (
        reusable_grades(json.loads(Path(args.reuse).read_text()), args.regrade_category)
        if args.reuse
        else {}
    )
    repeats = []
    for r, outs in enumerate(raw["repeats"][: args.max_repeats], 1):
        grades = []
        for i, out in enumerate(outs, 1):
            item = items[out["id"]]
            if (r, out["id"]) in reuse:
                grades.append(reuse[(r, out["id"])])
                continue
            source = cited_source(out, item.manual, blocks, pages)
            pages_only = (
                page_source(out, item.manual, pages) if out.get("claims") else None
            )
            grades.append(
                grade_item(
                    item,
                    {**out, "cited_source": source, "page_source": pages_only},
                    judge,
                )
            )
            print(f"[repeat {r}] graded {i}/{len(outs)} {out['id']}", flush=True)
        by_category = {}
        for c in sorted({g["category"] for g in grades}):
            by_category[c] = summarize_grades([g for g in grades if g["category"] == c])
        repeats.append(
            {
                "summary": summarize_grades(grades),
                "by_category": by_category,
                "length_bias": length_bias(grades),
                "items": grades,
            }
        )
    result = {
        "kind": "graded-keyfacts",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_file": str(args.raw),
        "config": raw["config"],
        "judge": {"model": judge.model, "prompt_version": PROMPT_VERSION},
        "repeats": repeats,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps([r["summary"] for r in repeats], indent=2))
    print(f"wrote {args.out}")


def cmd_score(args) -> None:
    cmd_score_keyfacts(args)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="run a system over the QA set")
    g.add_argument("--system", choices=sorted(ADAPTERS), required=True)
    g.add_argument("--ingest", default="data/ingest", help="v2: ingested corpus")
    g.add_argument("--embedder", default="st:Qwen/Qwen3-Embedding-0.6B", help="v2")
    g.add_argument("--reranker", default="qwen:Qwen/Qwen3-Reranker-4B", help="v2")
    g.add_argument("--qa", default=str(DEFAULT_QA))
    g.add_argument("--repeats", type=int, default=1)
    g.add_argument(
        "--limit", type=int, default=0, help="only the first N questions (smoke test)"
    )
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("score", help="score a raw run")
    s.add_argument("raw")
    s.add_argument("--qa", default=str(DEFAULT_QA))
    s.add_argument("--composed", default="data/ingest/composed.jsonl", help="source text the judge reads")
    s.add_argument("--max-repeats", type=int, help="grade only the first N repeats")
    s.add_argument("--reuse", help="keep good grades from this earlier file")
    s.add_argument(
        "--regrade-category", help="with --reuse, redo this category"
    )
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_score)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
