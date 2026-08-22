"""Contenu Notion de l'utilisateur, injecté comme source d'une réponse.

Pourquoi l'API REST et pas le connecteur MCP : le serveur `mcp.notion.com`
exige son propre flux OAuth, distinct du jeton d'intégration que Notion délivre
pour son API. Le jeton dont nous disposons ouvre l'API REST — et la traverser
nous-mêmes a trois avantages : ça marche avec tous les modèles (pas seulement
Claude), ça marche en streaming, et le contenu rejoint le même pool numéroté que
le web et les documents, donc il est cité comme le reste.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("axial.integrations.notion")

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_CAR_PAGE = 4000


@dataclass
class PassageNotion:
    """Même forme que les passages RAG, pour rejoindre le pool de sources."""
    text: str
    source: str = "notion"
    score: float = 0.0
    meta: dict = field(default_factory=dict)


def _entetes(jeton: str) -> dict:
    return {"Authorization": f"Bearer {jeton}", "Notion-Version": VERSION,
            "Content-Type": "application/json"}


def _titre(objet: dict) -> str:
    for v in (objet.get("properties") or {}).values():
        if v.get("type") == "title" and v.get("title"):
            return "".join(t.get("plain_text", "") for t in v["title"]).strip()
    if objet.get("title"):
        return "".join(t.get("plain_text", "") for t in objet["title"]).strip()
    return "Page Notion"


def _texte_blocs(jeton: str, page_id: str) -> str:
    """Texte brut d'une page (premier niveau de blocs)."""
    try:
        r = httpx.get(f"{API}/blocks/{page_id}/children",
                      headers=_entetes(jeton), params={"page_size": 100}, timeout=30)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.debug("Lecture de page Notion impossible (%s) : %s", page_id, e)
        return ""
    morceaux: list[str] = []
    for b in r.json().get("results") or []:
        corps = b.get(b.get("type"), {})
        riche = corps.get("rich_text") or []
        ligne = "".join(t.get("plain_text", "") for t in riche).strip()
        if ligne:
            morceaux.append(ligne)
    return "\n".join(morceaux)[:MAX_CAR_PAGE]


# Corpus mis en cache par utilisateur : recharger l'espace à chaque message
# coûterait plusieurs secondes de latence pour un contenu qui bouge peu.
_cache: dict[str, tuple[float, list]] = {}
CACHE_SECONDES = 900
PAGES_MAX = 12


def passages(jeton: str, requete: str, limite: int = 4) -> list[PassageNotion]:
    """Pages de l'espace partagé, contenu inclus.

    On ne se fie PAS à la recherche de Notion pour juger la pertinence : elle
    fonctionne par mots-clés sur les titres, et une question rédigée en langage
    naturel lui fait remonter des pages sans rapport. On récupère l'espace
    partagé (les plus récemment modifiées d'abord) et c'est notre reranker,
    qui compare le sens, qui décide lesquelles servent la question.
    """
    from concurrent.futures import ThreadPoolExecutor

    try:
        r = httpx.post(f"{API}/search", headers=_entetes(jeton),
                       json={"page_size": PAGES_MAX,
                             "filter": {"property": "object", "value": "page"},
                             "sort": {"direction": "descending",
                                      "timestamp": "last_edited_time"}},
                       timeout=30)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001 — un espace injoignable ne bloque rien
        logger.warning("Lecture de l'espace Notion échouée : %s", e)
        return []

    objets = (r.json().get("results") or [])[:PAGES_MAX]

    def _charger(objet: dict) -> PassageNotion | None:
        corps = _texte_blocs(jeton, objet.get("id", ""))
        if not corps:
            return None
        titre = _titre(objet)
        return PassageNotion(
            text=f"{titre}\n{corps}",
            meta={"title": titre, "source": "Notion", "url": objet.get("url", "")},
        )

    with ThreadPoolExecutor(max_workers=6) as ex:
        charges = [p for p in ex.map(_charger, objets) if p is not None]
    logger.info("Espace Notion : %d page(s) exploitable(s)", len(charges))
    return charges


def passages_pour(db, user_id: str, requete: str, limite: int = 4) -> list[PassageNotion]:
    """Passages Notion de cet utilisateur, ou liste vide s'il n'a rien connecté."""
    from app.modules.integrations import service as integrations

    import time

    try:
        jeton = integrations.jeton_actif(db, user_id, "notion")
    except Exception:  # noqa: BLE001
        return []
    if not jeton:
        return []

    frais = _cache.get(user_id)
    if frais and (time.time() - frais[0]) < CACHE_SECONDES:
        return frais[1]
    corpus = passages(jeton, requete, limite)
    _cache[user_id] = (time.time(), corpus)
    return corpus
