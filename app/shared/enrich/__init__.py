"""Enrichissements optionnels (registres externes, etc.).

Chaque module ici suit la même règle que les fournisseurs de recherche :
jamais d'exception hors du module, repli `None`/`[]` + `logger.warning` +
`notifier_fournisseur(..., bascule=True)` si une clé est configurée mais que
l'appel échoue. Une clé absente désactive silencieusement l'enrichisseur.
"""
from __future__ import annotations
