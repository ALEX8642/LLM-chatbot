# api.py

# © 2025 Alexander Feht
# Licensed under the MIT License
# This project was created independently and is not affiliated with any employer.

import json
import os
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# -------------------------
# Haystack / Retrieval Setup
# -------------------------
from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.joiners import DocumentJoiner
from haystack.components.rankers import (
    SentenceTransformersDiversityRanker,
    TransformersSimilarityRanker,
)
from haystack_integrations.components.retrievers.opensearch import (
    OpenSearchBM25Retriever,
)
from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from pydantic import BaseModel, Field

qdrant = QdrantDocumentStore(
    url="http://localhost:6333", index="manuals", embedding_dim=384
)
opensearch = OpenSearchDocumentStore(
    hosts="http://localhost:9200", username="admin", password="admin", index="manuals"
)

query_embedder = SentenceTransformersTextEmbedder(
    model="sentence-transformers/all-MiniLM-L6-v2"
)

# Retrieve broadly (recall) then filter/rerank (precision)
RETRIEVE_TOP_K = int(os.getenv("RAG_RETRIEVE_TOP_K", "30"))
MAX_CONTEXT_CHUNKS = int(os.getenv("RAG_MAX_CONTEXT_CHUNKS", "5"))

# Moderate-confidence gate. Tune per manual set.
# Note: Haystack score ranges differ by retriever/joiner mode; start conservative and adjust.
MIN_DOC_SCORE = float(os.getenv("RAG_MIN_DOC_SCORE", "0.2"))

dense_retriever = QdrantEmbeddingRetriever(document_store=qdrant, top_k=RETRIEVE_TOP_K)
bm25_retriever = OpenSearchBM25Retriever(
    document_store=opensearch, top_k=RETRIEVE_TOP_K
)

# Join + fuse scores across retrievers rather than blindly concatenating.
# Options include: reciprocal_rank_fusion, distribution_based_rank_fusion, merge, concatenate.
joiner = DocumentJoiner(join_mode=os.getenv("RAG_JOIN_MODE", "reciprocal_rank_fusion"))

