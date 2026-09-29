"""Correctifs du bilan veille du 29/09 — `docs/superpowers/specs/2026-09-29-bilan-veilles.md`.

Couvre les chemins que le bilan a trouvés nus : la boucle `run_watch`
(qui dépense des crédits, envoie des emails et reprogramme sans aucun test),
la fenêtre des URLs déjà vues, l'amorçage des flux, et la modification d'un
agent.
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
import app.modules.watches.models  # noqa: F401 — enregistre watches / rss_feeds / watch_runs
from app.modules.watches.models import RssFeed, Watch, WatchRun
from app.modules.watches import service


# --- socle -------------------------------------------------------------------

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


def _http(engine, *, user_id=None):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app as _app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user

    uid = user_id or str(uuid.uuid4())
    utilisateur = AuthUser(id=uid, email="u@axial-ia.fr", is_admin=False)

    def _db():
        with Session(engine) as s:
            yield s

    _app.dependency_overrides[get_db] = _db
    _app.dependency_overrides[get_current_user] = lambda: utilisateur
    return _app, TestClient(_app), uid


def _watch(db, user_id, **kw):
    w = Watch(id=uuid.uuid4(), user_id=user_id, name=kw.pop("name", "Veille"),
              query=kw.pop("query", "marché du SIRH"), skill=kw.pop("skill", "concurrentielle"),
              **kw)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def _run(db, watch_id, *, urls, quand):
    db.add(WatchRun(id=uuid.uuid4(), watch_id=watch_id, created_at=quand,
                    new_article_urls=urls, delta_content="x", full_content="x"))
    db.commit()


@pytest.fixture
def veille_bouchonnee(monkeypatch):
    """Neutralise tout ce que `run_watch` appelle à l'extérieur, et rend
    observable ce qu'il a décidé : crédits débités, emails envoyés."""
    journal = {"debits": [], "emails": [], "genere": 0}

    monkeypatch.setattr("app.modules.billing.service.check_credits",
                        lambda db, uid, action: {"affordable": True})
    monkeypatch.setattr("app.modules.billing.service.consume_credits",
                        lambda db, uid, action, is_admin=False: journal["debits"].append(action))
    monkeypatch.setattr("app.modules.memory.service.build_context", lambda db, uid: "")
    monkeypatch.setattr("app.modules.memory.service.get_notification_prefs",
                        lambda db, uid: {"findings": True})
    monkeypatch.setattr("app.shared.search.search_multi",
                        lambda angles, top_k=12, requete_de_rang=None, compteur=None: [])
    monkeypatch.setattr("app.modules.watches.rss.fetch_new_articles",
                        lambda feeds, since=None, seen_urls=None: [])
    monkeypatch.setattr("app.modules.viz.service.preparer_sans_faute", lambda db, corps: [])

    def _faux_email(destinataires, sujet, corps, vizs=None):
        journal["emails"].append({"a": destinataires, "sujet": sujet, "corps": corps})
        return True

    monkeypatch.setattr("app.modules.watches.email.send_email", _faux_email)

    def _fausse_generation(**kw):
        journal["genere"] += 1
        return {"had_changes": True, "delta": "du neuf", "full_report": "le point",
                "rolling_state": "mémoire", "sources": [], "mesure": None}

    monkeypatch.setattr("app.modules.watches.engine.generate_veille", _fausse_generation)
    return journal


# --- fenêtre des URLs déjà vues (bilan #16) ----------------------------------

def test_prior_seen_urls_ne_remonte_que_la_fenetre_recente(monkeypatch):
    """Relire toutes les URLs de tous les runs passés grossit sans borne :
    104 runs × jusqu'à 60 URLs aujourd'hui, à chaque exécution."""
    engine = _engine()
    monkeypatch.setattr(service, "FENETRE_RUNS_URLS_VUES", 2, raising=False)
    with Session(engine) as db:
        w = _watch(db, uuid.uuid4())
        base = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        for i in range(4):
            _run(db, w.id, urls=[f"http://ex.fr/{i}"], quand=base + dt.timedelta(days=i))

        vues = service._prior_seen_urls(db, w.id)

    assert vues == {"http://ex.fr/2", "http://ex.fr/3"}


# --- amorçage des flux (bilan #19) -------------------------------------------

def test_amorcer_flux_complete_une_categorie_deja_entamee(monkeypatch):
    """Un seul flux « tech » suffisait à priver l'utilisateur de tous les
    autres flux tech du catalogue."""
    engine = _engine()
    monkeypatch.setattr("app.modules.watches.catalogue.catalogue", lambda: [
        {"url": "http://cat.fr/tech1", "category": "tech", "title": "T1", "category_label": "Technologie"},
        {"url": "http://cat.fr/tech2", "category": "tech", "title": "T2", "category_label": "Technologie"},
        {"url": "http://cat.fr/produit", "category": "produit", "title": "P", "category_label": "Produit"},
    ])
    uid = uuid.uuid4()
    with Session(engine) as db:
        db.add(RssFeed(id=uuid.uuid4(), user_id=uid, url="http://moi.fr/tech", category="tech"))
        db.commit()

        ajoutes = service.amorcer_flux(db, str(uid), "produit_tech")
        urls = {f.url for f in db.query(RssFeed).all()}

    assert ajoutes == 3
    assert "http://cat.fr/tech1" in urls
    assert "http://cat.fr/tech2" in urls
    assert "http://cat.fr/produit" in urls


# --- un run dit s'il a lu des articles (bilan #10) ---------------------------

