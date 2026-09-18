"""Task 2 — flux RSS visibles et testés (spec ciblage-investisseurs-v2 §3).

Couvre : vérification d'un flux (bouchonnée : ok / 404 / XML invalide /
timeout), la route admin `/watches/feeds/verifier` (403 pour un non-admin),
`GET /watches/{id}/feeds` (filtre par catégories du skill + fusion du
catalogue), et le titre lu à l'ajout d'une URL libre.
"""
from __future__ import annotations

import types
import uuid

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
import app.modules.watches.models  # noqa: F401 — enregistre watches / rss_feeds
from app.modules.watches.models import RssFeed, Watch
from app.modules.watches import service


# --- socle de test -----------------------------------------------------------

def _engine():
    engine = create_engine("sqlite://", future=True,
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["watches"],
        Base.metadata.tables["rss_feeds"],
        Base.metadata.tables["watch_runs"],
    ])
    return engine


def _feed(db, user_id, *, url, category, title=None, verif_at=None, erreur=None):
    f = RssFeed(id=uuid.uuid4(), user_id=user_id, url=url, category=category,
               title=title, derniere_verification_at=verif_at, derniere_erreur=erreur)
    db.add(f)
    db.commit()
    return f


# --- réponses HTTP bouchonnées ------------------------------------------------

_FLUX_VALIDE = (
    "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel><title>Flux Test</title>"
    "<item><title>Article 1</title><link>http://ex.fr/1</link>"
    "<pubDate>Mon, 01 Sep 2025 10:00:00 GMT</pubDate></item>"
    "</channel></rss>"
)


class _FauxReponse:
    def __init__(self, status_code=200, content=b"", *, raise_status=None):
        self.status_code = status_code
        self.content = content
        self._raise_status = raise_status

    def raise_for_status(self):
        if self._raise_status:
            raise self._raise_status


