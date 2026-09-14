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


def rerank_indices_avec_etat(
    query: str, documents: list[str], top_k: int,
) -> tuple[list[tuple[int, float]], bool]:
    """Comme `rerank_indices`, mais indique aussi si les scores sont réels.

    `reel=False` (repli identité — pas de clé, timeout, panne, ou réponse
    sans résultat exploitable) : tous les scores valent 0.0 et ne doivent
    jamais fonder un filtre de pertinence — un score à 0.0 par repli n'a rien
    à voir avec « ce résultat n'est pas pertinent ».
    """
    settings = get_settings()
    if not documents:
        return [], False
    identity = [(i, 0.0) for i in range(min(top_k, len(documents)))]
    if not settings.cohere_api_key:
        return identity, False
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
        if not pairs:
            return identity, False
        return pairs, True
    except Exception as e:
        logger.warning("Cohere rerank failed, keeping heuristic order: %s", e)
        try:
            from app.shared.notifier import notifier_fournisseur
            notifier_fournisseur(fournisseur="cohere", erreur=e,
                                 fonction="rerank des sources", bascule=True)
        except Exception:  # noqa: BLE001
            pass
        return identity, False


def rerank_indices(query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
    """Rerank arbitrary text documents against the query.

    Returns (original_index, relevance_score) pairs, best-first. Fails soft to
    identity order (first `top_k`) if Cohere is unavailable or errors. This is
    the shared primitive behind both web-only and combined web+internal ranking.
    """
    pairs, _ = rerank_indices_avec_etat(query, documents, top_k)
    return pairs


def rerank_avec_etat(query: str, results: list[SearchResult], top_k: int,
                     contraintes: Contraintes | None = None,
                     compteur: dict[str, int] | None = None,
                     ) -> tuple[list[SearchResult], bool, int]:
    """Comme `rerank`, mais indique aussi si les scores utilisés pour classer
    (et, le cas échéant, filtrer) sont réels, et combien de résultats sont
    RÉELLEMENT pertinents (score ≥ seuil, garde minimale exclue) — la cascade
    à niveaux de l'orchestrateur s'en sert pour décider d'appeler le niveau
    suivant : `reel` dit si « le nombre de résultats rendus » peut être
    interprété comme « le nombre de résultats pertinents » ou seulement comme
    « la taille du pool » (repli), et `pertinents` porte ce compte (revue
    Task 2, constat C1 : compter `len(résultats rendus)` confondait à tort
    les `garde_minimale` résultats toujours conservés — même à score nul —
    avec des résultats effectivement pertinents, ce qui pouvait arrêter la
    cascade alors qu'aucune source ne franchissait le seuil).

    Le filtre de seuil ne s'applique que si Cohere a réellement noté les
    résultats — pas seulement si une clé est configurée (`available()` ne dit
    rien de la réussite de l'appel). Une panne Cohere (timeout, 429, 503)
    retombe sur l'ordre heuristique à score 0.0 : sans ce garde-fou, `0.0 <
    seuil` pour tout le monde et seule la garde minimale survivrait à un
    incident fournisseur transitoire — exactement la dégradation silencieuse
    que « pas de filtre sans Cohere » doit éviter. Filet de sécurité
    additionnel : si tous les scores rendus valent exactement 0.0, on ne
    filtre pas non plus. Au moins `garde_minimale` résultats (les mieux
    classés) sont toujours conservés, même sous le seuil, pour ne jamais
    vider le contexte.

    `compteur["_ecartes"]` (préfixe `_` : métadonnée, jamais un fournisseur
    facturable — voir `couts.cout_recherche_micro_eur`) est ASSIGNÉ, pas
    accumulé : l'orchestrateur reranke le pool cumulatif complet à chaque
    niveau de la cascade et rappelle cette fonction à chaque fois avec le
    même `compteur` ; assigner plutôt qu'additionner fait que seule la
    dernière passe (le rerank final, sur le pool complet) compte, comme le
    veut la revue (constat Q2) — pas la somme des écartés de chaque niveau,
    qui recompte plusieurs fois les mêmes sources.
    """
    if not results:
        return [], False, 0
    documents = [f"{r.title}\n{r.snippet}" for r in results]
    pairs, reel = rerank_indices_avec_etat(query, documents, top_k)
    ranked = []
    for idx, score in pairs:
        results[idx].score = score
        ranked.append(results[idx])

    if not reel or all(r.score == 0.0 for r in ranked):
        return ranked, False, 0

    settings = get_settings()
    seuil = (contraintes.seuil_pertinence if contraintes is not None
             and contraintes.seuil_pertinence is not None
             else settings.seuil_pertinence_recherche)
    garde_minimale = (contraintes.garde_minimale if contraintes is not None
                      else Contraintes().garde_minimale)

    filtres = []
    ecartes = 0
    pertinents = 0
    for i, r in enumerate(ranked):
        est_pertinent = r.score >= seuil
        if est_pertinent:
            pertinents += 1
        if i < garde_minimale or est_pertinent:
            filtres.append(r)
        else:
            ecartes += 1

    if ecartes:
        logger.info("Rerank : %d résultat(s) écarté(s) sous le seuil de pertinence %.2f",
                    ecartes, seuil)
    if compteur is not None:
        compteur["_ecartes"] = ecartes
    return filtres, True, pertinents


def rerank(query: str, results: list[SearchResult], top_k: int,
          contraintes: Contraintes | None = None,
          compteur: dict[str, int] | None = None) -> list[SearchResult]:
    """Reranke, puis écarte les résultats sous le seuil de pertinence.

    Alias d'une ligne autour de `rerank_avec_etat`, gardé comme API publique
    stable (et pour la suite de tests héritée de la Task 1) : aucun appelant
    de production ne s'en sert — `orchestrator.py` appelle
    `rerank_avec_etat` directement pour lire `reel` et `pertinents`.
    """
    ranked, _, _ = rerank_avec_etat(query, results, top_k,
                                    contraintes=contraintes, compteur=compteur)
    return ranked
