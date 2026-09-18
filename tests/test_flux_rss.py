"""Task 2 — flux RSS visibles et testés (spec ciblage-investisseurs-v2 §3).

Couvre : vérification d'un flux (bouchonnée : ok / 404 / XML invalide /
timeout), transmission du timeout/User-Agent/max_redirects au faux
`httpx.Client` (tout le trafic de `_get_flux` passe par lui — revue tour 2),
parallélisme + borne de `verifier_tous` ET son rendu-la-main réel même si un
flux reste bloqué (revue tour 1 Q1, tour 2), la route admin
`/watches/feeds/verifier` (403 pour un non-admin, `reste`),
`GET /watches/{id}/feeds` (filtre par catégories + actif, fusion du
catalogue, déclenchement best-effort de la vérification d'arrière-plan —
Q3/Q6), et le titre lu à l'ajout d'une URL libre.
"""
from __future__ import annotations

import datetime as dt
import time
import types
import uuid

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
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


def _feed(db, user_id, *, url, category, title=None, verif_at=None, erreur=None, active=True):
    f = RssFeed(id=uuid.uuid4(), user_id=user_id, url=url, category=category,
               title=title, derniere_verification_at=verif_at, derniere_erreur=erreur,
               active=active)
    db.add(f)
    db.commit()
    return f


def _fil_noop(cible, *, user_id):
    """Ne lance jamais la cible. Défaut pour tous les tests de ce fichier —
    sans ça, un test qui ne porte pas sur Q6 déclencherait quand même la
    vérification d'arrière-plan, qui ouvre une VRAIE `SessionLocal` liée à
    la base de prod configurée par `DATABASE_URL`.

    On patch `service._lancer_fil_verification` (l'indirection dédiée), PAS
    `threading.Thread` : ce dernier est aussi ce que `ThreadPoolExecutor`
    utilise en interne pour ses propres threads (`verifier_tous`), et le
    patcher globalement casse le pool."""


@pytest.fixture(autouse=True)
def _fils_demon_neutralises(monkeypatch):
    monkeypatch.setattr(service, "_lancer_fil_verification", _fil_noop)
    yield
    service._verification_en_cours.clear()


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


def _patch_client(monkeypatch, responder):
    """Bouchonne `httpx.Client(...)` — le SEUL transport que `_get_flux`
    utilise (revue tour 2 : `httpx.get` n'est plus appelé nulle part dans
    `service.py`, `_get_flux` route systématiquement par un `Client` pour
    pouvoir borner `max_redirects`). `responder(url, **kw)` doit renvoyer
    une réponse ou lever. Renvoie un dict `{"client": kw, "get": kw}` rempli
    par le dernier appel — suffisant, aucun test n'a besoin d'en inspecter
    plusieurs."""
    captures = {"client": None, "get": None}

    class _Client:
        def __init__(self, **kw):
            captures["client"] = kw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kw):
            captures["get"] = kw
            return responder(url, **kw)

    monkeypatch.setattr(httpx, "Client", _Client)
    return captures


def _patch_client_reponse(monkeypatch, reponse):
    return _patch_client(monkeypatch, lambda url, **kw: reponse)


def _patch_client_boom(monkeypatch, exc):
    def _lever(url, **kw):
        raise exc
    return _patch_client(monkeypatch, _lever)


class _ClientBoomConstruction:
    def __init__(self, **kw):
        raise AssertionError("httpx.Client ne doit pas être construit ici")


# --- verifier_flux : bouchonnée ok / 404 / XML invalide / timeout -----------

def test_verifier_flux_ok(monkeypatch):
    _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
    r = service.verifier_flux("http://ex.fr/feed")
    assert r["ok"] is True
    assert r["statut_http"] == 200
    assert r["entrees"] == 1
    assert r["dernier"] is not None
    assert r["erreur"] is None
    assert r["titre"] == "Flux Test"


