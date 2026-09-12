"""Valorisation des appels aux modèles.

Sans cette table, aucune métrique de rentabilité n'est calculable : le coût
variable d'un rapport reste une estimation de coin de table, et la marge avec.

Les tarifs sont dans la configuration plutôt qu'en dur : ils changent
régulièrement chez les fournisseurs, et une correction ne doit pas demander un
déploiement. Ils sont exprimés en **micro-euros par million de tokens** pour
rester entiers — un flottant qui traîne dans des sommes de coûts finit par
dériver.

⚠️ Ordres de grandeur au 25/08/2026, à confirmer sur les grilles officielles.
Un tarif faux ne casse rien : il fausse une marge, ce qui est pire. Vérifie-les
avant de fonder une décision de prix dessus.
"""
from __future__ import annotations

import os

from app.config import get_settings

# micro-euros par million de tokens (1 € = 1 000 000 µ€)
_DEFAUTS = {
    "claude-sonnet-5":      (2_760_000, 13_800_000),   # ~3 $ / 15 $ le MTok
    "claude-opus-5":        (13_800_000, 69_000_000),
    "gemini-flash-latest":  (280_000, 2_300_000),
    "gemini-2.5-flash":     (280_000, 2_300_000),
}

# Repli pour un modèle inconnu : on prend le tarif d'un modèle premium plutôt
# que zéro. Sous-estimer un coût est plus dangereux que le sur-estimer.
_REPLI = (2_760_000, 13_800_000)


def _tarif(modele: str) -> tuple[int, int]:
    cle = (modele or "").strip()
    surcharge = os.getenv(f"TARIF_{cle.upper().replace('-', '_')}")
    if surcharge:
        try:
            e, s = surcharge.split(":")
            return int(e), int(s)
        except ValueError:
            pass
    for nom, tarif in _DEFAUTS.items():
        if cle.startswith(nom):
            return tarif
    return _REPLI


def cout_micro_eur(modele: str, entree: int, sortie: int) -> int:
    """Coût d'un appel, en micro-euros. Toujours un entier."""
    t_entree, t_sortie = _tarif(modele)
    return round((entree * t_entree + sortie * t_sortie) / 1_000_000)


def en_euros(micro: int | None) -> float:
    return round((micro or 0) / 1_000_000, 4)


# --- Recherche web ---------------------------------------------------------
# Les tarifs vivent dans `config.py` (`TARIF_RECHERCHE_<FOURNISSEUR>_MICRO_EUR`),
# pas ici : ce sont des valeurs de marché, pas des constantes de code, et une
# correction de grille ne doit pas demander un déploiement.


def _tarif_recherche(fournisseur: str) -> int:
    """Micro-euros par appel pour ce fournisseur, depuis la configuration."""
    s = get_settings()
    nom = (fournisseur or "").strip().lower().replace("-", "_")
    return getattr(s, f"tarif_recherche_{nom}_micro_eur",
                   s.tarif_recherche_defaut_micro_eur)


def cout_recherche_micro_eur(appels: dict[str, int] | None) -> int:
    """Coût d'un ensemble d'appels de recherche, par fournisseur."""
    if not appels:
        return 0
    return sum(_tarif_recherche(f) * max(0, int(n or 0))
               for f, n in appels.items())
