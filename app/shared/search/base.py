"""Provider-agnostic web-search types.

Each provider (Exa, Tavily, Linkup) normalises its response into `SearchResult`,
so the orchestrator can merge, dedupe and rerank them uniformly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str          # short text used for reranking + context
    provider: str
    score: float = 0.0    # provider score, then rerank score
    published_at: str | None = None

    @property
    def domain(self) -> str:
        from urllib.parse import urlparse

        try:
            return (urlparse(self.url).netloc or "").lower().removeprefix("www.")
        except Exception:
            return ""


@runtime_checkable
class SearchProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def search(self, query: str, limit: int = 10) -> list[SearchResult]: ...
