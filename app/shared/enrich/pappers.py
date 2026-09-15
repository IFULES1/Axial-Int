"""Pappers — registre des entreprises françaises (SIREN, dirigeants, comptes).

Alimente `etude_marche` et `analyse_concurrentielle` (spec §3) : des fiches
d'entreprises nommées dans la question ou repérées par le modèle rejoignent
le pool de sources web AVANT le rerank final, comme n'importe quel autre
fournisseur. Même politique que les fournisseurs de recherche
(`app/shared/search/providers.py`) : jamais d'exception hors du module,
repli `None`/`[]` + `logger.warning` + `notifier_fournisseur(..., bascule=True)`,
un compteur incrémenté par fiche réellement obtenue via `/v2/entreprise`
(clé `pappers`, lue génériquement par `billing/couts.py`) — la recherche qui
précède (`/v2/recherche`) n'est pas facturée, seule la fiche l'est.

Cache mémoire 24 h par SIREN : une fiche ne change pas d'une requête à
l'autre dans la même journée, et `/v2/entreprise` est l'appel le plus
coûteux du module.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata

import httpx

from app.config import get_settings
from app.shared.search.base import SearchResult
from app.shared.secrets import sans_secret

logger = logging.getLogger("axial.pappers")

BASE_URL = "https://api.pappers.fr/v2"
TIMEOUT = 10.0
CACHE_TTL_SECONDES = 24 * 3600
NOMS_MAX = 8

# Cache mémoire process-local : {siren: (horloge_depot, fiche)}.
_cache: dict[str, tuple[float, dict]] = {}
_cache_verrou = threading.Lock()


def _horloge() -> float:
    """Isolée pour être bouchonnable dans les tests (cache 24h)."""
    import time as _time

    return _time.monotonic()


def _alerte_fournisseur(erreur: BaseException) -> None:
    """Email « fournisseur indisponible » — import paresseux, n'échoue jamais."""
    try:
        from app.shared.notifier import notifier_fournisseur

        notifier_fournisseur(fournisseur="pappers", erreur=erreur,
                             fonction="enrichissement Pappers (registre des entreprises)",
                             bascule=True)
    except Exception:  # noqa: BLE001
        pass


def disponible() -> bool:
    return bool(get_settings().pappers_api_key)


