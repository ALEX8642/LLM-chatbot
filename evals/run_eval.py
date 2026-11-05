"""Evaluation harness for the manual-QA chatbot.

Two steps, so answers can be re-scored without regenerating them:

    generate  Run a system over evals/qa.jsonl and write raw records
              (answer, retrieved pages, context shown to the model, latency).
    score     Compute retrieval and citation metrics, ask an LLM judge for
              correctness, abstention and faithfulness, and write a summary.

Usage:

    python evals/run_eval.py generate --system v1 --app-dir ../LLM-chatbot-v1 \
        --repeats 3 --out evals/results/raw/v1.json
    python evals/run_eval.py score evals/results/raw/v1.json \
        --out evals/results/v1.json

The judge is any OpenAI-compatible endpoint: LLM_BASE_URL, LLM_API_KEY and
LLM_JUDGE_MODEL come from the environment. The script needs only the standard
library and `requests`, so it runs inside the environment of the system it
evaluates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
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


def force_temperature(api: Any, temperature: float) -> None:
    """Adds a temperature to every request v1 sends, without changing v1's code."""
    post = api.requests.post

    def post_with_temperature(url, json=None, **kwargs):
        options = {**(json or {}).get("options", {}), "temperature": temperature}
        return post(url, json={**(json or {}), "options": options}, **kwargs)

    api.requests = SimpleNamespace(
        **{k: getattr(api.requests, k) for k in dir(api.requests) if k[0] != "_"}
    )
    api.requests.post = post_with_temperature


def make_v1_adapter(
    app_dir: Path, strict_mode: bool, temperature: Optional[float] = None
) -> Callable[..., Dict[str, Any]]:
    """Run v1's api.py unchanged, recording what happens inside it.

    v1 builds its pipeline in the FastAPI lifespan and answers through
    answer_with_ollama(). We wrap the pipeline to record retrieval results and
    wrap query_ollama() to record the exact prompt, then call v1 as the /ask
    endpoint would.
    """
    import asyncio

    sys.path.insert(0, str(app_dir))
    import api  # noqa: E402  (v1 module from app_dir)

    if temperature is not None:
        force_temperature(api, temperature)

    manuals_json = app_dir / "frontend" / "public" / "manuals" / "manuals.json"
    id_by_file = {
        Path(m["pdf_url"]).name: m["id"] for m in json.loads(manuals_json.read_text())
    }

    lifespan_cm = api.lifespan(api.app)
    asyncio.run(lifespan_cm.__aenter__())  # builds api.app.state.pipe
    pipe = api.app.state.pipe

    record: Dict[str, Any] = {}

    class RecordingPipe:
        def run(self, data):
            res = pipe.run(data, include_outputs_from={"join", "rerank", "diverse"})
            record["pipe_result"] = res
            return res

    original_query = api.query_ollama

    def recording_query(prompt, model=None, url=api.OLLAMA_URL):
        t0 = time.perf_counter()
        out = original_query(prompt, model=model, url=url)
        record["llm_s"] = time.perf_counter() - t0
        record["prompt"] = prompt
        return out

    api.query_ollama = recording_query
    recorder = RecordingPipe()

    def pages_of(res, key):
        docs = (res.get(key) or {}).get("documents") or []
        return dedupe_pages([d.meta.get("page") for d in docs])

    def run(question: str, manual: str) -> Dict[str, Any]:
        record.clear()
        t0 = time.perf_counter()
        out = api.answer_with_ollama(
            question,
            manual_id=id_by_file[manual],
            pipe=recorder,
            model=api.OLLAMA_MODEL,
            max_sections=None,
            strict_mode=strict_mode,
        )
        total = time.perf_counter() - t0
        res = record.get("pipe_result") or {}
        ranked = pages_of(res, "diverse") or pages_of(res, "rerank")
        prompt = record.get("prompt", "")
        context = prompt.split("Manual excerpts:", 1)[-1].strip() if prompt else ""
        return {
            "answer": out["answer"],
            "ranked_pages": ranked,
            "candidate_pages": pages_of(res, "join"),
            "cited_pages": [c["page"] for c in out["citations"]],
            "context": context,
            "timings": {"total_s": total, "llm_s": record.get("llm_s")},
        }

    # Endpoints and host names stay out of results: the repo is public.
    run.llm_url = api.OLLAMA_URL  # type: ignore[attr-defined]
    run.config = {  # type: ignore[attr-defined]
        "system": "v1",
        "strict_mode": strict_mode,
        "temperature": temperature,
        "llm_backend": "ollama",
        "llm_model": api.OLLAMA_MODEL,
        "retrieve_top_k": api.RETRIEVE_TOP_K,
        "max_context_chunks": api.MAX_CONTEXT_CHUNKS,
        "min_doc_score": os.getenv(
            "RAG_MIN_DOC_SCORE", os.getenv("MIN_DOC_SCORE", "0.35")
        ),
        "app_version": git_describe(app_dir),
    }
    return run


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
    "v1": lambda a: make_v1_adapter(Path(a.app_dir).resolve(), strict_mode=False),
    "v1-t0": lambda a: make_v1_adapter(
        Path(a.app_dir).resolve(), strict_mode=False, temperature=0
    ),
    "v1-strict": lambda a: make_v1_adapter(Path(a.app_dir).resolve(), strict_mode=True),
    "v2": lambda a: make_v2_adapter(Path(a.ingest), a.embedder, a.reranker),
}


