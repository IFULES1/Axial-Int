"""Concrete search adapters: Exa, Tavily, Linkup.

Each returns normalized `SearchResult`s and fails soft (empty list + log) so the
orchestrator can degrade gracefully when one provider is down or rate-limited.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

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
            body = {"api_key": key, "query": query, "max_results": limit,
                    "search_depth": "advanced"}
            if contraintes is not None:
                if contraintes.fraicheur_jours:
                    if contraintes.fraicheur_jours <= 365:
                        body["days"] = contraintes.fraicheur_jours
                    else:
                        body["time_range"] = "year"
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


_REGISTRY = {p.name: p for p in (ExaProvider(), TavilyProvider(), LinkupProvider())}


def get_provider(name: str):
    return _REGISTRY.get(name)