def test_verifier_flux_404(monkeypatch):
    def _get(url, **kw):
        return _FauxReponse(404, b"", raise_status=httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", url), response=httpx.Response(404)))
    _patch_client(monkeypatch, _get)
    r = service.verifier_flux("http://ex.fr/mort")
    assert r["ok"] is False
    assert r["statut_http"] == 404
    assert r["erreur"]


def test_verifier_flux_xml_invalide(monkeypatch):
    _patch_client_reponse(monkeypatch, _FauxReponse(200, b"<not><valid"))
    r = service.verifier_flux("http://ex.fr/invalide")
    assert r["ok"] is False
    assert r["entrees"] == 0
    assert r["erreur"]


def test_verifier_flux_timeout(monkeypatch):
    _patch_client_boom(monkeypatch, httpx.TimeoutException("timeout"))
    r = service.verifier_flux("http://ex.fr/lent")
    assert r["ok"] is False
    assert "timeout" in r["erreur"].lower()


# --- Q2 : timeout, User-Agent et max_redirects réellement transmis ----------

def test_verifier_flux_transmet_timeout_user_agent_et_max_redirects(monkeypatch):
    captures = _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
    service.verifier_flux("http://ex.fr/feed")
    assert captures["client"]["timeout"] == service.HTTP_TIMEOUT_VERIFICATION
    assert captures["client"]["max_redirects"] == service.MAX_REDIRECTS_VERIFICATION
    assert captures["client"]["follow_redirects"] is True
    assert captures["get"]["headers"]["User-Agent"] == service.USER_AGENT


def test_http_timeout_titre_borne_la_connexion_a_2s():
    # Q2 : `timeout=5.0` seul donnait 5 s à CHAQUE phase (connect compris) ;
    # `httpx.Timeout(5.0, connect=2.0)` borne spécifiquement la connexion.
    assert isinstance(service.HTTP_TIMEOUT_TITRE, httpx.Timeout)
    assert service.HTTP_TIMEOUT_TITRE.connect == 2.0
    assert service.HTTP_TIMEOUT_TITRE.read == 5.0
    assert service.MAX_REDIRECTS_TITRE == 3


def test_max_redirects_verification_est_borne_a_5():
    # Tour 2 : le chemin de vérification standard (pas seulement la lecture
    # de titre) borne aussi ses redirections — un flux qui boucle ne tourne
    # plus indéfiniment (limite par défaut d'httpx : 20).
    assert service.MAX_REDIRECTS_VERIFICATION == 5


def test_lire_titre_flux_transmet_timeout_borne_redirections_et_user_agent(monkeypatch):
    captures = _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
    assert service.lire_titre_flux("http://ex.fr/feed") == "Flux Test"
    assert captures["client"]["timeout"] == service.HTTP_TIMEOUT_TITRE
    assert captures["client"]["max_redirects"] == service.MAX_REDIRECTS_TITRE
    assert captures["client"]["follow_redirects"] is True
    assert captures["get"]["headers"]["User-Agent"] == service.USER_AGENT


def test_lire_titre_flux_best_effort(monkeypatch):
    _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
    assert service.lire_titre_flux("http://ex.fr/feed") == "Flux Test"

    _patch_client_boom(monkeypatch, RuntimeError("réseau down"))
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
        _patch_client(monkeypatch, _get)
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])

        sortie = service.verifier_tous(db)
        resultats = sortie["resultats"]
        assert sortie["reste"] == 0
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
        _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue",
                            lambda: [{"url": "http://cat.fr/feed", "category": "tech",
                                     "title": "Cat", "category_label": "Technologie"}])
        sortie = service.verifier_tous(db)
        assert any(r["url"] == "http://cat.fr/feed" for r in sortie["resultats"])
        # aucun RssFeed n'a été créé pour l'entrée catalogue
        assert db.scalars(select(RssFeed)).first() is None