def test_verifier_flux_ok(monkeypatch):
    monkeypatch.setattr(httpx, "get",
                        lambda url, **kw: _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
    r = service.verifier_flux("http://ex.fr/feed")
    assert r["ok"] is True
    assert r["statut_http"] == 200
    assert r["entrees"] == 1
    assert r["dernier"] is not None
    assert r["erreur"] is None
    assert r["titre"] == "Flux Test"


def test_verifier_flux_404(monkeypatch):
    def _get(url, **kw):
        resp = _FauxReponse(404, b"", raise_status=httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", url), response=httpx.Response(404)))
        return resp
    monkeypatch.setattr(httpx, "get", _get)
    r = service.verifier_flux("http://ex.fr/mort")
    assert r["ok"] is False
    assert r["statut_http"] == 404
    assert r["erreur"]


def test_verifier_flux_xml_invalide(monkeypatch):
    monkeypatch.setattr(httpx, "get",
                        lambda url, **kw: _FauxReponse(200, b"<not><valid"))
    r = service.verifier_flux("http://ex.fr/invalide")
    assert r["ok"] is False
    assert r["entrees"] == 0
    assert r["erreur"]


def test_verifier_flux_timeout(monkeypatch):
    def _boom(url, **kw):
        raise httpx.TimeoutException("timeout")
    monkeypatch.setattr(httpx, "get", _boom)
    r = service.verifier_flux("http://ex.fr/lent")
    assert r["ok"] is False
    assert "timeout" in r["erreur"].lower()


def test_lire_titre_flux_best_effort(monkeypatch):
    monkeypatch.setattr(httpx, "get",
                        lambda url, **kw: _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
    assert service.lire_titre_flux("http://ex.fr/feed") == "Flux Test"

    def _boom(url, **kw):
        raise RuntimeError("réseau down")
    monkeypatch.setattr(httpx, "get", _boom)
    assert service.lire_titre_flux("http://ex.fr/feed") is None


# --- verifier_tous : met à jour les flux utilisateurs, pas le catalogue ------

def test_verifier_tous_met_a_jour_les_flux_utilisateurs(monkeypatch):
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        f_ok = _feed(db, uid, url="http://ex.fr/ok", category="tech")
        f_ko = _feed(db, uid, url="http://ex.fr/ko", category="tech")

        def _get(url, **kw):
            if url == "http://ex.fr/ok":
                return _FauxReponse(200, _FLUX_VALIDE.encode("utf-8"))
            raise httpx.TimeoutException("timeout")
        monkeypatch.setattr(httpx, "get", _get)
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])

        resultats = service.verifier_tous(db)
        assert {r["url"] for r in resultats} == {"http://ex.fr/ok", "http://ex.fr/ko"}

        db.refresh(f_ok)
        db.refresh(f_ko)
        assert f_ok.derniere_verification_at is not None
        assert f_ok.derniere_erreur is None
        assert f_ko.derniere_verification_at is not None
        assert f_ko.derniere_erreur


def test_verifier_tous_inclut_le_catalogue_sans_ecrire(monkeypatch):
    engine = _engine()
    with Session(engine) as db:
        monkeypatch.setattr(httpx, "get",
                            lambda url, **kw: _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue",
                            lambda: [{"url": "http://cat.fr/feed", "category": "tech",
                                     "title": "Cat", "category_label": "Technologie"}])
        resultats = service.verifier_tous(db)
        assert any(r["url"] == "http://cat.fr/feed" for r in resultats)
        # aucun RssFeed n'a été créé pour l'entrée catalogue
        assert db.scalars(select(RssFeed)).first() is None


# --- feeds_pour_watch : filtre par catégories + fusion catalogue ------------

def test_feeds_pour_watch_filtre_par_categorie_et_fusionne_catalogue(monkeypatch):
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        _feed(db, uid, url="http://moi.fr/tech", category="tech", title="Mon flux tech")
        _feed(db, uid, url="http://moi.fr/hors-sujet", category="juridique", title="Hors sujet")

        monkeypatch.setattr(
            "app.modules.watches.catalogue.catalogue",
            lambda: [
                {"url": "http://cat.fr/tech", "category": "tech", "title": "Cat Tech",
                 "category_label": "Technologie"},
                {"url": "http://cat.fr/marche", "category": "marche", "title": "Cat Marché",
                 "category_label": "Marché"},
            ],
        )
        watch = types.SimpleNamespace(skill="produit_tech")  # rss_categories: produit, tech, marche, general
        items = service.feeds_pour_watch(db, str(uid), watch)
        urls = {i["url"] for i in items}
        assert "http://moi.fr/tech" in urls
        assert "http://moi.fr/hors-sujet" not in urls          # catégorie hors skill
        assert "http://cat.fr/tech" in urls
        assert "http://cat.fr/marche" in urls

        moi = next(i for i in items if i["url"] == "http://moi.fr/tech")
        assert moi["origine"] == "moi"
        assert moi["etat"] == "inconnu"                        # jamais vérifié

        cat = next(i for i in items if i["url"] == "http://cat.fr/tech")
        assert cat["origine"] == "catalogue"
        assert cat["etat"] == "inconnu"


def test_feeds_pour_watch_etat_catalogue_reprend_celui_du_flux_utilisateur(monkeypatch):
    """Un flux catalogue déjà suivi par l'utilisateur reprend SON état de
    vérification, plutôt que de rester 'inconnu' malgré une vérification faite."""
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc)
        _feed(db, uid, url="http://cat.fr/tech", category="tech", title="Déjà suivi",
             verif_at=now, erreur="mort")

        monkeypatch.setattr(
            "app.modules.watches.catalogue.catalogue",
            lambda: [{"url": "http://cat.fr/tech", "category": "tech", "title": "Cat Tech",
                     "category_label": "Technologie"}],
        )
        watch = types.SimpleNamespace(skill="produit_tech")
        items = service.feeds_pour_watch(db, str(uid), watch)
        # un seul item pour cette URL, celui de l'utilisateur (origine "moi")
        assert len([i for i in items if i["url"] == "http://cat.fr/tech"]) == 1
        item = items[0]
        assert item["origine"] == "moi"
        assert item["etat"] == "erreur"


# --- routes HTTP -------------------------------------------------------------

def _http(engine, *, is_admin, user_id=None):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app as _app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_admin, get_current_user

    uid = user_id or str(uuid.uuid4())
    utilisateur = AuthUser(id=uid, email="u@axial-ia.fr", is_admin=is_admin)

    def _db():
        with Session(engine) as s:
            yield s

    def _admin_dep():
        if not is_admin:
            from app.errors import AppError
            raise AppError("Accès réservé aux administrateurs.", 403, code="forbidden")
        return utilisateur

    _app.dependency_overrides[get_db] = _db
    _app.dependency_overrides[get_current_user] = lambda: utilisateur
    _app.dependency_overrides[get_current_admin] = _admin_dep
    return _app, TestClient(_app), uid


