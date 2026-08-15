"""Concrete search adapters: Exa, Tavily, Linkup.

Each returns normalized `SearchResult`s and fails soft (empty list + log) so the
orchestrator can degrade gracefully when one provider is down or rate-limited.
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings
from app.shared.search.base import SearchResult

logger = logging.getLogger("axial.search")
TIMEOUT = 20.0


class ExaProvider:
    name = "exa"

    def available(self) -> bool:
        return bool(get_settings().exa_api_key)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        key = get_settings().exa_api_key
        if not key:
            return []
        try:
            r = httpx.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json={"query": query, "numResults": limit,
                      "contents": {"text": {"maxCharacters": 600}}},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            out = []
            for it in r.json().get("results", []):
                out.append(SearchResult(
                    title=it.get("title") or it.get("url", ""),
                    url=it.get("url", ""),
                    snippet=(it.get("text") or "").strip()[:600],
                    provider=self.name,
                    score=float(it.get("score") or 0.0),
                    published_at=it.get("publishedDate"),
                ))
            return out
        except Exception as e:
            logger.warning("Exa search failed: %s", e)
            return []


class TavilyProvider:
    name = "tavily"

    def available(self) -> bool:
        return bool(get_settings().tavily_api_key)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        key = get_settings().tavily_api_key
        if not key:
            return []
        try:
            r = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": limit,
                      "search_depth": "advanced"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            out = []
            for it in r.json().get("results", []):
                out.append(SearchResult(
                    title=it.get("title") or it.get("url", ""),
                    url=it.get("url", ""),
                    snippet=(it.get("content") or "").strip()[:600],
                    provider=self.name,
                    score=float(it.get("score") or 0.0),
                    published_at=it.get("published_date"),
                ))
            return out
        except Exception as e:
            logger.warning("Tavily search failed: %s", e)
            return []


class LinkupProvider:
    name = "linkup"

    def available(self) -> bool:
        return bool(get_settings().linkup_api_key)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        key = get_settings().linkup_api_key
        if not key:
            return []
        try:
            r = httpx.post(
                "https://api.linkup.so/v1/search",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"q": query, "depth": "standard", "outputType": "searchResults"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            out = []
            for it in results[:limit]:
                out.append(SearchResult(
                    title=it.get("name") or it.get("title") or it.get("url", ""),
                    url=it.get("url", ""),
                    snippet=(it.get("content") or it.get("snippet") or "").strip()[:600],
                    provider=self.name,
                ))
            return out
        except Exception as e:
            logger.warning("Linkup search failed: %s", e)
            return []


_REGISTRY = {p.name: p for p in (ExaProvider(), TavilyProvider(), LinkupProvider())}


def get_provider(name: str):
    return _REGISTRY.get(name)