# --- Q1 : parallélisme borné -------------------------------------------------

def test_verifier_tous_est_parallele_et_reste_rapide(monkeypatch):
    """20 flux qui dorment chacun 0,3 s : en séquentiel ça ferait 6 s. Avec
    8 threads en vol (`VERIF_MAX_WORKERS`), 3 vagues suffisent (~0,9 s)."""
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        for i in range(20):
            _feed(db, uid, url=f"http://ex.fr/{i}", category="tech")

        def _get(url, **kw):
            time.sleep(0.3)
            return _FauxReponse(200, _FLUX_VALIDE.encode("utf-8"))
        _patch_client(monkeypatch, _get)
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])

        debut = time.monotonic()
        sortie = service.verifier_tous(db)
        duree = time.monotonic() - debut

        assert len(sortie["resultats"]) == 20
        assert duree < 2.0, f"20 flux à 0,3 s en 8 threads a pris {duree:.2f}s (attendu < 2 s)"


def test_verifier_tous_respecte_limit_et_rapporte_reste(monkeypatch):
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        for i in range(5):
            _feed(db, uid, url=f"http://ex.fr/{i}", category="tech")
        _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])

        sortie = service.verifier_tous(db, limit=3)
        assert len(sortie["resultats"]) == 3
        assert sortie["reste"] == 2
        # les flux traités ont bien été écrits, ceux hors du lot pas encore
        traites = {f.url for f in db.scalars(select(RssFeed))
                  if f.derniere_verification_at is not None}
        assert len(traites) == 3


# --- Tour 2 : rendre la main sans attendre un flux bloqué -------------------

def test_verifier_tous_rend_la_main_sans_attendre_un_flux_bloque(monkeypatch):
    """Avant correction, `with ThreadPoolExecutor(...)` attendait la fin de
    TOUS les threads à la sortie du bloc (`shutdown(wait=True)` implicite),
    annulant le bornage de `future.result(timeout=...)` : un flux qui ne
    répond jamais bloquait quand même la fonction ~3 s. Avec
    `executor.shutdown(wait=False)`, `verifier_tous` rend la main dès que le
    `.result(timeout=0.2)` a tranché, sans attendre le thread abandonné."""
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        _feed(db, uid, url="http://ex.fr/bloque", category="tech")

        def _get(url, **kw):
            time.sleep(3)
            return _FauxReponse(200, _FLUX_VALIDE.encode("utf-8"))
        _patch_client(monkeypatch, _get)
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])

        debut = time.monotonic()
        sortie = service.verifier_tous(db, timeout_future=0.2)
        duree = time.monotonic() - debut

        assert duree < 1.0, f"verifier_tous a mis {duree:.2f}s à rendre la main (attendu < 1 s)"
        assert sortie["resultats"][0]["ok"] is False
        assert "délai" in sortie["resultats"][0]["erreur"].lower()


def test_verifier_tous_pour_rend_aussi_la_main_sans_attendre(monkeypatch):
    """Même correction sur `verifier_tous_pour` (Q6, utilisée par la
    vérification d'arrière-plan) — même bouchon, même borne basse."""
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        flux = _feed(db, uid, url="http://ex.fr/bloque", category="tech")

        def _get(url, **kw):
            time.sleep(3)
            return _FauxReponse(200, _FLUX_VALIDE.encode("utf-8"))
        _patch_client(monkeypatch, _get)

        debut = time.monotonic()
        resultats = service.verifier_tous_pour(db, [flux], timeout_future=0.2)
        duree = time.monotonic() - debut

        assert duree < 1.0, f"verifier_tous_pour a mis {duree:.2f}s à rendre la main (attendu < 1 s)"
        assert resultats[0]["ok"] is False


# --- feeds_pour_watch : filtre par catégories, actif, fusion catalogue ------

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
        # URL présente dans le catalogue → étiquette « catalogue » même si la
        # ligne appartient à l'utilisateur (attachée à la création de l'agent).
        assert item["origine"] == "catalogue"
        assert item["etat"] == "erreur"