def test_route_verifier_feeds_403_pour_non_admin():
    engine = _engine()
    app_, client, _ = _http(engine, is_admin=False)
    try:
        r = client.post("/watches/feeds/verifier")
        assert r.status_code == 403
    finally:
        app_.dependency_overrides.clear()


def test_route_verifier_feeds_admin_ok(monkeypatch):
    engine = _engine()
    app_, client, uid = _http(engine, is_admin=True)
    try:
        with Session(engine) as db:
            _feed(db, uuid.UUID(uid), url="http://ex.fr/a", category="tech")
        monkeypatch.setattr(httpx, "get",
                            lambda url, **kw: _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        r = client.post("/watches/feeds/verifier")
        assert r.status_code == 200, r.text
        corps = r.json()
        assert any(item["url"] == "http://ex.fr/a" and item["ok"] for item in corps)
    finally:
        app_.dependency_overrides.clear()


def test_route_watch_feeds_filtre_et_fusionne(monkeypatch):
    engine = _engine()
    app_, client, uid = _http(engine, is_admin=False)
    try:
        with Session(engine) as db:
            watch = Watch(id=uuid.uuid4(), user_id=uuid.UUID(uid), name="Veille tech",
                          query="tech", skill="produit_tech")
            db.add(watch)
            _feed(db, uuid.UUID(uid), url="http://moi.fr/tech", category="tech", title="Mon flux")
            _feed(db, uuid.UUID(uid), url="http://moi.fr/juridique", category="juridique")
            db.commit()
            watch_id = str(watch.id)

        monkeypatch.setattr(
            "app.modules.watches.catalogue.catalogue",
            lambda: [{"url": "http://cat.fr/tech", "category": "tech", "title": "Cat Tech",
                     "category_label": "Technologie"}],
        )
        r = client.get(f"/watches/{watch_id}/feeds")
        assert r.status_code == 200, r.text
        corps = r.json()
        urls = {i["url"] for i in corps}
        assert "http://moi.fr/tech" in urls
        assert "http://moi.fr/juridique" not in urls
        assert "http://cat.fr/tech" in urls
        for item in corps:
            assert item["etat"] in ("ok", "erreur", "inconnu")
            assert item["origine"] in ("moi", "catalogue")
    finally:
        app_.dependency_overrides.clear()


def test_route_watch_feeds_404_pour_veille_dautrui():
    engine = _engine()
    app_, client, uid = _http(engine, is_admin=False)
    try:
        with Session(engine) as db:
            autre = Watch(id=uuid.uuid4(), user_id=uuid.uuid4(), name="Pas la mienne",
                          query="x", skill="marche")
            db.add(watch := autre)
            db.commit()
            watch_id = str(watch.id)
        r = client.get(f"/watches/{watch_id}/feeds")
        assert r.status_code == 404
    finally:
        app_.dependency_overrides.clear()


# --- titre lu à l'ajout d'une URL libre --------------------------------------

def test_ajout_flux_url_libre_lit_le_titre(monkeypatch):
    engine = _engine()
    app_, client, uid = _http(engine, is_admin=False)
    try:
        monkeypatch.setattr(httpx, "get",
                            lambda url, **kw: _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        r = client.post("/watches/feeds", json={"url": "http://ex.fr/libre", "category": "tech"})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Flux Test"
    finally:
        app_.dependency_overrides.clear()


def test_ajout_flux_url_libre_avec_titre_fourni_ne_verifie_pas(monkeypatch):
    engine = _engine()
    app_, client, uid = _http(engine, is_admin=False)
    try:
        appele = {"n": 0}

        def _boom(url, **kw):
            appele["n"] += 1
            raise AssertionError("ne doit pas être appelé quand un titre est fourni")
        monkeypatch.setattr(httpx, "get", _boom)
        r = client.post("/watches/feeds",
                        json={"url": "http://ex.fr/avec-titre", "category": "tech",
                              "title": "Titre fourni"})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Titre fourni"
        assert appele["n"] == 0
    finally:
        app_.dependency_overrides.clear()