def test_la_route_dit_si_un_run_a_lu_des_articles_rss():
    """37 % des runs ne consomment aucun article RSS : c'est la différence
    entre une veille et une recherche web, et rien ne le signalait."""
    engine = _engine()
    app_, client, uid = _http(engine)
    try:
        with Session(engine) as db:
            w = _watch(db, uuid.UUID(uid))
            quand = dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc)
            _run(db, w.id, urls=[], quand=quand)
            _run(db, w.id, urls=["http://ex.fr/a"], quand=quand + dt.timedelta(hours=1))
            watch_id = str(w.id)

        corps = client.get(f"/watches/{watch_id}/runs").json()

        assert [r["rss_utilise"] for r in corps] == [True, False]
    finally:
        app_.dependency_overrides.clear()


# --- extinction faute de crédits (bilan #1) ----------------------------------

def test_un_run_sans_credits_bascule_le_statut_et_previent_une_fois(
        monkeypatch, veille_bouchonnee):
    """Deux agents sur cinq se sont éteints en silence, dont le seul client
    externe. L'agent doit le dire, une fois."""
    monkeypatch.setattr("app.modules.billing.service.check_credits",
                        lambda db, uid, action: {"affordable": False})
    engine = _engine()
    with Session(engine) as db:
        w = _watch(db, uuid.uuid4(), email_recipients=["client@exemple.fr"])

        service.run_watch(db, w)
        db.refresh(w)

        assert w.status == "sans_credits"
        assert len(veille_bouchonnee["emails"]) == 1
        assert "crédit" in veille_bouchonnee["emails"][0]["sujet"].lower()

        service.run_watch(db, w)
        db.refresh(w)

        assert w.status == "sans_credits"
        assert len(veille_bouchonnee["emails"]) == 1, "une seule alerte, pas une par jour"


def test_un_agent_sans_credits_repart_des_que_le_solde_revient(veille_bouchonnee):
    engine = _engine()
    with Session(engine) as db:
        w = _watch(db, uuid.uuid4(), status="sans_credits")

        service.run_watch(db, w)
        db.refresh(w)

    assert w.status == "active"
    assert veille_bouchonnee["debits"] == ["run_agent_veille"]


def test_un_agent_sans_credits_reste_programme(monkeypatch, veille_bouchonnee):
    """Sinon il ne repartirait jamais tout seul : `next_run_at` à NULL sort
    l'agent de la requête du worker."""
    monkeypatch.setattr("app.modules.billing.service.check_credits",
                        lambda db, uid, action: {"affordable": False})
    engine = _engine()
    with Session(engine) as db:
        w = _watch(db, uuid.uuid4())
        service.run_watch(db, w)
        db.refresh(w)

    assert w.next_run_at is not None


# --- modifier un agent (bilan #4) --------------------------------------------

def test_modifier_un_agent_change_son_nom_et_sa_cadence():
    """Trois agents sur cinq portent un nom qui ne correspond pas à leur
    skill, et aucune route ne permettait de les renommer."""
    engine = _engine()
    app_, client, uid = _http(engine)
    try:
        with Session(engine) as db:
            w = _watch(db, uuid.UUID(uid), name="Veille concurrentielle", skill="marche")
            watch_id = str(w.id)

        r = client.patch(f"/watches/{watch_id}",
                         json={"name": "Veille marché — éolien", "cadence": "weekly"})

        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Veille marché — éolien"
        assert r.json()["cadence"] == "weekly"
    finally:
        app_.dependency_overrides.clear()


def test_modifier_la_veille_dun_autre_renvoie_404():
    engine = _engine()
    app_, client, _ = _http(engine)
    try:
        with Session(engine) as db:
            w = _watch(db, uuid.uuid4(), name="Pas la mienne")
            watch_id = str(w.id)

        r = client.patch(f"/watches/{watch_id}", json={"name": "volée"})

        assert r.status_code == 404
    finally:
        app_.dependency_overrides.clear()


def test_changer_la_cadence_reprogramme_le_prochain_passage():
    engine = _engine()
    app_, client, uid = _http(engine)
    try:
        with Session(engine) as db:
            w = _watch(db, uuid.UUID(uid), cadence="daily",
                       next_run_at=dt.datetime(2026, 9, 30, tzinfo=dt.timezone.utc))
            watch_id = str(w.id)

        client.patch(f"/watches/{watch_id}", json={"cadence": "manual"})

        with Session(engine) as db:
            assert db.get(Watch, uuid.UUID(watch_id)).next_run_at is None
    finally:
        app_.dependency_overrides.clear()


# --- mémoire roulante bornée (bilan #15) -------------------------------------

def test_la_memoire_roulante_est_bornee(monkeypatch):
    """La consigne demande « ~400 mots max » ; le modèle rendait jusqu'à
    4 207 caractères en production, et le coût d'entrée a grimpé de 30 % en
    un mois parce que cette mémoire repart dans le prompt du run suivant."""
    from app.modules.watches import engine, skills

    memoire_longue = "état " * 2000
    sortie = ("===HAD_CHANGES===\noui\n===DELTA===\nx\n===FULL_REPORT===\ny\n"
              f"===ROLLING_STATE===\n{memoire_longue}")

    class _Resultat:
        text = sortie
        input_tokens = 10
        output_tokens = 10
        model = "claude-sonnet-5"

    monkeypatch.setattr("app.shared.llm_client.generate", lambda **kw: _Resultat())
    monkeypatch.setattr("app.modules.pii.client.guard_outbound", lambda t: t)
    monkeypatch.setattr("app.shared.search.rerank_indices", lambda q, textes, k: [])

    veille = engine.generate_veille(
        skill=skills.get_skill("concurrentielle"), subject="SIRH",
        rolling_state=None, rss_articles=[], web_results=[], company_context="")

    assert len(veille["rolling_state"]) <= engine.MAX_ROLLING_STATE