def test_feeds_pour_watch_etat_catalogue_ignore_un_flux_utilisateur_hors_categorie(monkeypatch):
    """Q4 (corollaire du filtre Q3) : un flux personnel classé HORS des
    catégories du skill ne doit pas prêter son état à l'entrée catalogue de
    même URL — sinon un flux rangé par erreur dans la mauvaise catégorie
    « ressusciterait » une entrée catalogue qu'il ne représente pas vraiment
    pour cet agent."""
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        now = dt.datetime.now(dt.timezone.utc)
        # rangé en 'juridique' (hors skill produit_tech), mais en erreur
        _feed(db, uid, url="http://cat.fr/tech", category="juridique",
             verif_at=now, erreur="mort")

        monkeypatch.setattr(
            "app.modules.watches.catalogue.catalogue",
            lambda: [{"url": "http://cat.fr/tech", "category": "tech", "title": "Cat Tech",
                     "category_label": "Technologie"}],
        )
        watch = types.SimpleNamespace(skill="produit_tech")
        items = service.feeds_pour_watch(db, str(uid), watch)
        assert len(items) == 1
        assert items[0]["origine"] == "catalogue"
        assert items[0]["etat"] == "inconnu"  # pas "erreur" emprunté au flux hors catégorie


def test_feeds_pour_watch_ignore_les_flux_inactifs(monkeypatch):
    """Q3 : même filtre `active` que `service._feeds_for` (ce que `run_watch`
    lit réellement) — sinon la carte affiche comme lue une source que
    l'agent ignore."""
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        _feed(db, uid, url="http://moi.fr/actif", category="tech")
        _feed(db, uid, url="http://moi.fr/inactif", category="tech", active=False)
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        watch = types.SimpleNamespace(skill="produit_tech")
        items = service.feeds_pour_watch(db, str(uid), watch)
        urls = {i["url"] for i in items}
        assert "http://moi.fr/actif" in urls
        assert "http://moi.fr/inactif" not in urls


# --- Q6 : vérification d'arrière-plan au premier chargement -----------------

def _fil_espion(compteur):
    """Compte les déclenchements sans jamais exécuter la cible — pour
    vérifier QUAND la vérification d'arrière-plan part, pas encore ce
    qu'elle fait (couvert par le test synchrone ci-dessous)."""
    def _fil(cible, *, user_id):
        compteur["n"] += 1
    return _fil


def _fil_synchrone(cible, *, user_id):
    """Exécute la cible immédiatement, dans le fil courant — pour observer
    l'effet (écriture en base) sans dépendre d'un vrai thread."""
    cible()


def test_pas_de_verification_arriere_plan_si_tout_est_recent(monkeypatch):
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        _feed(db, uid, url="http://moi.fr/frais", category="tech",
             verif_at=dt.datetime.now(dt.timezone.utc))
        compteur = {"n": 0}
        monkeypatch.setattr(service, "_lancer_fil_verification", _fil_espion(compteur))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        watch = types.SimpleNamespace(skill="produit_tech")
        service.feeds_pour_watch(db, str(uid), watch)
        assert compteur["n"] == 0


def test_verification_arriere_plan_declenchee_si_jamais_verifie(monkeypatch):
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        _feed(db, uid, url="http://moi.fr/jamais-verifie", category="tech")  # verif_at=None
        compteur = {"n": 0}
        monkeypatch.setattr(service, "_lancer_fil_verification", _fil_espion(compteur))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        watch = types.SimpleNamespace(skill="produit_tech")
        service.feeds_pour_watch(db, str(uid), watch)
        assert compteur["n"] == 1