def ollama_model_digest(url: str, model: str) -> Optional[str]:
    try:
        tags = requests.get(f"{url}/api/tags", timeout=10).json()["models"]
        return next((m["digest"] for m in tags if m["name"] == model), None)
    except Exception:
        return None


def cmd_generate(args) -> None:
    qa = load_qa(Path(args.qa))
    if args.limit:
        qa = qa[: args.limit]
    run = ADAPTERS[args.system](args)
    config = dict(run.config)
    if config.get("llm_backend") == "ollama":
        config["llm_model_digest"] = ollama_model_digest(
            run.llm_url, config["llm_model"]
        )

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

# Judge prompts. Versioned: changing them changes every score, so bump JUDGE_VERSION
# and re-score every system being compared.
JUDGE_VERSION = 2

JUDGE_CORRECTNESS = """You grade answers from a technical-manual assistant.

Question: {question}
Reference answer: {reference}
Assistant answer: {answer}

Decide two things.
1. "abstained": true if the assistant does not commit to an answer: it declines, or says
   the manual or the excerpts do not contain the information. This holds even if it then
   suggests where else to look (an index, another document, a technician). False if it
   gives a substantive answer, even a wrong or hedged one.
2. "correctness", comparing the assistant answer with the reference answer:
   - "correct": contains the key facts of the reference and nothing that contradicts it
   - "partial": some key facts right, others missing or wrong
   - "incorrect": wrong, contradicts the reference, or gives no answer
   If the reference says the question is not covered by the manual, the answer is
   "correct" if the assistant abstains and "incorrect" if it gives a substantive answer.
   Ignore style, length and extra detail that does not contradict the reference.

Reply with JSON only: {{"abstained": true|false, "correctness": "correct"|"partial"|"incorrect", "reason": "<one sentence>"}}"""

JUDGE_FAITHFULNESS = """You check whether an answer is grounded in the excerpts it was given.

Manual excerpts shown to the assistant:
<<<
{context}
>>>

Assistant answer:
<<<
{answer}
>>>

List each factual claim in the answer that is NOT supported by the excerpts.
- Excerpts come from PDF text extraction. Tables are often flattened to one cell per
  line, in column order (for example item, codes, part number, description, quantity).
  Read them carefully before calling a value unsupported.
- Not claims: statements that the manual or excerpts lack the information, generic
  advice to consult a technician, and arithmetic or reasoning steps applied to supported
  facts (but a wrong result of such a step is an unsupported claim).
Then rate:
- "faithful": every claim is supported
- "partial": at least one claim is unsupported, but most are supported
- "unfaithful": most claims are unsupported

Reply with JSON only: {{"unsupported_claims": ["..."], "faithfulness": "faithful"|"partial"|"unfaithful"}}"""


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

