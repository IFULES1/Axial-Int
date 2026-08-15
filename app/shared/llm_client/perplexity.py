"""Perplexity (Sonar) web-search provider.

Uses the OpenAI-compatible client against api.perplexity.ai. This is the primary
"live web + grounding" engine. If the key is missing or the call fails, callers
degrade gracefully (see analysis service) rather than crashing.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.shared.llm_client.base import LLMResult, ProviderUnavailable

logger = logging.getLogger("axial.llm.perplexity")
_BASE_URL = "https://api.perplexity.ai"


class PerplexityProvider:
    name = "perplexity"

    def available(self) -> bool:
        return bool(get_settings().perplexity_api_key)

    def generate(self, *, system: str, prompt: str, model: str | None = None,
                 max_tokens: int = 4000) -> LLMResult:
        settings = get_settings()
        if not settings.perplexity_api_key:
            raise ProviderUnavailable("PERPLEXITY_API_KEY non configurée")

        from openai import OpenAI

        client = OpenAI(api_key=settings.perplexity_api_key, base_url=_BASE_URL)
        model = model or settings.perplexity_model_analysis
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        choice = completion.choices[0]
        usage = getattr(completion, "usage", None)
        citations = getattr(completion, "citations", None) or []
        return LLMResult(
            text=choice.message.content or "",
            model=model,
            provider=self.name,
            tokens=getattr(usage, "total_tokens", 0) or 0,
            citations=[{"url": c} if isinstance(c, str) else c for c in citations],
        )
