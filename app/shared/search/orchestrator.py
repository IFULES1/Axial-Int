"""Search orchestrator: fan-out → dedupe → rerank → top-K.

Queries every enabled provider in parallel, merges and de-duplicates the
results by canonical URL, then reranks the union with Cohere to produce a single
high-quality, cited context for synthesis. Resilient: providers that fail are
simply skipped.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from app.config import get_settings
from app.shared.search import rerank
from app.shared.search.base import SearchResult
from app.shared.search.providers import get_provider

logger = logging.getLogger("axial.search.orchestrator")


def _canonical(url: str) -> str:
    try:
        p = urlparse(url)
        netloc = (p.netloc or "").lower().removeprefix("www.")
        path = (p.path or "").rstrip("/")
        return f"{netloc}{path}"
    except Exception:
        return url


def _dedupe(results: list[SearchResult]) -> list[SearchResult]:
    seen: dict[str, SearchResult] = {}
    for r in results:
        if not r.url:
            continue
        key = _canonical(r.url)
        # Keep the richest snippet on collision.
        if key not in seen or len(r.snippet) > len(seen[key].snippet):
            seen[key] = r
    return list(seen.values())


def search(query: str, top_k: int | None = None) -> list[SearchResult]:
    """Run all enabled providers, merge, dedupe, rerank; return top-K results."""
    settings = get_settings()
    top_k = top_k or settings.search_topk
    providers = [p for name in settings.search_provider_list
                 if (p := get_provider(name)) and p.available()]
    if not providers:
        logger.info("No search provider configured/available.")
        return []

    # Fan-out in parallel; each provider returns up to top_k.
    merged: list[SearchResult] = []
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(p.search, query, top_k): p for p in providers}
        for fut in as_completed(futures):
            try:
                merged.extend(fut.result())
            except Exception as e:  # already handled in adapters, belt-and-braces
                logger.warning("Provider %s crashed: %s", futures[fut].name, e)

    deduped = _dedupe(merged)
    logger.info("Search: %d raw → %d deduped across %d providers",
                len(merged), len(deduped), len(providers))
    return rerank.rerank(query, deduped, top_k)


def format_sources(results: list[SearchResult]) -> str:
    """Numbered, cited context block for prompt injection."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title} — {r.domain}\n{r.snippet}\nURL: {r.url}")
    return "\n\n".join(lines)
