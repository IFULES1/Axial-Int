"""Provider & dependency health.

Exposes the *real* state of every external dependency so degradation is
observable, not mysterious. Used by GET /health/providers and by the analysis
module to decide which optional enrichers are available.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    required: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "configured": self.configured,
            "required": self.required,
            "detail": self.detail,
        }


def provider_statuses() -> list[ProviderStatus]:
    """Static configuration view (no network calls). Cheap and safe to call often."""
    s = get_settings()
    search_on = [p for p in ("exa", "tavily", "linkup")
                 if getattr(s, f"{p}_api_key", "")]
    return [
        # --- Web search: multi-provider, need at least one ---
        ProviderStatus("web_search", bool(search_on), required=True,
                       detail=f"actifs={','.join(search_on) or 'aucun'}"),
        # --- Embeddings (query + KB must share the same model) ---
        ProviderStatus("embeddings_cohere", bool(s.cohere_api_key), required=True,
                       detail=f"model={s.embedding_model_cohere}, provider={s.embedding_provider}"),
        # --- LLM chat tier (fast/cheap) ---
        ProviderStatus("llm_chat_gemini", bool(s.gemini_api_key), required=True,
                       detail=f"model={s.llm_chat_model}"),
        # --- LLM report tier (premium); chat can fall back to Gemini ---
        ProviderStatus("llm_report_claude", bool(s.anthropic_api_key), required=True,
                       detail=f"model={s.llm_report_model}"),
        # --- Rerank: improves ordering, degrades softly to heuristic ---
        ProviderStatus("rerank_cohere", bool(s.cohere_api_key), required=False,
                       detail=f"model={s.rerank_model}"),
        # --- Optional enrichers / infra ---
        ProviderStatus("pappers", bool(s.pappers_api_key), required=False),
        ProviderStatus("serper", bool(s.serper_api_key), required=False),
        ProviderStatus("stripe", bool(s.stripe_secret_key), required=False),
        ProviderStatus("presidio", s.pii_guard_mode != "off", required=False,
                       detail=f"mode={s.pii_guard_mode}"),
        ProviderStatus("analytics", bool(s.analytics_database_url) and s.analytics_enabled,
                       required=False),
    ]


def providers_summary() -> dict:
    statuses = provider_statuses()
    missing_required = [p.name for p in statuses if p.required and not p.configured]
    return {
        "ok": not missing_required,
        "missing_required": missing_required,
        "providers": [p.as_dict() for p in statuses],
    }
