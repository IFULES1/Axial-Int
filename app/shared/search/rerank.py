"""Cohere Rerank — the cross-provider "tri".

Scores every aggregated result against the query and returns them re-ordered.
Fails soft: if Cohere is unavailable, the orchestrator keeps its heuristic order.
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings
from app.shared.search.base import SearchResult
from app.shared.search.contraintes import Contraintes

logger = logging.getLogger("axial.search.rerank")
TIMEOUT = 20.0


def available() -> bool:
    return bool(get_settings().cohere_api_key)


def rerank_indices(query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
    """Rerank arbitrary text documents against the query.

    Returns (original_index, relevance_score) pairs, best-first. Fails soft to
    identity order (first `top_k`) if Cohere is unavailable or errors. This is
    the shared primitive behind both web-only and combined web+internal ranking.
    """
    settings = get_settings()
    if not documents:
        return []
    identity = [(i, 0.0) for i in range(min(top_k, len(documents)))]
    if not settings.cohere_api_key:
        return identity
    try:
        r = httpx.post(
            "https://api.cohere.com/v2/rerank",
            headers={"Authorization": f"Bearer {settings.cohere_api_key}",
                     "Content-Type": "application/json"},
            json={"model": settings.rerank_model, "query": query,
                  "documents": [d[:1024] for d in documents],
                  "top_n": min(top_k, len(documents))},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        pairs = []
        for item in r.json().get("results", []):
            idx = item.get("index")
            if idx is None or idx >= len(documents):
                continue
            pairs.append((idx, float(item.get("relevance_score") or 0.0)))
        return pairs or identity
    except Exception as e:
        logger.warning("Cohere rerank failed, keeping heuristic order: %s", e)
        try:
            from app.shared.notifier import notifier_fournisseur
            notifier_fournisseur(fournisseur="cohere", erreur=e,
                                 fonction="rerank des sources", bascule=True)
        except Exception:  # noqa: BLE001
            pass
        return identity


def rerank(query: str, results: list[SearchResult], top_k: int,
          contraintes: Contraintes | None = None,
          compteur: dict[str, int] | None = None) -> list[SearchResult]:
    """Reranke, puis écarte les résultats sous le seuil de pertinence.

    Le filtre ne s'applique que si Cohere a réellement noté les résultats
    (`available()`) — sans clé, l'ordre heuristique est conservé tel quel,
    aucun résultat n'est écarté. Au moins `garde_minimale` résultats (les
    mieux classés) sont toujours conservés, même sous le seuil, pour ne
    jamais vider le contexte.
    """
    if not results:
        return []
    documents = [f"{r.title}\n{r.snippet}" for r in results]
    ranked = []
    for idx, score in rerank_indices(query, documents, top_k):
        results[idx].score = score
        ranked.append(results[idx])

    if not available():
        return ranked

    settings = get_settings()
    seuil = (contraintes.seuil_pertinence if contraintes is not None
             and contraintes.seuil_pertinence is not None
             else settings.seuil_pertinence_recherche)
    garde_minimale = contraintes.garde_minimale if contraintes is not None else 3

    filtres = []
    ecartes = 0
    for i, r in enumerate(ranked):
        if i < garde_minimale or r.score >= seuil:
            filtres.append(r)
        else:
            ecartes += 1

    if ecartes:
        logger.info("Rerank : %d résultat(s) écarté(s) sous le seuil de pertinence %.2f",
                    ecartes, seuil)
    if compteur is not None:
        compteur["ecartes"] = compteur.get("ecartes", 0) + ecartes
    return filtres
