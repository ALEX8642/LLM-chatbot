# api.py

# © 2025 Alexander Feht
# Licensed under the MIT License
# This project was created independently and is not affiliated with any employer.

import os
import json
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# -------------------------
# Haystack / Retrieval Setup
# -------------------------
from haystack import Pipeline
from haystack.components.joiners import DocumentJoiner
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore
from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
from haystack_integrations.components.retrievers.opensearch import OpenSearchBM25Retriever

qdrant = QdrantDocumentStore(url="http://localhost:6333", index="manuals", embedding_dim=384)
opensearch = OpenSearchDocumentStore(
    hosts="http://localhost:9200", username="admin", password="admin", index="manuals"
)

query_embedder = SentenceTransformersTextEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
dense_retriever = QdrantEmbeddingRetriever(document_store=qdrant, top_k=5)
bm25_retriever = OpenSearchBM25Retriever(document_store=opensearch, top_k=5)
joiner = DocumentJoiner()

pipe = Pipeline()
pipe.add_component("query_embedder", query_embedder)
pipe.add_component("dense", dense_retriever)
pipe.add_component("sparse", bm25_retriever)
pipe.add_component("join", joiner)
pipe.connect("query_embedder.embedding", "dense.query_embedding")
pipe.connect("dense.documents", "join.documents")
pipe.connect("sparse.documents", "join.documents")

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
    context = "\n\n".join([f"[Page {d.meta.get('page')}] {d.content}" for d in docs[:top_k]])
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
    return [{"page": d.meta.get("page", 1), "product": d.meta.get("product_id")} for d in docs]

def build_manual_sections(docs, max_sections: int = 3, snippet_chars: int = 280) -> List[Dict[str, Any]]:
    sections = []
    for d in docs[:max_sections]:
        txt = (d.content or "").replace("\n", " ").strip()
        snippet = txt[:snippet_chars]
        if len(txt) > snippet_chars:
            snippet += "…"
        sections.append({
            "page": d.meta.get("page", 1),
            "product": d.meta.get("product_id"),
            "snippet": snippet
        })
    return sections

def answer_with_ollama(user_query: str, manual_id: str, model: str = OLLAMA_MODEL, max_sections: int = 3) -> Dict[str, Any]:
    # Retrieve docs only for the selected manual
    filter_condition = {
        "operator": "==",
        "field": "manual_id",
        "value": manual_id
    }

    res = pipe.run({
        "query_embedder": {"text": user_query},
        "dense": {"filters": filter_condition},
        "sparse": {"query": user_query, "filters": filter_condition}
    })
    docs = res["join"]["documents"]

    grounding_docs = docs[:max_sections]
    sections = build_manual_sections(grounding_docs, max_sections=max_sections)
    citations = build_citations(grounding_docs)

    prompt = make_prompt(user_query, grounding_docs, top_k=max_sections)
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

# Allow both localhost and 127.0.0.1 for dev
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
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
    manual_id: str
    query: str

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
    result = answer_with_ollama(req.query, manual_id=req.manual_id, model=OLLAMA_MODEL, max_sections=3)
    return AskResponse(
        answer=result["answer"],
        citations=[Citation(**c) for c in result["citations"]],
        manual_sections=[Section(**s) for s in result["manual_sections"]],
        used_model=result["used_model"],
        top_pages=result["top_pages"],
        manual_id=req.manual_id,
    )
