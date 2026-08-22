"""llm_client — provider accessors and health.

Business code imports `web_search_provider()` / `enrich_provider()` and the
`providers_health()` helper; it never imports a concrete vendor module.
"""
from __future__ import annotations

from app.shared.llm_client.base import (
    EnrichProvider,
    LLMResult,
    ProviderUnavailable,
    WebSearchProvider,
)
from app.shared.llm_client.claude import ClaudeProvider
from app.shared.llm_client.perplexity import PerplexityProvider

_web = PerplexityProvider()
_enrich = ClaudeProvider()


def web_search_provider() -> WebSearchProvider:
    return _web


def enrich_provider() -> EnrichProvider:
    return _enrich


def generation_available() -> bool:
    """True if at least one text-generation LLM (Gemini or Claude) is usable."""
    from app.shared.llm_client import claude, gemini

    return gemini.available() or claude.available()


def generate(*, system: str, prompt: str, tier: str = "chat",
             max_tokens: int = 4000, mcp_servers: list | None = None,
             mcp_tools: list | None = None) -> LLMResult:
    """Two-tier text generation with runtime failover.

    tier="report" → Claude first (premium, final reports); tier="chat"/"draft" →
    Gemini first (cheap/fast). If the preferred provider fails at runtime
    (e.g. a transient 503), fall back to the other configured provider.
    """
    import logging

    from app.shared.llm_client import claude, gemini

    logger = logging.getLogger("axial.llm")
    chain = ([("claude", claude), ("gemini", gemini)] if tier == "report"
             else [("gemini", gemini), ("claude", claude)])

    last_err: Exception | None = None
    for name, mod in chain:
        if not mod.available():
            continue
        try:
            # Seul Claude sait joindre des serveurs MCP ; Gemini reste le repli
            # sans outils plutôt que d'échouer.
            if mcp_servers and name == "claude":
                return mod.generate(system=system, prompt=prompt,
                                    max_tokens=max_tokens,
                                    mcp_servers=mcp_servers, mcp_tools=mcp_tools)
            return mod.generate(system=system, prompt=prompt, max_tokens=max_tokens)
        except Exception as e:  # noqa: BLE001 — try the next provider, whatever the cause
            last_err = e
            logger.warning("LLM %s a échoué, bascule sur le suivant : %s", name, e)
    if last_err:
        raise last_err
    raise ProviderUnavailable("Aucun LLM de génération configuré (Gemini/Claude).")


def stream_text(*, system: str, prompt: str, tier: str = "chat",
                max_tokens: int = 4000):
    """Streaming counterpart of generate(): yields text chunks.

    Failover only applies BEFORE the first chunk — once text has reached the
    user, switching provider mid-answer would splice two different replies
    together, so a late failure surfaces as an error instead.
    """
    import logging

    from app.shared.llm_client import claude, gemini

    logger = logging.getLogger("axial.llm")
    chain = ([("claude", claude), ("gemini", gemini)] if tier == "report"
             else [("gemini", gemini), ("claude", claude)])

    last_err: Exception | None = None
    for name, mod in chain:
        if not mod.available():
            continue
        started = False
        try:
            for chunk in mod.stream(system=system, prompt=prompt,
                                    max_tokens=max_tokens):
                started = True
                yield chunk
            return
        except Exception as e:  # noqa: BLE001
            if started:
                logger.warning("LLM %s a coupé en cours de réponse : %s", name, e)
                raise
            last_err = e
            logger.warning("LLM %s a échoué avant le 1er mot, bascule : %s", name, e)
    if last_err:
        raise last_err
    raise ProviderUnavailable("Aucun LLM de génération configuré (Gemini/Claude).")


def providers_health() -> dict[str, bool]:
    """Real availability of each provider, for GET /health/providers."""
    from app.shared.llm_client import claude, gemini

    return {"gemini": gemini.available(), "claude": claude.available(),
            "perplexity": _web.available()}


__all__ = [
    "web_search_provider",
    "enrich_provider",
    "generate",
    "generation_available",
    "providers_health",
    "LLMResult",
    "ProviderUnavailable",
    "WebSearchProvider",
    "EnrichProvider",
]
