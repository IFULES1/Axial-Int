"""Search orchestrator: fan-out → dedupe → rerank → top-K.

Queries every enabled provider in parallel, merges and de-duplicates the
results by canonical URL, then reranks the union with Cohere to produce a single
high-quality, cited context for synthesis. Resilient: providers that fail are
simply skipped.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from urllib.parse import urlparse

from app.config import get_settings
from app.shared.search import rerank
from app.shared.search.base import SearchResult
from app.shared.search.contraintes import Contraintes
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


def _repli_sans_domaines_inclus(contraintes: Contraintes | None) -> Contraintes | None:
    """Contraintes de relance (domaines inclus retirés), ou `None` si aucune
    relance n'est pertinente (pas de contraintes, ou pas de domaines inclus
    posés — le `None` sert alors de garde « pas de relance » à l'appelant)."""
    if contraintes is None or not contraintes.domaines_inclus:
        return None
    return replace(contraintes, domaines_inclus=())


def _niveaux_disponibles(settings) -> list[list]:
    """`search_tier_list` résolu en objets fournisseur : un fournisseur
    inconnu (`get_provider` renvoie `None`) ou sans clé (`available()` faux)
    est ignoré ; un niveau qui n'a plus aucun fournisseur après ce filtre est
    sauté entièrement (il n'apparaît pas dans la liste renvoyée)."""
    niveaux = []
    for noms in settings.search_tier_list:
        providers = [p for n in noms if (p := get_provider(n)) and p.available()]
        if providers:
            niveaux.append(providers)
    return niveaux


def _fan_out(providers: list, query: str, top_k: int,
            contraintes: Contraintes | None,
            compteur: dict[str, int] | None) -> list[SearchResult]:
    if compteur is not None:
        for p in providers:
            compteur[p.name] = compteur.get(p.name, 0) + 1
    merged: list[SearchResult] = []
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(p.search, query, top_k, contraintes=contraintes): p
                   for p in providers}
        for fut in as_completed(futures):
            try:
                merged.extend(fut.result())
            except Exception as e:  # already handled in adapters, belt-and-braces
                logger.warning("Provider %s crashed: %s", futures[fut].name, e)
    return merged


def _fan_out_multi(providers: list, angles: list[str], par_angle: int,
                   contraintes: Contraintes | None,
                   compteur: dict[str, int] | None) -> list[SearchResult]:
    taches = [(p, q) for p in providers for q in angles]
    if compteur is not None:
        for p, _ in taches:
            compteur[p.name] = compteur.get(p.name, 0) + 1
    merged: list[SearchResult] = []
    with ThreadPoolExecutor(max_workers=min(len(taches), 12)) as pool:
        futures = {pool.submit(p.search, q, par_angle, contraintes=contraintes): (p, q)
                   for p, q in taches}
        for fut in as_completed(futures):
            try:
                merged.extend(fut.result())
            except Exception as e:
                p, q = futures[fut]
                logger.warning("Provider %s a échoué sur « %s » : %s", p.name, q[:60], e)
    return merged


def _cascade(niveaux: list[list], fan_out, rerank_query: str, top_k: int,
            contraintes: Contraintes | None, compteur: dict[str, int] | None,
            nom_log: str) -> list[SearchResult]:
    """Cascade partagée par `search` et `search_multi` : interroge les
    niveaux l'un après l'autre, pool cumulatif dédupliqué, rerank du pool
    complet à chaque niveau. `fan_out(providers, contraintes)` fait le
    fan-out réel (un provider·requête à la fois pour `search`, tous les
    angles pour `search_multi`) — c'est le seul point qui diffère entre les
    deux appelants, d'où la factorisation (revue Task 2 : la boucle était
    dupliquée à l'identique, ce qui aurait divergé au premier correctif).

    Arrêt dès que `top_k` sources RÉELLEMENT pertinentes (score ≥ seuil,
    garde minimale exclue — `pertinents` rendu par `rerank_avec_etat`, pas
    `len(resultats)` qui inclut la garde même à score nul, cf. revue Task 2
    constat C1) sont réunies, ou que tous les niveaux ont été consultés. Sans
    scores réels (`reel=False` — pas de Cohere, panne, ou réponse sans
    résultat exploitable), on ne peut pas juger la pertinence : la cascade
    s'arrête dès que le pool dédupliqué atteint `top_k`, à n'importe quel
    niveau. `compteur["_niveaux"]` (préfixe `_` : métadonnée, jamais
    facturée comme un fournisseur — cf. `couts.cout_recherche_micro_eur`)
    reçoit le nombre de niveaux effectivement consultés ; `compteur["_ecartes"]`
    est écrit par le dernier appel à `rerank_avec_etat` (assignation, pas
    accumulation — voir sa docstring), donc reflète le rerank final sur le
    pool cumulé complet, pas la somme des écartés de chaque niveau.

    Relance sans domaines inclus (Task 1) : une seule fois pour toute la
    cascade (pas par niveau), si le pool dédupliqué est encore vide.
    """
    pool: list[SearchResult] = []
    resultats: list[SearchResult] = []
    relance_faite = False
    niveaux_utilises = 0

    for i, providers in enumerate(niveaux, 1):
        niveaux_utilises = i
        bruts = fan_out(providers, contraintes)
        pool.extend(bruts)
        deduped = _dedupe(pool)

        if not deduped and not relance_faite:
            repli = _repli_sans_domaines_inclus(contraintes)
            if repli is not None:
                relance_faite = True
                logger.info("%s : pool vide avec domaines inclus, relance sans eux.",
                            nom_log)
                bruts2 = fan_out(providers, repli)
                pool.extend(bruts2)
                deduped = _dedupe(pool)

        resultats, reel, pertinents = rerank.rerank_avec_etat(
            rerank_query, deduped, top_k, contraintes=contraintes, compteur=compteur)
        logger.info("%s niveau %d : %d bruts (ce niveau) → %d dédupliqués (cumulé) → "
                    "%d retenus dont %d pertinents",
                    nom_log, i, len(bruts), len(deduped), len(resultats), pertinents)

        assez = pertinents >= top_k if reel else len(deduped) >= top_k
        if assez:
            break

    if compteur is not None:
        compteur["_niveaux"] = niveaux_utilises
    return resultats


