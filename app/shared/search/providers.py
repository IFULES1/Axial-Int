"""Concrete search adapters: Perplexity, Exa, Tavily, Linkup.

Each returns normalized `SearchResult`s and fails soft (empty list + log) so the
orchestrator can degrade gracefully when one provider is down or rate-limited.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
import threading
import time

from app.config import get_settings
from app.shared.search.base import SearchResult
from app.shared.search.contraintes import Contraintes

logger = logging.getLogger("axial.search")
TIMEOUT = 20.0


def _iso_depuis(jours: int) -> str:
    """Date ISO 8601 (Exa `startPublishedDate`), `jours` avant aujourd'hui."""
    return (datetime.now(timezone.utc) - timedelta(days=jours)).strftime(
        "%Y-%m-%dT00:00:00.000Z")


def _date_depuis(jours: int) -> str:
    """Date ISO courte (Linkup `fromDate`), `jours` avant aujourd'hui."""
    return (datetime.now(timezone.utc) - timedelta(days=jours)).strftime("%Y-%m-%d")


def _domaines(contraintes: Contraintes, cle_inclus: str, cle_exclus: str) -> dict:
    """`domaines_inclus` privilégie sans exclure : plusieurs fournisseurs
    refusent la combinaison inclusion + exclusion (400). Les deux listes ne
    sont donc jamais envoyées ensemble — l'inclusion suffit à elle seule."""
    if contraintes.domaines_inclus:
        return {cle_inclus: list(contraintes.domaines_inclus)}
    if contraintes.domaines_exclus:
        return {cle_exclus: list(contraintes.domaines_exclus)}
    return {}


def _tavily_time_range(jours: int) -> str:
    """`time_range`, jamais `days` (validation prod du 14/09) : Tavily ignore
    silencieusement `include_domains` quand `days` est envoyé dans le même
    appel, mais le respecte avec `time_range`. `day`/`week`/`month` pour les
    fraîcheurs courtes, `year` au-delà de 31 jours (y compris > 365, comme
    avant)."""
    if jours <= 1:
        return "day"
    if jours <= 7:
        return "week"
    if jours <= 31:
        return "month"
    return "year"


def _domaines_perplexity(contraintes: Contraintes) -> list[str]:
    """`search_domain_filter` : inclus, sinon exclus préfixés `-`, jamais les
    deux, 10 domaines maximum (limite de l'API)."""
    if contraintes.domaines_inclus:
        return list(contraintes.domaines_inclus)[:10]
    if contraintes.domaines_exclus:
        return [f"-{d}" for d in contraintes.domaines_exclus][:10]
    return []


_MOTIF_PHRASE = re.compile(r"(?<=[.!?])\s+")


def _extrait_pour_citation(contenu: str, indice: int) -> str:
    """Phrase(s) de la réponse Perplexity qui citent `[indice]`, sinon vide."""
    marqueur = f"[{indice}]"
    if not contenu or marqueur not in contenu:
        return ""
    phrases = [p.strip() for p in _MOTIF_PHRASE.split(contenu) if marqueur in p]
    return " ".join(phrases).strip()


def _alerte_fournisseur(nom: str, erreur: BaseException) -> None:
    """Email « fournisseur indisponible » : les autres fournisseurs de la
    recherche continuent (repli actif), l'alerte sert à recharger ou à
    surveiller un incident. Import paresseux pour éviter un cycle."""
    try:
        from app.shared.notifier import notifier_fournisseur
        notifier_fournisseur(fournisseur=nom, erreur=erreur,
                             fonction="recherche web", bascule=True)
    except Exception:  # noqa: BLE001
        pass


class ExaProvider:
    name = "exa"

    def available(self) -> bool:
        return bool(get_settings().exa_api_key)

    def search(self, query: str, limit: int = 10,
               contraintes: Contraintes | None = None) -> list[SearchResult]:
        key = get_settings().exa_api_key
        if not key:
            return []
        try:
            body = {"query": query, "numResults": limit,
                    "contents": {"text": {"maxCharacters": 600}}}
            if contraintes is not None:
                if contraintes.fraicheur_jours:
                    body["startPublishedDate"] = _iso_depuis(contraintes.fraicheur_jours)
                body.update(_domaines(contraintes, "includeDomains", "excludeDomains"))
            r = httpx.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json=body,
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
            _alerte_fournisseur("exa", e)
            return []


