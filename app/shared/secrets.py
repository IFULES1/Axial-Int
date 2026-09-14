"""Masquage de secrets dans les messages destinés aux journaux et aux alertes.

httpx (et les autres clients HTTP synchrones du dépôt) mettent l'URL complète
dans le message d'erreur — clé d'API comprise quand elle voyage en paramètre
de requête (Gemini, Cohere, Pappers…). Un `raise_for_status()` sur un 401
Pappers, par exemple, produit un message contenant
`…?q=...&api_token=<clé en clair>&par_page=3`.

Partagé entre `app.shared.llm_client` (journal applicatif de chaque
fournisseur) et `app.shared.notifier` (email d'alerte), pour qu'un
fournisseur de plus n'ait pas à redéfinir son propre masquage — et pour que
les deux emplacements reconnaissent exactement les mêmes noms de paramètre.
"""
from __future__ import annotations

import re

# `api_token` (Pappers), `api_key`/`apikey`/`key` (Gemini, Cohere…), `token`
# générique — insensible à la casse, uniquement en paramètre de requête
# (précédé de `?` ou `&`, comme le pose une URL).
SECRET_DANS_URL = re.compile(
    r"([?&](?:api_token|api_key|apikey|key|token)=)[^&'\"\s]+", re.IGNORECASE)


def sans_secret(err: BaseException | str) -> str:
    """Masque la valeur d'un paramètre d'URL sensible dans un message d'erreur
    OU un texte libre.

    Accepte aussi une chaîne : un appelant qui journalise un traceback complet
    avant de l'envoyer par email n'a pas à en tenir une deuxième copie du
    motif.
    """
    return SECRET_DANS_URL.sub(r"\1<masqué>", str(err))
