"""Fixtures partagées à toute la suite."""
from __future__ import annotations

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _pas_de_notification_erreur_reelle(monkeypatch):
    """Désactive les notifications d'erreur email par défaut pour toute la
    suite : aucun test ne doit pouvoir déclencher un envoi réel juste en
    provoquant une exception. Les tests du notifieur la réactivent
    explicitement."""
    monkeypatch.setenv("ERREURS_NOTIF_ACTIVES", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _qdrant_en_memoire(monkeypatch):
    """Aucun test ne touche un Qdrant réel.

    Le 15/09, la suite lancée sur le serveur de prod (QDRANT_URL du Doppler)
    a écrit 127 points de test dans la collection `knowledge_base` réelle :
    `vector_store._client()` est mis en cache et lisait la vraie URL. Ici,
    chaque test repart d'un client `:memory:` neuf.
    """
    from app.config import get_settings
    from app.modules.rag import vector_store

    monkeypatch.setenv("QDRANT_URL", ":memory:")
    get_settings.cache_clear()
    vector_store._client.cache_clear()
    yield
    vector_store._client.cache_clear()
    get_settings.cache_clear()
