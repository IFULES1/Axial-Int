"""Contraintes de recherche : fraîcheur, domaines, seuil de pertinence.

Chaque recherche web porte des contraintes dérivées du type de rapport et des
mots de la question — voir `docs/superpowers/specs/2026-09-14-sources-v2.md`
§1. `Contraintes` est un objet de valeur immuable transmis en option à
`orchestrator.search`/`search_multi`, aux fournisseurs et au reranker ;
`None` partout dans la chaîne préserve le comportement actuel (aucun filtre).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


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

# Mots-clés de la question → (fraicheur_jours ou None, domaines inclus additionnels).
# Insensibles à la casse, testés en FR et EN. `None` en fraicheur signifie
# « aucun filtre » (le moins restrictif) : il ne gagne que si aucune autre
# règle plus restrictive ne s'applique par ailleurs.
_MOTS_FRAICHEUR: tuple[tuple[re.Pattern, int | None, tuple[str, ...]], ...] = (
    (re.compile(r"\b(actualit\w*|r[ée]cent\w*|dernier\w*|derni[èe]res?|cette semaine|"
                r"ce mois|this week|latest|news)\b", re.IGNORECASE), 90, ()),
    (re.compile(r"\b(2026|cette ann[ée]e|this year)\b", re.IGNORECASE), 365, ()),
    (re.compile(r"\b(loi|d[ée]cret|r[èe]glement\w*|directive|rgpd|dsa|dma|"
                r"ai act|r[ée]glementation|regulation|compliance)\b", re.IGNORECASE),
     365, DOMAINES_OFFICIELS_FR_UE),
    (re.compile(r"\b(historique|depuis\s+20\d{2}|[ée]volution sur)\b", re.IGNORECASE),
     None, ()),
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
    mots de la question l'affinent. La règle la plus restrictive gagne — un
    `fraicheur_jours` plus petit est plus restrictif ; `None` (aucun filtre)
    ne l'emporte que si rien de plus restrictif n'a été détecté par ailleurs.
    """
    question = question or ""
    fraicheur_defaut, domaines_defaut = _DEFAUTS_PAR_TYPE.get(
        analysis_type, (None, ()))

    candidats_fraicheur: list[int] = []
    if fraicheur_defaut is not None:
        candidats_fraicheur.append(fraicheur_defaut)

    domaines_mots: tuple[str, ...] = ()
    correspondance_trouvee = False
    for motif, fraicheur, domaines in _MOTS_FRAICHEUR:
        if motif.search(question):
            correspondance_trouvee = True
            if fraicheur is not None:
                candidats_fraicheur.append(fraicheur)
            domaines_mots = _fusion_domaines(domaines_mots, domaines)

    if candidats_fraicheur:
        fraicheur = min(candidats_fraicheur)
    elif correspondance_trouvee:
        # Seule une règle « aucun filtre » (ex. historique) a matché.
        fraicheur = None
    else:
        fraicheur = fraicheur_defaut

    domaines_inclus = _fusion_domaines(domaines_defaut, domaines_mots)

    return Contraintes(
        fraicheur_jours=fraicheur,
        domaines_inclus=domaines_inclus,
        domaines_exclus=DOMAINES_EXCLUS_DEFAUT,
    )
