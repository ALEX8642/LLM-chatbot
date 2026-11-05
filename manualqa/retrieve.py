"""Retrieval: hybrid search, reranking, and evidence for the generator.

Evidence is what the generator may cite: text blocks (with their line boxes), table rows
(with the table header and cell boxes, found by search or by ``lookup_table``), and
figures with text. Each piece has a stable id the generator copies into its claims.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from manualqa.blocks import Block, load_pages
from manualqa.chunks import Chunk
from manualqa.geometry import Box
from manualqa.index import Embedder, search, tokens
from manualqa.tables import RowHit, TableStore

MAX_IMAGES = 3
TITLE_CHARS = 120
LEAD_IN_ROWS = 3
LEAD_IN_CHARS = 500
_ITEM = re.compile(r"\bitem\s+(?:no\.?\s*)?(\d+[A-Z]?)\b", re.I)
_FIGURE = re.compile(r"\bfig(?:ure)?\.?\s*(\d+[A-Z]?)\b", re.I)


class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(
        self, model: str = "BAAI/bge-reranker-v2-m3", device: str | None = None
    ):
        from sentence_transformers import CrossEncoder

        self.name = model
        self._model = CrossEncoder(model, device=device)

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self._model.predict([(query, t) for t in texts])]


class HttpReranker:
    """An OpenAI-style ``/v1/rerank`` endpoint (vLLM, Infinity, TEI)."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None):
        self.name, self._url, self._key = model, base_url.rstrip("/"), api_key

    def score(self, query: str, texts: list[str]) -> list[float]:
        import requests

        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        resp = requests.post(
            f"{self._url}/v1/rerank",
            json={"model": self.name, "query": query, "documents": texts},
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()
        scores = [0.0] * len(texts)
        for r in resp.json()["results"]:
            scores[r["index"]] = float(r["relevance_score"])
        return scores


@dataclass
class Evidence:
    id: str
    kind: Literal["text", "row", "figure"]
    manual: str
    page: int
    block_id: str
    text: str
    boxes: list[Box]
    header: list[str] | None = None
    cells: list[str] | None = None
    cell_boxes: list[Box | None] | None = None
    row: int | None = None
    group: str | None = None
    under: str = ""  # the headings and captions the page sits under


@dataclass
class RetrievalResult:
    evidence: list[Evidence]
    ranked_pages: list[int]
    candidate_pages: list[int]
    page_images: list[Path]
    table_hits: int = 0
    chunks: list[str] = field(default_factory=list)


@dataclass
class IngestContext:
    root: Path
    blocks: dict[str, Block]
    block_page: dict[str, tuple[str, int]]
    tables: TableStore
    embedder: Embedder
    reranker: Reranker
    page_blocks: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    under: dict[tuple[str, int], str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path, embedder: Embedder, reranker: Reranker) -> IngestContext:
        path = Path(path)
        blocks, where, on_page = {}, {}, {}
        pages = load_pages(path / "composed.jsonl")
        for pp in pages:
            on_page[(pp.manual, pp.page)] = [b.id for b in pp.blocks]
            for b in pp.blocks:
                blocks[b.id] = b
                where[b.id] = (pp.manual, pp.page)
        return cls(
            path,
            blocks,
            where,
            TableStore(path / "tables.sqlite"),
            embedder,
            reranker,
            on_page,
            titles_by_page(pages),
        )

    def page_image(self, manual: str, page: int) -> Path:
        return self.root / "pages" / Path(manual).stem / f"p{page:03d}-gen.jpg"


def titles_by_page(pages: list) -> dict[tuple[str, int], str]:
    """What each page sits under: the heading and caption running into it, and its own.

    A table that continues over pages prints what it is about only on its first page.
    """
    out: dict[tuple[str, int], str] = {}
    running: dict[str, dict[str, str]] = {}
    for pp in sorted(pages, key=lambda p: (p.manual, p.page)):
        last = running.setdefault(pp.manual, {})
        own = {"heading": [], "caption": []}
        for b in pp.blocks:
            if b.kind in own and b.text.strip():
                own[b.kind].append(" ".join(b.text.split())[:TITLE_CHARS])
        titles = [
            *([last["heading"]] if "heading" in last else []),
            *own["heading"],
            *([last["caption"]] if "caption" in last else []),
            *own["caption"],
        ]
        out[(pp.manual, pp.page)] = "; ".join(dict.fromkeys(titles))
        for kind, texts in own.items():
            if texts:
                last[kind] = texts[-1]
    return out


def layout_row(
    header: list[str], cells: list[str], group: str | None
) -> tuple[str, list[tuple[int, int, int]]]:
    """Row text as "header: value; ..." and the (start, end, column) of each value."""
    parts, spans, pos = [], [], 0
    for col, (h, v) in enumerate(zip(header, cells)):
        if not v.strip():
            continue
        prefix = f"{h}: " if h else ""
        if parts:
            pos += 2  # "; "
        spans.append((pos + len(prefix), pos + len(prefix) + len(v), col))
        parts.append(prefix + v)
        pos += len(prefix) + len(v)
    text = "; ".join(parts)
    if group:
        text += f" (group: {group})"
    return text, spans


def row_evidence(hit: RowHit, under: str = "") -> Evidence:
    text, _ = layout_row(hit.header, hit.cells, hit.group)
    return Evidence(
        id=f"{hit.block_id}:r{hit.row}",
        kind="row",
        manual=hit.manual,
        page=hit.page,
        block_id=hit.block_id,
        text=text,
        boxes=[b for b in hit.cell_boxes if b],
        header=hit.header,
        cells=hit.cells,
        cell_boxes=hit.cell_boxes,
        row=hit.row,
        group=hit.group,
        under=under,
    )


def _block_evidence(ctx: IngestContext, block_id: str) -> Evidence | None:
    b = ctx.blocks.get(block_id)
    if b is None or not b.text.strip() or b.kind == "table":
        return None
    manual, page = ctx.block_page[block_id]
    under = ctx.under.get((manual, page), "")
    if b.kind == "figure":  # a figure claim highlights the figure, not its OCR lines
        return Evidence(
            b.id, "figure", manual, page, b.id, b.text, [b.box], under=under
        )
    return Evidence(
        b.id,
        "text",
        manual,
        page,
        b.id,
        b.text,
        [ln.box for ln in b.lines],
        under=under,
    )


def _table_rows(ctx: IngestContext, block_id: str) -> list[Evidence]:
    under = ctx.under.get(ctx.block_page[block_id], "")
    return [
        row_evidence(hit, under)
        for hit in ctx.tables.lookup_table(block_id=block_id, limit=1000)
    ]


def lead_in(ctx: IngestContext, ev: Evidence) -> str:
    """What comes just before this evidence: a procedure's stem, the rows above a table row."""
    if ev.kind == "row":
        rows = ctx.tables.lookup_table(block_id=ev.block_id, limit=1000)
        above = [h for h in rows if ev.row is not None and h.row < ev.row]
        return "\n".join(
            " | ".join(c for c in h.cells if c.strip()) for h in above[-LEAD_IN_ROWS:]
        )
    on_page = ctx.page_blocks.get((ev.manual, ev.page), [])
    if ev.block_id not in on_page:
        return ""
    for block_id in reversed(on_page[: on_page.index(ev.block_id)]):
        block = ctx.blocks[block_id]
        if block.kind in ("text", "heading") and block.text.strip():
            return block.text[-LEAD_IN_CHARS:]
    return ""


def page_evidence(ctx: IngestContext, manual: str, page: int) -> list[Evidence]:
    """Everything quotable on a page, for a quote the model attributed to the wrong block."""
    out: list[Evidence] = []
    for block_id in ctx.page_blocks.get((manual, page), []):
        if ctx.blocks[block_id].kind == "table":
            out += _table_rows(ctx, block_id)
        else:
            ev = _block_evidence(ctx, block_id)
            if ev and ev.kind == "text":
                out.append(ev)
    return out


def _identifier(tok: str) -> bool:
    """Part numbers, codes and long numbers ("p14-8969", "ms35338-63", "18265")."""
    has_digit = any(ch.isdigit() for ch in tok)
    has_alpha = any(ch.isalpha() for ch in tok)
    return has_digit and (
        "-" in tok or (has_alpha and len(tok) >= 4) or (tok.isdigit() and len(tok) >= 5)
    )


def _lookups(question: str, manual: str, ctx: IngestContext) -> list[RowHit]:
    hits: list[RowHit] = []
    item, figure = _ITEM.search(question), _FIGURE.search(question)
    if item:
        hits += ctx.tables.lookup_table(
            columns={"item": item.group(1)},
            figure=figure.group(1) if figure else None,
            manual=manual,
            limit=5,
        )
    for tok in dict.fromkeys(tokens(question)):
        if _identifier(tok):
            hits += ctx.tables.lookup_table(query=tok, manual=manual, limit=3)
    return hits


def retrieve(
    question: str,
    manual: str,
    ctx: IngestContext,
    k_chunks: int = 8,
    pool: int = 50,
) -> RetrievalResult:
    found = search(question, ctx.root / "qdrant", ctx.embedder, k=pool, manual=manual)
    candidates = [c for c, _ in found]
    scores = (
        ctx.reranker.score(question, [c.text for c in candidates]) if candidates else []
    )
    ranked: list[Chunk] = [
        c for _, c in sorted(zip(scores, candidates), key=lambda p: -p[0])
    ][:k_chunks]

    evidence: dict[str, Evidence] = {}
    hits = _lookups(question, manual, ctx)
    for hit in hits:
        ev = row_evidence(hit, ctx.under.get((hit.manual, hit.page), ""))
        evidence.setdefault(ev.id, ev)
    for chunk in ranked:
        for block_id in chunk.block_ids:
            block = ctx.blocks.get(block_id)
            if block is not None and block.kind == "table":
                for ev in _table_rows(ctx, block_id):
                    evidence.setdefault(ev.id, ev)
                continue
            ev = _block_evidence(ctx, block_id)
            if ev:
                evidence.setdefault(ev.id, ev)
            if block is not None and block.kind == "caption":
                # a table's caption can rank without its rows, which then reach the
                # model only as a page image with nothing to quote
                for other in ctx.page_blocks.get(ctx.block_page[block_id], []):
                    if ctx.blocks[other].kind == "table":
                        for ev in _table_rows(ctx, other):
                            evidence.setdefault(ev.id, ev)

    ranked_pages = list(dict.fromkeys(p for c in ranked for p in c.pages))
    image_pages = list(dict.fromkeys([h.page for h in hits] + ranked_pages))
    images = [ctx.page_image(manual, p) for p in image_pages]
    images = [p for p in images if p.exists()][:MAX_IMAGES]
    return RetrievalResult(
        evidence=list(evidence.values()),
        ranked_pages=ranked_pages,
        candidate_pages=list(dict.fromkeys(p for c in candidates for p in c.pages)),
        page_images=images,
        table_hits=len(hits),
        chunks=[c.id for c in ranked],
    )