# Precision stage 1: cross-encoder rerank for true relevance.
ranker = TransformersSimilarityRanker(
    model=os.getenv("RAG_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
    top_k=MAX_CONTEXT_CHUNKS,
)

# Precision stage 2: diversity (MMR) to avoid near-duplicate citations.
diversity_ranker = SentenceTransformersDiversityRanker(
    model=os.getenv("RAG_DIVERSITY_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
    top_k=MAX_CONTEXT_CHUNKS,
    strategy="maximum_margin_relevance",
    lambda_threshold=float(os.getenv("RAG_MMR_LAMBDA", "0.7")),
)

pipe = Pipeline()
pipe.add_component("query_embedder", query_embedder)
pipe.add_component("dense", dense_retriever)
pipe.add_component("sparse", bm25_retriever)
pipe.add_component("join", joiner)
pipe.add_component("rerank", ranker)
pipe.add_component("diverse", diversity_ranker)
pipe.connect("query_embedder.embedding", "dense.query_embedding")
pipe.connect("dense.documents", "join.documents")
pipe.connect("sparse.documents", "join.documents")

# Rankers need both query and documents
pipe.connect("join.documents", "rerank.documents")
pipe.connect("rerank.documents", "diverse.documents")

# Warm-up rankers at startup to avoid first-request latency spikes.
try:
    ranker.warm_up()
except Exception:
    pass
try:
    diversity_ranker.warm_up()
except Exception:
    pass

# -------------------------
# Ollama (chat endpoint)
# -------------------------
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "command-r7b:latest"


def query_ollama(prompt: str, model: str = None, url: str = OLLAMA_URL) -> str:
    """Calls Ollama /api/chat in streaming mode and concatenates the chunks."""
    model = model or OLLAMA_MODEL
    r = requests.post(
        f"{url}/api/chat",
        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        stream=True,
        timeout=180,
    )
    r.raise_for_status()

    full_text = ""
    for line in r.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line.decode("utf-8"))
        except Exception:
            continue
        if "message" in data and "content" in data["message"]:
            full_text += data["message"]["content"]
        if data.get("done"):
            break
    return full_text.strip()


# -------------------------
# Prompt + wrappers
# -------------------------
def make_prompt(user_query: str, docs, top_k: int = 5) -> str:
    picked = docs[:top_k] if docs else []
    if picked:
        context = "\n\n".join(
            [f"[Page {d.meta.get('page')}] {d.content}" for d in picked]
        )
    else:
        context = "(No sufficiently relevant manual excerpts were retrieved for this question.)"
    return f"""You are a careful technical support assistant.
Answer the user’s question following these rules:
- Use the manual excerpts as the primary source of truth.
- Prefer exact terminology from the excerpts (e.g., feature names, selectors, parameters).
- If you cannot find enough information, say so clearly.
- You may combine steps across excerpts if they describe parts of the same procedure.
- Do not add extra interface elements or buttons unless named in the excerpts.

User question:
{user_query}

Manual excerpts:
{context}
"""


def build_citations(docs) -> List[Dict[str, Any]]:
    return [
        {"page": d.meta.get("page", 1), "product": d.meta.get("product_id")}
        for d in docs
    ]


def build_manual_sections(
    docs, max_sections: int = 3, snippet_chars: int = 280
) -> List[Dict[str, Any]]:
    sections = []
    for d in docs[:max_sections]:
        txt = (d.content or "").replace("\n", " ").strip()
        snippet = txt[:snippet_chars]
        if len(txt) > snippet_chars:
            snippet += "…"
        sections.append(
            {
                "page": d.meta.get("page", 1),
                "product": d.meta.get("product_id"),
                "snippet": snippet,
            }
        )
    return sections


def answer_with_ollama(
    user_query: str,
    manual_id: str,
    model: str = OLLAMA_MODEL,
    max_sections: int | None = None,
    strict_mode: bool = False,
) -> Dict[str, Any]:
    """Retrieve, gate, and answer.

    strict_mode=False (guardrails OFF): always provide some context if any docs exist (fallback to top-1).
    strict_mode=True (guardrails ON): only provide context if docs exceed MIN_DOC_SCORE; otherwise abstain (no citations).
    """

    filter_condition = {"operator": "==", "field": "manual_id", "value": manual_id}

    res = pipe.run(
        {
            "query_embedder": {"text": user_query},
            "dense": {"filters": filter_condition},
            "sparse": {"query": user_query, "filters": filter_condition},
            "rerank": {"query": user_query, "top_k": MAX_CONTEXT_CHUNKS},
            "diverse": {"query": user_query, "top_k": MAX_CONTEXT_CHUNKS},
        }
    )

    # Prefer the final diverse-ranked list, but fall back gracefully.
    docs = []
    if isinstance(res, dict):
        docs = (res.get("diverse") or {}).get("documents") or []
        if not docs:
            docs = (res.get("rerank") or {}).get("documents") or []
        if not docs:
            docs = (res.get("join") or {}).get("documents") or []

    min_score = float(
        os.getenv("RAG_MIN_DOC_SCORE", os.getenv("MIN_DOC_SCORE", "0.35"))
    )
    eligible = [d for d in docs if (getattr(d, "score", 0.0) or 0.0) >= min_score]

    if strict_mode:
        grounding_pool = eligible
        if not grounding_pool:
            prompt = make_prompt(user_query, [], top_k=0)
            answer_text = query_ollama(prompt, model=model)
            return {
                "answer": answer_text,
                "citations": [],
                "manual_sections": [],
                "used_model": model,
                "top_pages": [],
            }
    else:
        grounding_pool = eligible if eligible else (docs[:1] if docs else [])

    if max_sections is None:
        max_sections = min(len(grounding_pool), MAX_CONTEXT_CHUNKS)

    grounding_docs = grounding_pool[:max_sections]

    sections = build_manual_sections(grounding_docs, max_sections=max_sections)
    citations = build_citations(grounding_docs)

    prompt = make_prompt(user_query, grounding_docs, top_k=len(grounding_docs))
    answer_text = query_ollama(prompt, model=model)

    return {
        "answer": answer_text,
        "citations": citations,
        "manual_sections": sections,
        "used_model": model,
        "top_pages": [s["page"] for s in sections],
    }


# -------------------------
# FastAPI setup
# -------------------------
app = FastAPI(title="Manual Support API")

# Allow localhost dev server on any port (5173-5180)
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:5177",
    "http://localhost:5178",
    "http://localhost:5179",
    "http://localhost:5180",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://127.0.0.1:5177",
    "http://127.0.0.1:5178",
    "http://127.0.0.1:5179",
    "http://127.0.0.1:5180",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print("✅ CORS middleware enabled")

# --- Load manuals.json dynamically ---
MANUALS_PATH = "/home/alex8642/LLM-chatbot/frontend/public/manuals/manuals.json"
if os.path.exists(MANUALS_PATH):
    with open(MANUALS_PATH) as f:
        manuals = json.load(f)
else:
    manuals = []


# -------------------------
# Pydantic models
# -------------------------
class AskRequest(BaseModel):
    # Accept both snake_case and the frontend's camelCase key.
    model_config = {"populate_by_name": True}

    manual_id: str
    query: str
    guardrails_enabled: bool = Field(default=False, alias="guardrailsEnabled")


class Citation(BaseModel):
    page: int
    product: Optional[str] = None


class Section(BaseModel):
    page: int
    product: Optional[str] = None
    snippet: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    manual_sections: List[Section]
    used_model: str
    top_pages: List[int]
    manual_id: Optional[str] = None


# -------------------------
# Endpoints
# -------------------------
@app.get("/manuals")
def get_manuals():
    if not manuals:
        return {"error": "No manuals found. Run ingestion first."}
    return manuals


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    result = answer_with_ollama(
        req.query,
        manual_id=req.manual_id,
        model=OLLAMA_MODEL,
        max_sections=None,
        strict_mode=req.guardrails_enabled,
    )
    return AskResponse(
        answer=result["answer"],
        citations=[Citation(**c) for c in result["citations"]],
        manual_sections=[Section(**s) for s in result["manual_sections"]],
        used_model=result["used_model"],
        top_pages=result["top_pages"],
        manual_id=req.manual_id,
    )
