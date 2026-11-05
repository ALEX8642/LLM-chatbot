"""Hybrid chunk index in Qdrant: dense embeddings plus BM25 sparse vectors, fused by RRF.

Dense vectors come from any ``Embedder`` (in-process sentence-transformers, or an
OpenAI-compatible ``/v1/embeddings`` endpoint). Sparse vectors are BM25 term weights over
tokens that keep identifiers whole and also split them ("P14-8969" -> "p14-8969", "p14",
"8969"); Qdrant applies IDF. Local mode (a directory) for development.
"""

from __future__ import annotations

import os
import re
import zlib
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from manualqa.chunks import Chunk

COLLECTION = "chunks"
K1, B = 1.2, 0.75
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-./][A-Za-z0-9]+)*")


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str | None = None,
        half: bool = False,
        batch_size: int = 16,
    ):
        from sentence_transformers import SentenceTransformer

        self.name, self._batch_size = model, batch_size
        kwargs = {"model_kwargs": {"torch_dtype": "float16"}} if half else {}
        self._model = SentenceTransformer(model, device=device, **kwargs)
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]:
        # Qwen3-Embedding: queries take the model's "query" prompt, documents none
        prompt = "query" if query and "query" in self._model.prompts else None
        vectors = self._model.encode(
            texts,
            prompt_name=prompt,
            normalize_embeddings=True,
            batch_size=self._batch_size,
        )
        return [v.tolist() for v in vectors]


class OpenAIEmbedder:
    def __init__(self, base_url: str, model: str, api_key: str | None = None):
        self.name, self._url, self._key = model, base_url.rstrip("/"), api_key
        self.dim = len(self.embed(["dimension probe"])[0])

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]:
        import requests

        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        resp = requests.post(
            f"{self._url}/v1/embeddings",
            json={"model": self.name, "input": texts},
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]


def make_embedder(spec: str, half: bool = False, batch_size: int = 16) -> Embedder:
    """``st:<model>`` or ``openai:<model>`` (endpoint from EMBED_BASE_URL/EMBED_API_KEY)."""
    kind, _, model = spec.partition(":")
    if kind == "st":
        return SentenceTransformerEmbedder(model, half=half, batch_size=batch_size)
    if kind == "openai":
        return OpenAIEmbedder(
            os.environ["EMBED_BASE_URL"], model, os.environ.get("EMBED_API_KEY")
        )
    raise ValueError(f"unknown embedder {spec!r}")


def tokens(text: str) -> list[str]:
    out = []
    for match in _TOKEN.finditer(text):
        tok = match.group(0).lower()
        out.append(tok)
        if re.search(r"[-./]", tok):
            out.extend(p for p in re.split(r"[-./]", tok) if p)
    return out


def _term_id(tok: str) -> int:
    return zlib.crc32(tok.encode()) & 0x7FFFFFFF


def sparse_vector(
    text: str, avg_len: float | None = None
) -> tuple[list[int], list[float]]:
    """BM25 term-frequency weights (IDF is applied by Qdrant)."""
    toks = tokens(text)
    length = len(toks) or 1
    avg = avg_len or length
    weights: dict[int, float] = {}
    for tok, tf in Counter(toks).items():
        w = tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / avg))
        weights[_term_id(tok)] = weights.get(_term_id(tok), 0.0) + w
    ids = sorted(weights)
    return ids, [weights[i] for i in ids]


def _query_sparse(text: str) -> tuple[list[int], list[float]]:
    ids = sorted({_term_id(t) for t in tokens(text)})
    return ids, [1.0] * len(ids)


def _client(path: Path | str):
    from qdrant_client import QdrantClient

    return QdrantClient(path=str(path))


def build_index(chunks: list[Chunk], path: Path | str, embedder: Embedder) -> None:
    from qdrant_client import models

    client = _client(path)
    try:
        if client.collection_exists(COLLECTION):
            client.delete_collection(COLLECTION)
        client.create_collection(
            COLLECTION,
            vectors_config={
                "dense": models.VectorParams(
                    size=embedder.dim, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        avg = sum(len(tokens(c.text)) for c in chunks) / max(1, len(chunks))
        for start in range(0, len(chunks), 64):
            batch = chunks[start : start + 64]
            dense = embedder.embed([c.text for c in batch])
            points = []
            for i, (c, vec) in enumerate(zip(batch, dense), start=start):
                ids, vals = sparse_vector(c.text, avg)
                points.append(
                    models.PointStruct(
                        id=i,
                        vector={
                            "dense": vec,
                            "bm25": models.SparseVector(indices=ids, values=vals),
                        },
                        payload=asdict(c),
                    )
                )
            client.upsert(COLLECTION, points)
    finally:
        client.close()


def search(
    query: str,
    path: Path | str,
    embedder: Embedder,
    k: int = 10,
    manual: str | None = None,
    pool: int = 50,
) -> list[tuple[Chunk, float]]:
    from qdrant_client import models

    flt = (
        models.Filter(
            must=[
                models.FieldCondition(
                    key="manual", match=models.MatchValue(value=manual)
                )
            ]
        )
        if manual
        else None
    )
    ids, vals = _query_sparse(query)
    client = _client(path)
    try:
        result = client.query_points(
            COLLECTION,
            prefetch=[
                models.Prefetch(
                    query=embedder.embed([query], query=True)[0],
                    using="dense",
                    limit=pool,
                    filter=flt,
                ),
                models.Prefetch(
                    query=models.SparseVector(indices=ids, values=vals),
                    using="bm25",
                    limit=pool,
                    filter=flt,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=k,
            with_payload=True,
        )
    finally:
        client.close()
    return [(Chunk(**p.payload), p.score) for p in result.points]