def rechercher(nom: str) -> dict | None:
    """Première entreprise trouvée pour ce nom, ou `None`.

    Ne compte pas dans `compteur["pappers"]` : la spec tarife la FICHE
    (`/v2/entreprise`), pas la recherche qui la précède — voir `fiche()`.
    """
    nom = (nom or "").strip()
    settings = get_settings()
    cle = settings.pappers_api_key
    if not nom or not cle:
        return None
    try:
        r = httpx.get(
            f"{BASE_URL}/recherche",
            params={"q": nom, "api_token": cle, "par_page": 5},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("Pappers recherche a échoué pour %r : %s", nom, sans_secret(e))
        _alerte_fournisseur(e)
        return None
    candidats = [e for e in (data.get("resultats") or []) if e.get("siren")]
    if not candidats:
        return None
    # Homonymes : « N2F » rendait en tête une SCI immobilière (15/09). On
    # préfère une société d'édition / conseil informatique, puis la plus
    # grosse, et on écarte les SCI et holdings quand un autre candidat existe.
    return max(candidats, key=_score_candidat)


_NAF_LOGICIEL = ("58.2", "62.0", "63.1", "70.2", "73.1", "58.1", "46.5", "47.9")


def _score_candidat(e: dict) -> tuple:
    naf = str(e.get("code_naf") or "")
    forme = str(e.get("forme_juridique") or "").lower()
    effectif = str(e.get("effectif") or e.get("tranche_effectif") or "")
    chiffres = [int(x) for x in re.findall(r"\d+", effectif)]
    return (
        naf.startswith(_NAF_LOGICIEL),
        not ("civile" in forme or "holding" in forme or naf.startswith("68.")),
        max(chiffres) if chiffres else 0,
    )


def fiche(siren: str, compteur: dict[str, int] | None = None) -> dict | None:
    """Fiche complète d'une entreprise par SIREN, avec cache 24 h.

    `compteur["pappers"]` n'est incrémenté que si l'appel HTTP à
    `/v2/entreprise` part réellement — un coup de cache ne facture rien.
    """
    siren = re.sub(r"\D", "", siren or "")
    if not siren:
        return None

    now = _horloge()
    with _cache_verrou:
        entree = _cache.get(siren)
        if entree is not None and (now - entree[0]) < CACHE_TTL_SECONDES:
            return entree[1]

    settings = get_settings()
    cle = settings.pappers_api_key
    if not cle:
        return None
    try:
        if compteur is not None:
            compteur["pappers"] = compteur.get("pappers", 0) + 1
        r = httpx.get(
            f"{BASE_URL}/entreprise",
            params={"siren": siren, "api_token": cle},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("Pappers fiche a échoué pour %s : %s", siren, sans_secret(e))
        _alerte_fournisseur(e)
        return None

    with _cache_verrou:
        _cache[siren] = (now, data)
    return data


def _slug(nom: str) -> str:
    """`Ma Société S.A.S.` → `ma-societe-s-a-s` (accents retirés, non
    alphanumériques réduits à `-`, sans tirets en double ni en bordure)."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", nom or "")
        if not unicodedata.combining(c)
    )
    brut = re.sub(r"[^a-z0-9]+", "-", sans_accents.lower())
    return re.sub(r"-+", "-", brut).strip("-")


def _montant(valeur) -> str | None:
    """`3200000` → `3,2 M€` — les comptes Pappers sont en euros bruts."""
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    return f"{v / 1_000_000:.1f} M€".replace(".", ",")


def _snippet(fiche_data: dict) -> str:
    """Fiche en une phrase structurée en français. Champs absents omis."""
    parties: list[str] = []

    forme = fiche_data.get("forme_juridique")
    date_creation = str(fiche_data.get("date_creation") or "")
    annee_creation = date_creation[:4] if date_creation[:4].isdigit() else None
    if forme and annee_creation:
        parties.append(f"{forme} créée en {annee_creation}")
    elif forme:
        parties.append(forme)

    naf = fiche_data.get("code_naf")
    libelle_naf = fiche_data.get("libelle_code_naf")
    if naf and libelle_naf:
        parties.append(f"NAF {naf} ({libelle_naf})")
    elif naf:
        parties.append(f"NAF {naf}")

    effectif = str(fiche_data.get("effectif") or "").strip()
    if effectif:
        # Pappers rend tantôt un nombre, tantôt « Entre 50 et 99 salariés ».
        parties.append(effectif if "salari" in effectif.lower() else f"{effectif} salariés")

    ville = (fiche_data.get("siege") or {}).get("ville")
    if ville:
        parties.append(f"siège à {ville}")

    finances = fiche_data.get("finances") or []
    if finances:
        dernier = finances[-1]
        annee_f = dernier.get("annee")
        ca = _montant(dernier.get("chiffre_affaires"))
        if ca:
            parties.append(f"CA {annee_f} {ca}" if annee_f else f"CA {ca}")
        resultat = _montant(dernier.get("resultat"))
        if resultat:
            parties.append(f"résultat {resultat}")

    representants = fiche_data.get("representants") or []
    noms_dirigeants = []
    for rep in representants[:3]:
        nom_rep = rep.get("nom_complet")
        qualite = rep.get("qualite")
        if not nom_rep:
            continue
        noms_dirigeants.append(f"{nom_rep} ({qualite})" if qualite else nom_rep)
    if noms_dirigeants:
        parties.append("dirigeants : " + ", ".join(noms_dirigeants))

    return ", ".join(parties) + "." if parties else "Fiche registre sans détail disponible."


def sources_pappers(noms: list[str], compteur: dict[str, int] | None = None) -> list[SearchResult]:
    """Un `SearchResult` par société trouvée (8 fiches max), prêt à rejoindre
    le pool de sources web avant le rerank final."""
    if not disponible():
        return []

    resultats: list[SearchResult] = []
    noms_vus: set[str] = set()
    sirens_vus: set[str] = set()
    for nom in (noms or [])[:NOMS_MAX]:
        nom = (nom or "").strip()
        if not nom or nom.lower() in noms_vus:
            continue
        noms_vus.add(nom.lower())

        trouve = rechercher(nom)
        if not trouve or not trouve.get("siren"):
            continue
        siren = trouve["siren"]
        # Deux noms peuvent désigner la même entreprise (« Doctolib » et
        # « Doctolib SAS » côte à côte dans l'extraction du modèle) : une
        # seule fiche par SIREN dans le pool, même si `rechercher` est
        # relancé pour chaque nom.
        if siren in sirens_vus:
            continue
        sirens_vus.add(siren)

        data = fiche(siren, compteur=compteur)
        if not data:
            continue

        nom_affiche = data.get("nom_entreprise") or trouve.get("nom_entreprise") or nom
        slug = _slug(nom_affiche)
        url = (f"https://www.pappers.fr/entreprise/{slug}-{siren}" if slug
               else f"https://www.pappers.fr/entreprise/{siren}")
        resultats.append(SearchResult(
            title=nom_affiche,
            url=url,
            snippet=_snippet(data),
            provider="pappers",
        ))
        if len(resultats) >= NOMS_MAX:
            break
    return resultats
