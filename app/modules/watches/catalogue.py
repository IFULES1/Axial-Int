"""Catalogue de flux RSS proposés aux utilisateurs.

Ajouter un flux demandait jusqu'ici de connaître son URL — un fondateur ne
connaît pas l'adresse RSS de Sifted ou de la CNIL. Le catalogue expose des
sources vérifiées, classées par thème, qu'on ajoute en un clic.

La liste vit dans `data/rss_feeds.csv` plutôt qu'en base : elle est éditoriale
et n'a pas à être migrée. Revue tour 1 (C1) : `data/` est gitignoré
(`.gitignore:30`), ce fichier n'est PAS versionné — c'est une donnée de
configuration du serveur, modifiée directement sur disque (ou via le script
`scripts/tester_flux_rss.py` pour la vérifier), jamais relue dans une pull
request.
"""
from __future__ import annotations

import csv
import functools
import logging
import pathlib

logger = logging.getLogger("axial.watches.catalogue")

_FICHIER = pathlib.Path(__file__).resolve().parents[3] / "data" / "rss_feeds.csv"

# Libellés lisibles pour les catégories techniques stockées en base.
LIBELLES = {
    "startup": "Écosystème startup",
    "vc": "Capital-risque",
    "financement": "Financement et levées",
    "reglementaire": "Réglementaire",
    "juridique": "Juridique",
    "tech": "Technologie",
    "produit": "Produit",
    "marche": "Marché",
    "concurrence": "Concurrence",
    "general": "Généraliste",
}


@functools.lru_cache(maxsize=1)
def catalogue() -> list[dict]:
    """Flux proposés, lus une fois puis gardés en mémoire."""
    if not _FICHIER.exists():
        logger.warning("Catalogue de flux introuvable : %s", _FICHIER)
        return []
    try:
        with _FICHIER.open(encoding="utf-8") as f:
            return [
                {"url": r["url"].strip(),
                 "category": r["category"].strip(),
                 "title": (r.get("title") or "").strip(),
                 "category_label": LIBELLES.get(r["category"].strip(),
                                                r["category"].strip())}
                for r in csv.DictReader(f) if r.get("url")
            ]
    except Exception as e:  # noqa: BLE001 — un catalogue illisible n'empêche pas la veille
        logger.warning("Catalogue de flux illisible : %s", e)
        return []


def par_url(url: str) -> dict | None:
    cible = (url or "").strip()
    return next((f for f in catalogue() if f["url"] == cible), None)
