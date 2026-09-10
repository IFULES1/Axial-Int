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
