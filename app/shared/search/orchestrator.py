"""Search orchestrator: fan-out → dedupe → rerank → top-K.

Queries every enabled provider in parallel, merges and de-duplicates the
results by canonical URL, then reranks the union with Cohere to produce a single
high-quality, cited context for synthesis. Resilient: providers that fail are
simply skipped.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from app.config import get_settings
from app.shared.search import rerank
from app.shared.search.base import SearchResult
from app.shared.search.providers import get_provider

logger = logging.getLogger("axial.search.orchestrator")


def _canonical(url: str) -> str:
    try:
        p = urlparse(url)
        netloc = (p.netloc or "").lower().removeprefix("www.")
        path = (p.path or "").rstrip("/")
        return f"{netloc}{path}"
    except Exception:
        return url


def _dedupe(results: list[SearchResult]) -> list[SearchResult]:
    seen: dict[str, SearchResult] = {}
    for r in results:
        if not r.url:
            continue
        key = _canonical(r.url)
        # Keep the richest snippet on collision.
        if key not in seen or len(r.snippet) > len(seen[key].snippet):
            seen[key] = r
    return list(seen.values())


def search(query: str, top_k: int | None = None,
           compteur: dict[str, int] | None = None) -> list[SearchResult]:
    """Run all enabled providers, merge, dedupe, rerank; return top-K results.

    `compteur` — dictionnaire fourni par l'appelant, rempli du nombre d'appels
    par fournisseur. C'est ce qui rend le coût de recherche mesurable : il
    n'apparaît sur aucune facture ventilée par rapport.
    """
    settings = get_settings()
    top_k = top_k or settings.search_topk
    providers = [p for name in settings.search_provider_list
                 if (p := get_provider(name)) and p.available()]
    if not providers:
        logger.info("No search provider configured/available.")
        return []
    if compteur is not None:
        for p in providers:
            compteur[p.name] = compteur.get(p.name, 0) + 1

    # Fan-out in parallel; each provider returns up to top_k.
    merged: list[SearchResult] = []
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(p.search, query, top_k): p for p in providers}
        for fut in as_completed(futures):
            try:
                merged.extend(fut.result())
            except Exception as e:  # already handled in adapters, belt-and-braces
                logger.warning("Provider %s crashed: %s", futures[fut].name, e)

    deduped = _dedupe(merged)
    logger.info("Search: %d raw → %d deduped across %d providers",
                len(merged), len(deduped), len(providers))
    return rerank.rerank(query, deduped, top_k)


def search_multi(queries: list[str], top_k: int | None = None,
                 requete_de_rang: str | None = None,
                 compteur: dict[str, int] | None = None) -> list[SearchResult]:
    """Plusieurs angles de recherche, un seul pool classé.

    Une requête unique ne ramène qu'une facette du sujet. Une étude de marché
    livrée le 24/08 sous-estimait un marché parce que la seule requête portait
    sur le dimensionnement : rien n'avait cherché le parc installé ni la voie
    d'homologation, et le modèle a traité ces absences comme des contraintes.

    Les angles élargissent la collecte ; le reranker reste seul juge de ce qui
    entre dans le contexte final, classé contre la question d'origine.
    """
    settings = get_settings()
    top_k = top_k or settings.search_topk
    angles = [q.strip() for q in queries if q and q.strip()]
    if not angles:
        return []
    if len(angles) == 1:
        return search(angles[0], top_k, compteur=compteur)

    providers = [p for name in settings.search_provider_list
                 if (p := get_provider(name)) and p.available()]
    if not providers:
        logger.info("No search provider configured/available.")
        return []

    # Chaque angle interroge chaque fournisseur. On demande moins par angle que
    # le top_k final : le but est d'élargir la couverture, pas de noyer le
    # reranker sous des variantes du même résultat.
    par_angle = max(5, top_k // 2)
    taches = [(p, q) for p in providers for q in angles]
    if compteur is not None:
        for p, _ in taches:
            compteur[p.name] = compteur.get(p.name, 0) + 1
    merged: list[SearchResult] = []
    with ThreadPoolExecutor(max_workers=min(len(taches), 12)) as pool:
        futures = {pool.submit(p.search, q, par_angle): (p, q) for p, q in taches}
        for fut in as_completed(futures):
            try:
                merged.extend(fut.result())
            except Exception as e:
                p, q = futures[fut]
                logger.warning("Provider %s a échoué sur « %s » : %s", p.name, q[:60], e)

    deduped = _dedupe(merged)
    logger.info("Recherche multi-angles : %d angles, %d bruts → %d dédupliqués",
                len(angles), len(merged), len(deduped))
    return rerank.rerank(requete_de_rang or angles[0], deduped, top_k)


def format_sources(results: list[SearchResult]) -> str:
    """Numbered, cited context block for prompt injection."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title} — {r.domain}\n{r.snippet}\nURL: {r.url}")
    return "\n\n".join(lines)