class TavilyProvider:
    name = "tavily"

    def available(self) -> bool:
        return bool(get_settings().tavily_api_key)

    def search(self, query: str, limit: int = 10,
               contraintes: Contraintes | None = None) -> list[SearchResult]:
        key = get_settings().tavily_api_key
        if not key:
            return []
        try:
            # Tavily refuse (400) toute requête de plus de 400 caractères : le
            # 16/09, un participant a collé son pitch entier (7 024 caractères)
            # et les six angles ont échoué. Les autres moteurs acceptent plus.
            body = {"api_key": key, "query": query[:TAVILY_REQUETE_MAX], "max_results": limit,
                    "search_depth": "advanced"}
            if contraintes is not None:
                if contraintes.fraicheur_jours:
                    body["time_range"] = _tavily_time_range(contraintes.fraicheur_jours)
                body.update(_domaines(contraintes, "include_domains", "exclude_domains"))
            r = httpx.post(
                "https://api.tavily.com/search",
                json=body,
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
            _alerte_fournisseur("tavily", e)
            return []


class LinkupProvider:
    name = "linkup"

    def available(self) -> bool:
        return bool(get_settings().linkup_api_key)

    def search(self, query: str, limit: int = 10,
               contraintes: Contraintes | None = None) -> list[SearchResult]:
        key = get_settings().linkup_api_key
        if not key:
            return []
        try:
            body = {"q": query, "depth": "standard", "outputType": "searchResults"}
            if contraintes is not None:
                if contraintes.fraicheur_jours:
                    body["fromDate"] = _date_depuis(contraintes.fraicheur_jours)
                body.update(_domaines(contraintes, "includeDomains", "excludeDomains"))
            r = httpx.post(
                "https://api.linkup.so/v1/search",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
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
            _alerte_fournisseur("linkup", e)
            return []


_VERROU_PERPLEXITY = threading.Semaphore(2)
TAVILY_REQUETE_MAX = 400


class PerplexityProvider:
    """Perplexity Sonar comme FOURNISSEUR DE RECHERCHE : rend des
    `SearchResult`, pas une réponse générée — distinct du client
    `app.shared.llm_client.perplexity` (génération/grounding)."""

    name = "perplexity"

    def available(self) -> bool:
        return bool(get_settings().perplexity_api_key)

    def search(self, query: str, limit: int = 10,
               contraintes: Contraintes | None = None) -> list[SearchResult]:
        settings = get_settings()
        key = settings.perplexity_api_key
        if not key:
            return []
        try:
            body = {
                "model": settings.perplexity_model_chat,
                "messages": [
                    {"role": "system", "content": (
                        "Tu es un moteur de recherche. Réponds par une liste de "
                        "faits sourcés, une phrase par fait, en citant [n].")},
                    {"role": "user", "content": query},
                ],
                "return_related_questions": False,
            }
            if contraintes is not None:
                if contraintes.fraicheur_jours:
                    if contraintes.fraicheur_jours <= 31:
                        body["search_recency_filter"] = "month"
                    elif contraintes.fraicheur_jours <= 365:
                        body["search_recency_filter"] = "year"
                domaines = _domaines_perplexity(contraintes)
                if domaines:
                    body["search_domain_filter"] = domaines
            # Perplexity limite le débit par clé : six angles en parallèle
            # rendaient des 429 (constaté le 15/09). Deux appels simultanés au
            # plus, et un second essai après 2 s sur 429.
            with _VERROU_PERPLEXITY:
                r = httpx.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=body,
                    timeout=TIMEOUT,
                )
                if getattr(r, "status_code", 200) == 429:
                    time.sleep(2)
                    r = httpx.post(
                        "https://api.perplexity.ai/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json=body,
                        timeout=TIMEOUT,
                    )
            r.raise_for_status()
            data = r.json()
            message = ((data.get("choices") or [{}])[0].get("message") or {})
            contenu = message.get("content") or ""
            search_results = data.get("search_results") or []
            out: list[SearchResult] = []
            if search_results:
                for i, it in enumerate(search_results, 1):
                    url = it.get("url", "")
                    titre = it.get("title") or url
                    extrait = (it.get("snippet")
                              or _extrait_pour_citation(contenu, i)
                              or titre)
                    out.append(SearchResult(
                        title=titre,
                        url=url,
                        snippet=extrait.strip()[:600],
                        provider=self.name,
                        published_at=it.get("date"),
                    ))
            else:
                for i, url in enumerate(data.get("citations") or [], 1):
                    extrait = _extrait_pour_citation(contenu, i) or url
                    out.append(SearchResult(
                        title=url,
                        url=url,
                        snippet=extrait.strip()[:600],
                        provider=self.name,
                    ))
            return out[:limit]
        except Exception as e:
            logger.warning("Perplexity search failed: %s", e)
            _alerte_fournisseur("perplexity", e)
            return []


_REGISTRY = {p.name: p for p in (
    PerplexityProvider(), ExaProvider(), TavilyProvider(), LinkupProvider())}


def get_provider(name: str):
    return _REGISTRY.get(name)
