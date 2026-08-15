"""Cohere Rerank — the cross-provider "tri".

Scores every aggregated result against the query and returns them re-ordered.
Fails soft: if Cohere is unavailable, the orchestrator keeps its heuristic order.
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings
from app.shared.search.base import SearchResult

logger = logging.getLogger("axial.search.rerank")
TIMEOUT = 20.0


def available() -> bool:
    return bool(get_settings().cohere_api_key)


def rerank_indices(query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
    """Rerank arbitrary text documents against the query.

    Returns (original_index, relevance_score) pairs, best-first. Fails soft to
    identity order (first `top_k`) if Cohere is unavailable or errors. This is
    the shared primitive behind both web-only and combined web+internal ranking.
    """
    settings = get_settings()
    if not documents:
        return []
    identity = [(i, 0.0) for i in range(min(top_k, len(documents)))]
    if not settings.cohere_api_key:
        return identity
    try:
        r = httpx.post(
            "https://api.cohere.com/v2/rerank",
            headers={"Authorization": f"Bearer {settings.cohere_api_key}",
                     "Content-Type": "application/json"},
            json={"model": settings.rerank_model, "query": query,
                  "documents": [d[:1024] for d in documents],
                  "top_n": min(top_k, len(documents))},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        pairs = []
        for item in r.json().get("results", []):
            idx = item.get("index")
            if idx is None or idx >= len(documents):
                continue
            pairs.append((idx, float(item.get("relevance_score") or 0.0)))
        return pairs or identity
    except Exception as e:
        logger.warning("Cohere rerank failed, keeping heuristic order: %s", e)
        return identity


def rerank(query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
    if not results:
        return []
    documents = [f"{r.title}\n{r.snippet}" for r in results]
    ranked = []
    for idx, score in rerank_indices(query, documents, top_k):
        results[idx].score = score
        ranked.append(results[idx])
    return ranked