CORRECTNESS_SCORE = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
FAITHFUL_SCORE = {"faithful": 1.0, "partial": 0.5, "unfaithful": 0.0}


def retrieval_metrics(ranked: List[int], gold: List[int]) -> Dict[str, Any]:
    gold_set = set(gold)
    first = next((i for i, p in enumerate(ranked, 1) if p in gold_set), None)
    m = {f"recall@{k}": float(any(p in gold_set for p in ranked[:k])) for k in K_VALUES}
    m["rr"] = 1.0 / first if first else 0.0
    return m


def score_item(
    item: Dict[str, Any], gold: Dict[str, Any], judge: Optional[Judge]
) -> Dict[str, Any]:
    answerable = gold["category"] != "unanswerable"
    s: Dict[str, Any] = {
        "id": item["id"],
        "category": gold["category"],
        "manual": gold["manual"],
        "answerable": answerable,
        "error": item.get("error"),
    }
    if answerable:
        s.update(retrieval_metrics(item["ranked_pages"], gold["gold_pages"]))
        s["candidate_recall"] = float(
            bool(set(item.get("candidate_pages") or []) & set(gold["gold_pages"]))
        )
        cited = item["cited_pages"]
        hits = [p for p in cited if p in set(gold["gold_pages"])]
        s["citation_hit"] = float(bool(hits))
        s["citation_precision"] = len(hits) / len(cited) if cited else 0.0
    s["latency_s"] = item["timings"].get("total_s")

    if judge and not item.get("error"):
        try:
            _judge_item(s, item, gold, judge)
        except ValueError as e:  # a reply without JSON: unjudged, not wrong
            s["judge_error"] = str(e)[:300]
            s.setdefault("correctness", None)
    return s


def _judge_item(
    s: Dict[str, Any], item: Dict[str, Any], gold: Dict[str, Any], judge: Judge
) -> None:
    c = judge.ask(
        JUDGE_CORRECTNESS.format(
            question=gold["question"],
            reference=gold["reference_answer"],
            answer=item["answer"],
        )
    )
    s["abstained"] = bool(c.get("abstained"))
    s["correctness"] = c.get("correctness")
    s["correctness_reason"] = c.get("reason")
    if item["answer"].strip() and not s["abstained"]:
        f = judge.ask(
            JUDGE_FAITHFULNESS.format(
                context=item["context"] or "(no excerpts)", answer=item["answer"]
            )
        )
        s["faithfulness"] = f.get("faithfulness")
        s["unsupported_claims"] = f.get("unsupported_claims", [])


