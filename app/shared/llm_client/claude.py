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
             max_tokens: int = 4000, mcp_servers: list | None = None,
             mcp_tools: list | None = None) -> LLMResult:
    """General text generation (premium tier — final reports).

    `mcp_servers` / `mcp_tools` branchent les outils du client (Notion…) :
    Claude interroge alors son espace de travail pendant la rédaction. Les deux
    listes vont ensemble — un serveur déclaré sans son `mcp_toolset` est rejeté.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ProviderUnavailable("ANTHROPIC_API_KEY non configurée")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.llm_report_model
    kwargs = {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if mcp_servers and mcp_tools:
        kwargs["mcp_servers"] = mcp_servers
        kwargs["tools"] = mcp_tools
        kwargs["betas"] = ["mcp-client-2025-11-20"]
    # Au-delà de ~16k tokens de sortie, une requête bloquante expire côté HTTP :
    # le SDK impose le streaming. On agrège nous-mêmes le message final.
    espace = client.beta.messages if "betas" in kwargs else client.messages
    if max_tokens > 16000:
        with espace.stream(**kwargs) as stream:
            message = stream.get_final_message()
    else:
        message = espace.create(**kwargs)
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


def stream(*, system: str, prompt: str, model: str | None = None,
           max_tokens: int = 4000, mcp_servers: list | None = None,
           mcp_tools: list | None = None):
    """Yield text chunks as they are produced (streaming variant of generate()).

    Avec des serveurs MCP, les appels d'outils sont exécutés côté Anthropic :
    le flux de texte reste le même pour l'appelant, il marque simplement une
    pause pendant que Claude interroge l'outil.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ProviderUnavailable("ANTHROPIC_API_KEY non configurée")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.llm_report_model
    kwargs = {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if mcp_servers and mcp_tools:
        kwargs["mcp_servers"] = mcp_servers
        kwargs["tools"] = mcp_tools
        kwargs["betas"] = ["mcp-client-2025-11-20"]
    espace = client.beta.messages if "betas" in kwargs else client.messages
    with espace.stream(**kwargs) as s:
        yield from s.text_stream
