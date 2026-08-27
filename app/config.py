"""Centralized, validated application configuration.

All environment variables are declared and typed here. The app fails fast at
startup if a required setting is missing, instead of blowing up deep in a
request. This is the single source of truth for config across every module.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core -------------------------------------------------------------
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Only this origin list is allowed by CORS. Never "*".
    allowed_origins: str = "http://localhost:3000"
    request_timeout_seconds: float = 120.0

    # --- Databases --------------------------------------------------------
    # App database (business data + auth mirror).
    database_url: str = "postgresql+psycopg://axial:axial@localhost:5432/axial"
    # Qdrant vector store.
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"

    # --- Auth ------------------------------------------------------------
    # "local"  → self-contained dev auth (no Supabase needed).
    # "supabase" → GoTrue-backed auth (production).
    # Both issue HS256 JWTs signed with supabase_jwt_secret and Supabase-shaped
    # claims, so the rest of the app is identical in either mode.
    auth_mode: Literal["local", "supabase"] = "local"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""
    jwt_ttl_seconds: int = 3600
    refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    # Registration policy (kept from the current product).
    require_invitation_code: bool = False
    allow_freemail: bool = False

    # --- Analytics (separate Supabase ANALYTICS project) -----------------
    analytics_database_url: str = ""
    analytics_enabled: bool = True

    # --- Web search (multi-provider: Exa + Tavily + Linkup) ---------------
    exa_api_key: str = ""
    tavily_api_key: str = ""
    linkup_api_key: str = ""
    # Comma-separated list of enabled providers, in fan-out order.
    search_providers: str = "exa,tavily,linkup"
    search_topk: int = 10  # results kept after dedup + rerank

    # --- Rerank + embeddings (Cohere) ------------------------------------
    cohere_api_key: str = ""
    rerank_model: str = "rerank-v3.5"
    embedding_provider: Literal["cohere", "openai"] = "cohere"
    embedding_model_cohere: str = "embed-multilingual-v3.0"
    embedding_dim_cohere: int = 1024

    # --- LLM (two-tier: Gemini for drafts/chat, Claude for final) --------
    gemini_api_key: str = ""
    # "-latest" auto-tracks the current Flash → immune to model retirements.
    llm_chat_model: str = "gemini-flash-latest"  # cheap/fast — chat & drafts
    llm_report_model: str = "claude-sonnet-5"    # premium — final reports

    # --- LLM / providers (legacy + embeddings) ---------------------------
    perplexity_api_key: str = ""
    perplexity_model_chat: str = "sonar"
    perplexity_model_analysis: str = "sonar-pro"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    anthropic_api_key: str = ""
    claude_enrichment_enabled: bool = False
    claude_enrichment_model: str = "claude-sonnet-5"

    @property
    def search_provider_list(self) -> list[str]:
        return [p.strip() for p in self.search_providers.split(",") if p.strip()]
    # Optional enrichers — absence simply disables them (graceful degradation).
    pappers_api_key: str = ""
    serper_api_key: str = ""

    # --- PII sidecar ------------------------------------------------------
    # Base investisseurs (projet Supabase distinct, accès lecture seule) :
    # alimente la cartographie des investisseurs.
    # Chiffrement des jetons OAuth des intégrations (Notion, Google).
    integrations_secret_key: str = ""
    notion_client_id: str = ""
    notion_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""

    investor_db_url: str = ""
    investor_db_key: str = ""

    presidio_url: str = "http://localhost:8010"
    # Coûts fixes mensuels en euros (VPS + Supabase + Resend + domaine…).
    # Saisis à la main, une fois par mois : ils n'apparaissent dans aucune base
    # de l'application. Sans eux, ni le coût total ni le point mort ne sont
    # calculables — le tableau de bord affiche « non renseigné » plutôt qu'un
    # zéro qui ferait croire à une structure gratuite.
    couts_fixes_mensuels_eur: float = 0.0

    # Jeton de lecture seule pour l'export vers Google Sheets. Distinct des
    # jetons de session : un script planifié ne peut pas se reconnecter, et un
    # JWT d'administration expire. Vide = endpoint fermé.
    metrics_export_token: str = ""

    pii_guard_mode: Literal["off", "shadow", "enforce"] = "shadow"
    pii_mapping_key: str = ""

    # --- Billing ----------------------------------------------------------
    # Priority order: a TEST key wins when present (dev safety — no real charges),
    # then the conventional live names. Prod Doppler config omits the test key.
    stripe_secret_key: str = Field(
        default="", validation_alias=AliasChoices(
            "STRIPE_TEST_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_API_KEY"))
    stripe_webhook_secret: str = ""

    @property
    def stripe_test_mode(self) -> bool:
        return self.stripe_secret_key.startswith("sk_test")

    # --- Email (worker) ---------------------------------------------------
    # Resend HTTP API (preferred) — one key, no SMTP config needed.
    resend_api_key: str = ""
    mail_from: str = "onboarding@resend.dev"  # Resend test sender; switch to a verified domain in prod
    # SMTP fallback (used only if RESEND_API_KEY is empty).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@axial.com"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @field_validator("database_url", "analytics_database_url")
    @classmethod
    def _coerce_asyncless_scheme(cls, v: str) -> str:
        # Accept the common "postgresql://" form and keep it; drivers are chosen
        # explicitly in db.py. Empty analytics URL is allowed (feature optional).
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Import and call this everywhere."""
    return Settings()
