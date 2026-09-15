"""Provider & dependency health.

Exposes the *real* state of every external dependency so degradation is
observable, not mysterious. Used by GET /health/providers and by the analysis
module to decide which optional enrichers are available.

Deux modes :
- `providers_summary()` (par défaut) : vue statique, sans appel réseau — ce
  qu'utilise la supervision, jamais bloquant.
- `providers_summary(reel=True)` : un appel de test court par fournisseur
  CONFIGURÉ, en parallèle, timeout 8 s chacun — réservé à un admin (voir
  `app/main.py`). Jamais d'exception hors de cette fonction : un fournisseur
  qui explose devient `ok=False` + `erreur`, jamais une 500.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeoutError
from dataclasses import dataclass

from app.config import get_settings
from app.shared.secrets import sans_secret

TIMEOUT_REEL_SECONDES = 8
_MOTEURS_RECHERCHE = ("exa", "tavily", "linkup", "perplexity")
_LONGUEUR_MAX_ERREUR = 200


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    required: bool
    detail: str = ""
    ok: bool | None = None
    latence_ms: int | None = None
    erreur: str | None = None

    def as_dict(self, *, inclure_reel: bool = False) -> dict:
        d = {
            "name": self.name,
            "configured": self.configured,
            "required": self.required,
            "detail": self.detail,
        }
        if inclure_reel:
            d["ok"] = self.ok
            d["latence_ms"] = self.latence_ms
            d["erreur"] = self.erreur
        return d


def _base_providers(reel: bool) -> list[ProviderStatus]:
    """Configuration statique de chaque fournisseur (aucun appel réseau).

    En mode réel, `web_search` (agrégat) laisse la place aux 4 moteurs
    individuels — ce sont eux qu'on peut réellement tester un par un.
    """
    s = get_settings()
    providers: list[ProviderStatus] = []
    if reel:
        for moteur in _MOTEURS_RECHERCHE:
            providers.append(ProviderStatus(
                moteur, bool(getattr(s, f"{moteur}_api_key", "")), required=False))
    else:
        search_on = [p for p in _MOTEURS_RECHERCHE if getattr(s, f"{p}_api_key", "")]
        providers.append(ProviderStatus(
            "web_search", bool(search_on), required=True,
            detail=f"actifs={','.join(search_on) or 'aucun'}"))
    providers += [
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
    return providers


def provider_statuses() -> list[ProviderStatus]:
    """Static configuration view (no network calls). Cheap and safe to call often."""
    return _base_providers(reel=False)


def _verifier_recherche(nom: str) -> None:
    from app.shared.search.providers import get_provider

    provider = get_provider(nom)
    if provider is None:
        raise RuntimeError("fournisseur de recherche introuvable")
    if not provider.search("Axial Intelligence test", 1):
        raise RuntimeError("aucun résultat")


def _verifier_llm(tier: str) -> None:
    from app.shared import llm_client

    llm_client.generate(system="Réponds par OK.", prompt="OK ?", tier=tier, max_tokens=5)


def _verifier_rerank() -> None:
    from app.shared.search.rerank import rerank_indices_avec_etat

    _, reel = rerank_indices_avec_etat("test", ["a", "b"], 1)
    if not reel:
        raise RuntimeError("repli identité (pas de score réel)")


def _verifier_pappers() -> None:
    from app.shared.enrich import pappers

    if not pappers.rechercher("Axial"):
        raise RuntimeError("aucun résultat")


_VERIFICATIONS = {
    "exa": lambda: _verifier_recherche("exa"),
    "tavily": lambda: _verifier_recherche("tavily"),
    "linkup": lambda: _verifier_recherche("linkup"),
    "perplexity": lambda: _verifier_recherche("perplexity"),
    "llm_chat_gemini": lambda: _verifier_llm("chat"),
    "llm_report_claude": lambda: _verifier_llm("report"),
    "rerank_cohere": _verifier_rerank,
    "pappers": _verifier_pappers,
}


def _verifications_reelles(noms: list[str]) -> dict[str, dict]:
    """Un appel de test par nom, EN PARALLÈLE, timeout individuel.

    Jamais d'exception hors de cette fonction : une panne, une exception ou
    un dépassement de délai devient `ok=False` + `erreur`, jamais une
    exception qui remonte.
    """
    resultats: dict[str, dict] = {}
    if not noms:
        return resultats
    with ThreadPoolExecutor(max_workers=len(noms)) as executeur:
        debuts = {nom: time.monotonic() for nom in noms}
        futures = {nom: executeur.submit(_VERIFICATIONS[nom]) for nom in noms}
        for nom, future in futures.items():
            try:
                future.result(timeout=TIMEOUT_REEL_SECONDES)
                resultats[nom] = {
                    "ok": True,
                    "latence_ms": int((time.monotonic() - debuts[nom]) * 1000),
                    "erreur": None,
                }
            except _FutureTimeoutError:
                resultats[nom] = {
                    "ok": False,
                    "latence_ms": None,
                    "erreur": f"délai dépassé ({TIMEOUT_REEL_SECONDES} s)",
                }
            except Exception as e:  # noqa: BLE001 — jamais d'exception hors de la fonction
                resultats[nom] = {
                    "ok": False,
                    "latence_ms": int((time.monotonic() - debuts[nom]) * 1000),
                    "erreur": sans_secret(str(e))[:_LONGUEUR_MAX_ERREUR],
                }
    return resultats


def providers_summary(reel: bool = False) -> dict:
    statuses = _base_providers(reel)
    if reel:
        a_verifier = [p.name for p in statuses if p.configured and p.name in _VERIFICATIONS]
        resultats = _verifications_reelles(a_verifier)
        for p in statuses:
            r = resultats.get(p.name)
            if r is not None:
                p.ok, p.latence_ms, p.erreur = r["ok"], r["latence_ms"], r["erreur"]
    missing_required = [p.name for p in statuses if p.required and not p.configured]
    echec_requis = reel and any(p.required and p.ok is False for p in statuses)
    return {
        "ok": not missing_required and not echec_requis,
        "missing_required": missing_required,
        "providers": [p.as_dict(inclure_reel=reel) for p in statuses],
    }
