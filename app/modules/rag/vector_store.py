"""Qdrant vector store wrapper.

Two logical corpora, same COSINE space (dim = current embedding provider):
  * user documents  → collection `documents`, filtered by `user_id`.
  * knowledge base   → collection `knowledge_base`, global (no user filter),
    with rich payload (category, source, sector, title…).

Storage mode follows QDRANT_URL: ":memory:" (ephemeral dev), a local path
(persistent embedded — survives restarts), or a server URL (prod).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.modules.rag import embeddings

USER_COLLECTION = "documents"
KB_COLLECTION = "knowledge_base"


@dataclass
class Passage:
    text: str
    score: float
    doc_id: str
    chunk_index: int = 0
    source: str = "user"          # "user" | "kb"
    meta: dict = field(default_factory=dict)


@lru_cache
def _client() -> QdrantClient:
    url = (get_settings().qdrant_url or "").strip()
    if not url or url == ":memory:":
        return QdrantClient(location=":memory:")
    if url.startswith("file:"):
        return QdrantClient(path=url[len("file:"):])
    if url.startswith((".", "/")):  # local path → persistent embedded
        return QdrantClient(path=url)
    return QdrantClient(url=url)


def ensure_collection(name: str) -> None:
    client = _client()
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=embeddings.embedding_dim(),
                                        distance=Distance.COSINE),
        )


def _point_id(doc_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk_index}"))


def upsert_chunks(doc_id: str, user_id: str, chunks: list[str],
                  vectors: list[list[float]], *, collection: str = USER_COLLECTION,
                  extra_payload: dict | None = None) -> int:
    ensure_collection(collection)
    base = extra_payload or {}
    points = [
        PointStruct(
            id=_point_id(doc_id, i),
            vector=vec,
            payload={"doc_id": doc_id, "user_id": user_id, "chunk_index": i,
                     "text": chunk, **base},
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True))
    ]
    if points:
        _client().upsert(collection_name=collection, points=points)
    return len(points)


def search(vector: list[float], *, user_id: str | None = None, top_k: int = 8,
           collection: str = USER_COLLECTION) -> list[Passage]:
    """Search a collection. When user_id is given, filter by owner (user docs).
    When None (knowledge base), search globally."""
    ensure_collection(collection)
    flt = None
    if user_id is not None:
        flt = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
    response = _client().query_points(
        collection_name=collection, query=vector, query_filter=flt, limit=top_k,
    )
    src = "kb" if collection == KB_COLLECTION else "user"
    out = []
    for h in response.points:
        p = h.payload or {}
        out.append(Passage(
            text=p.get("text", ""), score=h.score, doc_id=p.get("doc_id", ""),
            chunk_index=p.get("chunk_index", 0), source=src,
            meta={k: p[k] for k in ("title", "category", "source", "sector") if k in p},
        ))
    return out


def has_document(doc_id: str, *, collection: str = USER_COLLECTION) -> bool:
    """True if any chunk of this document is already indexed (for resumable ingest)."""
    ensure_collection(collection)
    res = _client().count(
        collection_name=collection, exact=True,
        count_filter=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )
    return res.count > 0


def delete_document(doc_id: str, *, collection: str = USER_COLLECTION) -> None:
    """Delete every chunk of a document (cascade from the app-DB delete)."""
    flt = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
    _client().delete(collection_name=collection, points_selector=flt)
