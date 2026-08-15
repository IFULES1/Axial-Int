"""Embeddings — provider-agnostic (Cohere by default, OpenAI fallback).

Cohere embed-multilingual-v3 gives strong FR+EN retrieval. Fails loudly if no
key is configured — never silent mock vectors.
"""
from __future__ import annotations

import httpx

from app.config import get_settings
from app.errors import AppError

TIMEOUT = 60.0


def embedding_dim() -> int:
    s = get_settings()
    return s.embedding_dim_cohere if s.embedding_provider == "cohere" else 1536


def _cohere_embed(texts: list[str], input_type: str) -> list[list[float]]:
    import time

    s = get_settings()
    if not s.cohere_api_key:
        raise AppError("COHERE_API_KEY non configurée — embeddings indisponibles.",
                       503, code="embeddings_unavailable")
    payload = {"model": s.embedding_model_cohere, "texts": texts,
               "input_type": input_type, "embedding_types": ["float"]}
    headers = {"Authorization": f"Bearer {s.cohere_api_key}", "Content-Type": "application/json"}
    # Retry with backoff on rate limits (429) / transient 5xx — trial keys are
    # heavily throttled, so ingestion must be patient rather than crash.
    delay = 3.0
    for attempt in range(6):
        r = httpx.post("https://api.cohere.com/v2/embed", headers=headers,
                       json=payload, timeout=TIMEOUT)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("retry-after") or delay)
            time.sleep(min(wait, 30.0))
            delay = min(delay * 2, 30.0)
            continue
        r.raise_for_status()
        return r.json()["embeddings"]["float"]
    raise AppError("Cohere rate-limité (429) après plusieurs tentatives.", 503,
                   code="embeddings_rate_limited")


def _openai_embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    if not s.openai_api_key:
        raise AppError("OPENAI_API_KEY non configurée — embeddings indisponibles.",
                       503, code="embeddings_unavailable")
    from openai import OpenAI

    resp = OpenAI(api_key=s.openai_api_key).embeddings.create(
        model=s.embedding_model, input=texts)
    return [d.embedding for d in resp.data]


def embed_texts(texts: list[str], *, input_type: str = "search_document") -> list[list[float]]:
    """Embed a batch of documents (default) or queries (input_type='search_query')."""
    if not texts:
        return []
    if get_settings().embedding_provider == "cohere":
        # Cohere caps batch size at 96 texts per call.
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):
            out.extend(_cohere_embed(texts[i:i + 96], input_type))
        return out
    return _openai_embed(texts)


def embed_query(query: str) -> list[float]:
    return embed_texts([query], input_type="search_query")[0]
