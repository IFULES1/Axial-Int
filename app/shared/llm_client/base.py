"""Provider-agnostic LLM interfaces.

The rest of the app depends on these Protocols, never on a concrete vendor.
Swapping Perplexity/Claude/OpenAI for another provider means adding one adapter,
not touching business code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    tokens: int = 0
    citations: list[dict] = field(default_factory=list)
    # Pourquoi le modèle s'est arrêté. « max_tokens » signifie que le texte est
    # tronqué, souvent en plein mot — sans cette information, un rapport coupé
    # est indiscernable d'un rapport terminé, et il est facturé comme tel.
    stop_reason: str | None = None


@runtime_checkable
class WebSearchProvider(Protocol):
    """Generates an answer grounded in a live web search (+ optional context)."""

    name: str

    def available(self) -> bool: ...

    def generate(self, *, system: str, prompt: str, model: str | None = None,
                 max_tokens: int = 4000) -> LLMResult: ...


@runtime_checkable
class EnrichProvider(Protocol):
    """Refines/enriches an existing draft. No web search."""

    name: str

    def available(self) -> bool: ...

    def enrich(self, *, system: str, draft: str, model: str | None = None,
               max_tokens: int = 8000) -> LLMResult: ...


class ProviderUnavailable(RuntimeError):
    """Raised by a provider that is called while not configured/healthy."""
