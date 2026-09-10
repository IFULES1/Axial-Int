"""Task 4 : notification d'erreur backend par email (§5.10)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.errors import install_error_handlers
from app.shared import notifier


def _active(monkeypatch):
    monkeypatch.setenv("ERREURS_NOTIF_ACTIVES", "true")
    get_settings.cache_clear()


def _desactive(monkeypatch):
    monkeypatch.setenv("ERREURS_NOTIF_ACTIVES", "false")
    get_settings.cache_clear()


def _appel(monkeypatch, envois, route="intelligence.post_message"):
    monkeypatch.setattr(notifier, "envoyer_brut",
                        lambda *a, **k: envois.append((a, k)) or (True, "id"))
    try:
        raise ValueError("boom")
    except ValueError as e:
        notifier.notifier_erreur(titre="t", route=route, methode="POST",
                                 user_email="a@b.com", exc=e, action="agir")


def setup_function(_fn):
    notifier._reinitialiser()


def teardown_function(_fn):
    notifier._reinitialiser()


def test_dedup_meme_signature_un_seul_envoi(monkeypatch):
    _active(monkeypatch)
    envois: list = []
    _appel(monkeypatch, envois)
    _appel(monkeypatch, envois)
    assert len(envois) == 1
    get_settings.cache_clear()


def test_deux_routes_differentes_deux_envois(monkeypatch):
    _active(monkeypatch)
    envois: list = []
    _appel(monkeypatch, envois, route="intelligence.post_message")
    _appel(monkeypatch, envois, route="intelligence.stream_message")
    assert len(envois) == 2
    get_settings.cache_clear()


def test_desactive_zero_envoi(monkeypatch):
    _desactive(monkeypatch)
    envois: list = []
    _appel(monkeypatch, envois)
    assert len(envois) == 0
    get_settings.cache_clear()


def test_ne_leve_jamais_meme_si_envoyer_brut_casse(monkeypatch):
    _active(monkeypatch)
    monkeypatch.setattr(notifier, "envoyer_brut",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("resend down")))
    try:
        raise ValueError("boom")
    except ValueError as e:
        notifier.notifier_erreur(titre="t", route="x", methode="POST",
                                 user_email=None, exc=e, action="agir")
    get_settings.cache_clear()


def test_corps_contient_les_champs_attendus(monkeypatch):
    _active(monkeypatch)
    captures: list = []

    def _fake(destinataire, sujet, texte, **k):
        captures.append((destinataire, sujet, texte))
        return True, "id"

    monkeypatch.setattr(notifier, "envoyer_brut", _fake)
    try:
        raise ValueError("boom")
    except ValueError as e:
        notifier.notifier_erreur(titre="Titre incident", route="/api/x", methode="POST",
                                 user_email="user@axial-ia.fr", exc=e,
                                 action="Vérifier le fournisseur LLM")
    assert len(captures) == 1
    destinataire, sujet, texte = captures[0]
    assert destinataire == get_settings().erreurs_notif_destinataire
    assert sujet == "[Axial] Erreur backend : POST /api/x"
    assert "user@axial-ia.fr" in texte
    assert "/api/x" in texte
    assert "Vérifier le fournisseur LLM" in texte
    assert "ValueError" in texte
    assert "boom" in texte
    get_settings.cache_clear()


def test_gestionnaire_renvoie_toujours_500_json(monkeypatch):
    """Le gestionnaire global doit rester fonctionnel même si la
    notification échoue en interne — jamais d'exception qui remplace le 500
    propre par une 500 non gérée."""
    _active(monkeypatch)
    monkeypatch.setattr(notifier, "envoyer_brut",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("resend down")))

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def _boom():
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Erreur interne."}}
    get_settings.cache_clear()


def test_gestionnaire_envoie_une_notification(monkeypatch):
    _active(monkeypatch)
    envois: list = []
    monkeypatch.setattr(notifier, "envoyer_brut",
                        lambda *a, **k: envois.append((a, k)) or (True, "id"))

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def _boom():
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    assert len(envois) == 1
    get_settings.cache_clear()