def mean(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def summarize(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    ans = [s for s in scored if s["answerable"]]
    unans = [s for s in scored if not s["answerable"]]
    out: Dict[str, Any] = {
        "n": len(scored),
        "n_answerable": len(ans),
        "n_unanswerable": len(unans),
    }
    for k in K_VALUES:
        out[f"recall@{k}"] = mean([s[f"recall@{k}"] for s in ans])
    out["mrr"] = mean([s["rr"] for s in ans])
    out["candidate_recall"] = mean([s["candidate_recall"] for s in ans])
    out["citation_hit"] = mean([s["citation_hit"] for s in ans])
    out["citation_precision"] = mean([s["citation_precision"] for s in ans])
    if any("correctness" in s for s in scored):
        out["correctness"] = mean(
            [
                CORRECTNESS_SCORE.get(s.get("correctness"), 0.0)
                for s in ans
                if s.get("correctness") is not None
            ]
        )
        out["judge_errors"] = sum(1 for s in scored if s.get("judge_error"))
        faith = [
            FAITHFUL_SCORE[s["faithfulness"]]
            for s in scored
            if s.get("faithfulness") in FAITHFUL_SCORE
        ]
        out["faithfulness"] = mean(faith)
        out["n_faithfulness_judged"] = len(faith)
        abstained = [s for s in scored if s.get("abstained")]
        tp = sum(1 for s in abstained if not s["answerable"])
        out["abstention_precision"] = (
            round(tp / len(abstained), 4) if abstained else None
        )
        out["abstention_recall"] = round(tp / len(unans), 4) if unans else None
        out["false_abstentions"] = sum(1 for s in abstained if s["answerable"])
    lat = [s["latency_s"] for s in scored if s.get("latency_s") is not None]
    out["latency_p50_s"] = round(percentile(lat, 0.5), 2) if lat else None
    out["latency_p95_s"] = round(percentile(lat, 0.95), 2) if lat else None
    out["errors"] = sum(1 for s in scored if s.get("error"))
    return out


def breakdown(scored: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in scored:
        groups.setdefault(s[key], []).append(s)
    return {g: summarize(v) for g, v in sorted(groups.items())}


def spread(per_repeat: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mean, min and max of each numeric metric across repeats."""
    out = {}
    for k in per_repeat[0]:
        vals = [r[k] for r in per_repeat if isinstance(r.get(k), (int, float))]
        if len(vals) == len(per_repeat):
            out[k] = {
                "mean": round(statistics.mean(vals), 4),
                "min": min(vals),
                "max": max(vals),
            }
    return out


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
    if args.grader == "keyfacts":
        cmd_score_keyfacts(args)
        return
    raw = json.loads(Path(args.raw).read_text())
    qa = {q["id"]: q for q in load_qa(Path(args.qa))}
    if raw["qa_sha256"] != sha256_file(Path(args.qa)):
        print(
            "WARNING: qa file changed since generation; scoring against the current file",
            file=sys.stderr,
        )

    judge = None
    if not args.no_judge:
        judge = Judge(
            os.environ["LLM_BASE_URL"],
            os.environ.get("LLM_API_KEY", ""),
            os.environ["LLM_JUDGE_MODEL"],
        )

    repeats = []
    for r, items in enumerate(raw["repeats"], 1):
        scored = []
        for i, item in enumerate(items, 1):
            scored.append(score_item(item, qa[item["id"]], judge))
            print(
                f"[repeat {r}/{len(raw['repeats'])}] scored {i}/{len(items)} {item['id']}",
                flush=True,
            )
        repeats.append(
            {
                "summary": summarize(scored),
                "by_category": breakdown(scored, "category"),
                "by_manual": breakdown(scored, "manual"),
                "items": scored,
            }
        )

    result = {
        "kind": "scored",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_file": str(args.raw),
        "qa_sha256": raw["qa_sha256"],
        "config": raw["config"],
        "judge": (
            {
                "model": judge.model,
                "version": JUDGE_VERSION,
                "temperature": 0,
                "seed": judge.seed,
            }
            if judge
            else None
        ),
        "n_repeats": len(repeats),
        "summary": spread([r["summary"] for r in repeats]),
        "by_category": {
            c: spread([r["by_category"][c] for r in repeats])
            for c in repeats[0]["by_category"]
        },
        "by_manual": {
            m: spread([r["by_manual"][m] for r in repeats])
            for m in repeats[0]["by_manual"]
        },
        "repeats": repeats,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result["summary"], indent=2))
    print(f"wrote {args.out}")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="run a system over the QA set")
    g.add_argument("--system", choices=sorted(ADAPTERS), required=True)
    g.add_argument("--app-dir", default=".", help="checkout of the system to evaluate")
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
    s.add_argument(
        "--no-judge", action="store_true", help="retrieval and citation metrics only"
    )
    s.add_argument(
        "--grader",
        choices=["legacy", "keyfacts"],
        default="legacy",
        help="legacy: holistic grade (history); keyfacts: checklist and source support",
    )
    s.add_argument("--composed", default="data/ingest/composed.jsonl", help="keyfacts")
    s.add_argument("--max-repeats", type=int, help="keyfacts: grade only the first N")
    s.add_argument("--reuse", help="keyfacts: keep good grades from this earlier file")
    s.add_argument(
        "--regrade-category", help="keyfacts: with --reuse, redo this category"
    )
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_score)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