def test_verification_arriere_plan_declenchee_si_perimee_plus_de_7_jours(monkeypatch):
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        perime = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)
        _feed(db, uid, url="http://moi.fr/perime", category="tech", verif_at=perime)
        compteur = {"n": 0}
        monkeypatch.setattr(service, "_lancer_fil_verification", _fil_espion(compteur))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        watch = types.SimpleNamespace(skill="produit_tech")
        service.feeds_pour_watch(db, str(uid), watch)
        assert compteur["n"] == 1


def test_verification_arriere_plan_ne_relance_pas_si_deja_en_cours(monkeypatch):
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        _feed(db, uid, url="http://moi.fr/jamais-verifie", category="tech")
        compteur = {"n": 0}
        monkeypatch.setattr(service, "_lancer_fil_verification", _fil_espion(compteur))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        service._verification_en_cours.add(str(uid))
        watch = types.SimpleNamespace(skill="produit_tech")
        service.feeds_pour_watch(db, str(uid), watch)
        assert compteur["n"] == 0


def test_verification_arriere_plan_ecrit_bien_l_etat_du_flux(monkeypatch):
    """Bout en bout (fil synchrone + `SessionLocal` redirigée vers le
    moteur de test) : le point gris doit devenir vert/rouge après le passage."""
    engine = _engine()
    uid = uuid.uuid4()
    with Session(engine) as db:
        _feed(db, uid, url="http://moi.fr/jamais-verifie", category="tech")
        monkeypatch.setattr(service, "_lancer_fil_verification", _fil_synchrone)
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        fausse_session_locale = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                                             future=True)
        monkeypatch.setattr("app.db.SessionLocal", fausse_session_locale)

        watch = types.SimpleNamespace(skill="produit_tech")
        service.feeds_pour_watch(db, str(uid), watch)

    with Session(engine) as verif:
        flux = verif.scalars(select(RssFeed).where(RssFeed.user_id == uid)).one()
        assert flux.derniere_verification_at is not None
        assert flux.derniere_erreur is None


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
        _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        r = client.post("/watches/feeds/verifier")
        assert r.status_code == 200, r.text
        corps = r.json()
        assert corps["reste"] == 0
        assert any(item["url"] == "http://ex.fr/a" and item["ok"] for item in corps["resultats"])
    finally:
        app_.dependency_overrides.clear()


def test_route_verifier_feeds_borne_le_lot_et_rapporte_reste(monkeypatch):
    """Q1 : la route ne traite jamais plus de `VERIF_LIMITE_PAR_APPEL` flux
    dans un même appel — vérifié ici avec une limite abaissée pour ne pas
    créer 61 flux dans le test."""
    engine = _engine()
    app_, client, uid = _http(engine, is_admin=True)
    try:
        with Session(engine) as db:
            for i in range(5):
                _feed(db, uuid.UUID(uid), url=f"http://ex.fr/{i}", category="tech")
        monkeypatch.setattr(service, "VERIF_LIMITE_PAR_APPEL", 3)
        _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [])
        r = client.post("/watches/feeds/verifier")
        assert r.status_code == 200, r.text
        corps = r.json()
        assert len(corps["resultats"]) == 3
        assert corps["reste"] == 2
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
        _patch_client_reponse(monkeypatch, _FauxReponse(200, _FLUX_VALIDE.encode("utf-8")))
        r = client.post("/watches/feeds", json={"url": "http://ex.fr/libre", "category": "tech"})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Flux Test"
    finally:
        app_.dependency_overrides.clear()


def test_ajout_flux_url_libre_avec_titre_fourni_ne_verifie_pas(monkeypatch):
    engine = _engine()
    app_, client, uid = _http(engine, is_admin=False)
    try:
        monkeypatch.setattr(httpx, "Client", _ClientBoomConstruction)
        r = client.post("/watches/feeds",
                        json={"url": "http://ex.fr/avec-titre", "category": "tech",
                              "title": "Titre fourni"})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Titre fourni"
    finally:
        app_.dependency_overrides.clear()
