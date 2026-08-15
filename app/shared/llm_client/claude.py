"""Claude enrichment provider.

Second-pass refinement of a draft report. No web search (deliberate: avoids
extra search cost). Gated by CLAUDE_ENRICHMENT_ENABLED + a valid key. Absence
disables enrichment cleanly.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.shared.llm_client.base import LLMResult, ProviderUnavailable

logger = logging.getLogger("axial.llm.claude")


def available() -> bool:
    return bool(get_settings().anthropic_api_key)


def generate(*, system: str, prompt: str, model: str | None = None,
             max_tokens: int = 4000) -> LLMResult:
    """General text generation (premium tier — final reports)."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ProviderUnavailable("ANTHROPIC_API_KEY non configurée")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.llm_report_model
    message = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    usage = getattr(message, "usage", None)
    tokens = 0
    if usage is not None:
        tokens = (getattr(usage, "input_tokens", 0) or 0) + (getattr(usage, "output_tokens", 0) or 0)
    return LLMResult(text=text, model=model, provider="claude", tokens=tokens)


class ClaudeProvider:
    name = "claude"

    def available(self) -> bool:
        s = get_settings()
        return bool(s.claude_enrichment_enabled and s.anthropic_api_key)

    def enrich(self, *, system: str, draft: str, model: str | None = None,
               max_tokens: int = 8000) -> LLMResult:
        settings = get_settings()
        if not (settings.claude_enrichment_enabled and settings.anthropic_api_key):
            raise ProviderUnavailable("Claude enrichment désactivé ou clé absente")

        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        model = model or settings.claude_enrichment_model
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": draft}],
        )
        text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
        usage = getattr(message, "usage", None)
        tokens = 0
        if usage is not None:
            tokens = (getattr(usage, "input_tokens", 0) or 0) + (
                getattr(usage, "output_tokens", 0) or 0
            )
        return LLMResult(text=text, model=model, provider=self.name, tokens=tokens)
