"""Contraintes de recherche : fraîcheur, domaines, seuil de pertinence.

Chaque recherche web porte des contraintes dérivées du type de rapport et des
mots de la question — voir `docs/superpowers/specs/2026-09-14-sources-v2.md`
§1. `Contraintes` est un objet de valeur immuable transmis en option à
`orchestrator.search`/`search_multi`, aux fournisseurs et au reranker ;
`None` partout dans la chaîne préserve le comportement actuel (aucun filtre).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Contraintes:
    fraicheur_jours: int | None = None       # None = pas de filtre
    domaines_inclus: tuple[str, ...] = ()    # privilégier (Exa/Tavily/Linkup includeDomains)
    domaines_exclus: tuple[str, ...] = ()
    seuil_pertinence: float | None = None    # None = reprendre le défaut settings
    garde_minimale: int = 3                  # on garde au moins N sources même sous le seuil


# Domaines exclus par défaut, partout : bruit / réseaux sociaux sans valeur
# de sourçage pour un rapport professionnel.
DOMAINES_EXCLUS_DEFAUT: tuple[str, ...] = (
    "pinterest.com", "facebook.com", "instagram.com", "tiktok.com", "quora.com",
)

# Domaines officiels FR/UE — privilégiés pour tout ce qui touche la
# réglementation (type de rapport ou mots de la question).
DOMAINES_OFFICIELS_FR_UE: tuple[str, ...] = (
    "legifrance.gouv.fr", "eur-lex.europa.eu", "economie.gouv.fr",
    "service-public.fr", "amf-france.org", "cnil.fr", "europa.eu",
    "senat.fr", "assemblee-nationale.fr",
)

# Défauts par type de rapport : (fraicheur_jours, domaines_inclus).
# `None` en clé = conversation (pas de type d'analyse) : aucun filtre par défaut.
_DEFAUTS_PAR_TYPE: dict[str | None, tuple[int | None, tuple[str, ...]]] = {
    "analyse_reglementaire": (365, DOMAINES_OFFICIELS_FR_UE),
    "analyse_risques": (365, ()),
    "veille_technologique": (365, ()),
    "analyse_concurrentielle": (730, ()),
    "etude_marche": (730, ()),
    "synthese_executive": (730, ()),
    "cartographie_investisseurs": (730, ()),
    None: (None, ()),
}

# « historique / depuis 20xx / évolution sur » neutralise toute fraîcheur —
# y compris le défaut du type de rapport — et l'emporte sur les autres règles
# de mots (décision Miradie, tour de revue 1 du 14/09). Vérifiée à part, avant
# les autres règles, plutôt que comme une candidate parmi d'autres du `min()`.
_MOT_HISTORIQUE = re.compile(r"\b(historique|depuis\s+20\d{2}|[ée]volution sur)\b",
                             re.IGNORECASE)


def _regles_mots(annee: int) -> tuple[tuple[re.Pattern, int, tuple[str, ...]], ...]:
    """Mots-clés de la question → (fraicheur_jours, domaines inclus additionnels).

    Insensibles à la casse, testés en FR et EN. `annee` est l'année courante,
    recalculée à chaque appel pour que le motif « année en cours » ne devienne
    pas faux au changement d'année.
    """
    return (
        (re.compile(r"\b(actualit\w*|r[ée]cent\w*|dernier\w*|derni[èe]res?|cette semaine|"
                    r"ce mois|this week|latest|news)\b", re.IGNORECASE), 90, ()),
        (re.compile(rf"\b({annee}|cette ann[ée]e|this year)\b", re.IGNORECASE), 365, ()),
        (re.compile(r"\b(loi|d[ée]cret|r[èe]glement\w*|directive|rgpd|dsa|dma|"
                    r"ai act|r[ée]glementation|regulation|compliance)\b", re.IGNORECASE),
         365, DOMAINES_OFFICIELS_FR_UE),
    )


def _fusion_domaines(*groupes: tuple[str, ...]) -> tuple[str, ...]:
    vus: dict[str, None] = {}
    for groupe in groupes:
        for d in groupe:
            vus.setdefault(d, None)
    return tuple(vus.keys())


def contraintes_pour(question: str, analysis_type: str | None = None) -> Contraintes:
    """Dérive les contraintes de recherche d'une question et d'un type de rapport.

    Fonction pure : le défaut du type de rapport est le point de départ, les
    mots de la question l'affinent. « historique / depuis 20xx / évolution
    sur » neutralise la fraîcheur inconditionnellement (y compris le défaut du
    type). Sinon, la règle la plus restrictive gagne entre le défaut du type
    et les mots de la question — un `fraicheur_jours` plus petit est plus
    restrictif.
    """
    question = question or ""
    fraicheur_defaut, domaines_defaut = _DEFAUTS_PAR_TYPE.get(
        analysis_type, (None, ()))
    historique = bool(_MOT_HISTORIQUE.search(question))

    candidats_fraicheur: list[int] = []
    if not historique and fraicheur_defaut is not None:
        candidats_fraicheur.append(fraicheur_defaut)

    domaines_mots: tuple[str, ...] = ()
    for motif, fraicheur, domaines in _regles_mots(date.today().year):
        if motif.search(question):
            if not historique:
                candidats_fraicheur.append(fraicheur)
            domaines_mots = _fusion_domaines(domaines_mots, domaines)

    fraicheur = None if historique else (
        min(candidats_fraicheur) if candidats_fraicheur else fraicheur_defaut)

    domaines_inclus = _fusion_domaines(domaines_defaut, domaines_mots)

    return Contraintes(
        fraicheur_jours=fraicheur,
        domaines_inclus=domaines_inclus,
        domaines_exclus=DOMAINES_EXCLUS_DEFAUT,
    )