def search(query: str, top_k: int | None = None,
           contraintes: Contraintes | None = None,
           compteur: dict[str, int] | None = None) -> list[SearchResult]:
    """Run enabled providers by tier, merge, dedupe, rerank; return top-K results.

    Recherche à niveaux (`settings.search_tier_list`, voir `_cascade`) : le
    niveau 1 est interrogé seul, dédupliqué et reranké. Si le nombre de
    sources RÉELLEMENT pertinentes est inférieur à `top_k`, le niveau 2 est
    ajouté au pool (le pool complet est reranké, pas seulement le niveau 2),
    puis le niveau 3 si besoin.

    `contraintes` (optionnel — `None` = comportement actuel, aucun filtre) :
    fraîcheur et domaines transmis à chaque fournisseur. `compteur` —
    dictionnaire fourni par l'appelant, rempli du nombre d'appels par
    fournisseur (clés de métadonnées préfixées `_` : `_niveaux`, `_ecartes`
    — jamais des fournisseurs, jamais facturées). C'est ce qui rend le coût
    de recherche mesurable : il n'apparaît sur aucune facture ventilée par
    rapport.
    """
    settings = get_settings()
    top_k = top_k or settings.search_topk
    niveaux = _niveaux_disponibles(settings)
    if not niveaux:
        logger.info("No search provider configured/available.")
        return []

    def fan_out(providers: list, c: Contraintes | None) -> list[SearchResult]:
        return _fan_out(providers, query, top_k, c, compteur)

    return _cascade(niveaux, fan_out, query, top_k, contraintes, compteur, "Search")


def search_multi(queries: list[str], top_k: int | None = None,
                 requete_de_rang: str | None = None,
                 contraintes: Contraintes | None = None,
                 compteur: dict[str, int] | None = None) -> list[SearchResult]:
    """Plusieurs angles de recherche, un seul pool classé.

    Une requête unique ne ramène qu'une facette du sujet. Une étude de marché
    livrée le 24/08 sous-estimait un marché parce que la seule requête portait
    sur le dimensionnement : rien n'avait cherché le parc installé ni la voie
    d'homologation, et le modèle a traité ces absences comme des contraintes.

    Les angles élargissent la collecte ; le reranker reste seul juge de ce qui
    entre dans le contexte final, classé contre la question d'origine.

    `contraintes` propage comme dans `search`. Cascade à niveaux identique à
    `search` (voir `_cascade`), mais chaque niveau interroge TOUS les angles.
    """
    settings = get_settings()
    top_k = top_k or settings.search_topk
    angles = [q.strip() for q in queries if q and q.strip()]
    if not angles:
        return []
    if len(angles) == 1:
        return search(angles[0], top_k, contraintes=contraintes, compteur=compteur)

    niveaux = _niveaux_disponibles(settings)
    if not niveaux:
        logger.info("No search provider configured/available.")
        return []

    # Chaque angle interroge chaque fournisseur. On demande moins par angle que
    # le top_k final : le but est d'élargir la couverture, pas de noyer le
    # reranker sous des variantes du même résultat.
    par_angle = max(5, top_k // 2)
    requete = requete_de_rang or angles[0]

    def fan_out(providers: list, c: Contraintes | None) -> list[SearchResult]:
        return _fan_out_multi(providers, angles, par_angle, c, compteur)

    return _cascade(niveaux, fan_out, requete, top_k, contraintes, compteur,
                    "Recherche multi-angles")


def format_sources(results: list[SearchResult]) -> str:
    """Numbered, cited context block for prompt injection."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title} — {r.domain}\n{r.snippet}\nURL: {r.url}")
    return "\n\n".join(lines)
