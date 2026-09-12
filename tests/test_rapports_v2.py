"""Rapports v2 — socle backend (Task 1).

Trois garanties qu'aucune relecture ne remplace :

* le premier rapport offert ne peut pas être servi deux fois, **même sous
  concurrence** — la vérification applicative laissait passer deux appels
  simultanés, et le test les rejoue tels quels (deux sessions, deux lectures
  avant écriture) ;
* l'import des rapports hérités ne tourne qu'une fois par compte ;
* les deux tables d'alias n'en font plus qu'une.

Les tests de base tournent sur SQLite en mémoire, avec `StaticPool` pour que
deux sessions voient la même base (la concurrence simulée en dépend). SQLite
connaît les index partiels : la contrainte testée ici est bien celle que
PostgreSQL appliquera.
"""
from __future__ import annotations

import datetime as dt
import uuid as uuidlib

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.modules.intelligence.models  # noqa: F401 — enregistre `projects`
import app.modules.reports.feedback  # noqa: F401 — enregistre `report_feedback`
import app.modules.reports.models  # noqa: F401 — enregistre `reports`
from app.db import Base
from app.modules.billing.models import (
    ACTION_PREMIER_RAPPORT_OFFERT, CreditBalance, CreditEvent)
from app.modules.reports import service as reports_service
from app.modules.reports.feedback import ReportFeedback
from app.modules.reports.models import Report


# --- socle de test ---------------------------------------------------------

def _base():
    """Une base SQLite en mémoire PARTAGÉE entre sessions.

    `StaticPool` + une seule connexion : sans cela, deux `Session` ouvrent deux
    bases distinctes et le test de concurrence passerait pour de mauvaises
    raisons (deux insertions dans deux bases ne se collisionnent jamais).
    """
    engine = create_engine("sqlite://", future=True,
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["projects"],
        Base.metadata.tables["reports"],
        Base.metadata.tables["report_feedback"],
        Base.metadata.tables["credit_balances"],
        Base.metadata.tables["credit_events"],
    ])
    return engine


def _rapport(db: Session, user_id: uuidlib.UUID, **kw) -> Report:
    r = Report(id=uuidlib.uuid4(), user_id=user_id,
               title=kw.pop("title", "Rapport de test"), **kw)
    db.add(r)
    db.commit()
    return r


# --- Step 1 : colonnes et table -------------------------------------------

def test_colonnes_rapports_v2_presentes():
    cols = Base.metadata.tables["reports"].c
    for nom in ("statut", "etape", "progression", "detail", "question",
                "termine_at", "annulation_demandee", "archived_at", "pinned_at",
                "project_id", "jeton_partage", "partage_at"):
        assert nom in cols, f"reports.{nom} manquant"
    assert not cols["statut"].nullable
    assert not cols["progression"].nullable
    assert not cols["annulation_demandee"].nullable
    # Les colonnes de suivi doivent porter un server_default : sans lui,
    # l'ALTER TABLE laisserait les rapports existants à NULL sur une colonne
    # NOT NULL et la migration échouerait sur la base de production.
    assert cols["statut"].server_default is not None
    assert cols["progression"].server_default is not None
    assert cols["annulation_demandee"].server_default is not None


def test_project_id_est_set_null_et_non_cascade():
    """Supprimer un dossier ne doit pas détruire des rapports payés."""
    fk = next(iter(Base.metadata.tables["reports"].c["project_id"].foreign_keys))
    assert fk.column.table.name == "projects"
    assert fk.ondelete == "SET NULL"
    # Le contraste avec les conversations est volontaire : une conversation
    # sans dossier n'a pas de sens, un rapport si.
    fk_conv = next(iter(
        Base.metadata.tables["conversations"].c["project_id"].foreign_keys))
    assert fk_conv.ondelete == "CASCADE"


def test_defauts_des_rapports_existants():
    """Tout rapport écrit sans suivi se lit `termine` / 100 %."""
    engine = _base()
    with Session(engine) as db:
        r = _rapport(db, uuidlib.uuid4(), content="ok")
        db.refresh(r)
        assert r.statut == "termine"
        assert r.progression == 100
        assert r.annulation_demandee is False
        assert r.termine_at is None


def test_jeton_partage_unique_mais_plusieurs_rapports_non_partages():
    engine = _base()
    uid = uuidlib.uuid4()
    with Session(engine) as db:
        # Les NULL n'entrent pas en collision : deux rapports non partagés
        # coexistent, c'est le cas de l'immense majorité.
        _rapport(db, uid, title="A")
        _rapport(db, uid, title="B")
        _rapport(db, uid, title="C", jeton_partage="j" * 22)
        with pytest.raises(IntegrityError):
            _rapport(db, uid, title="D", jeton_partage="j" * 22)
        db.rollback()


def test_feedback_lie_au_rapport_et_supprime_avec_lui():
    engine = _base()
    uid = uuidlib.uuid4()
    with Session(engine) as db:
        db.execute(text("PRAGMA foreign_keys=ON"))  # SQLite : désactivé par défaut
        r = _rapport(db, uid)
        db.add(ReportFeedback(id=uuidlib.uuid4(), report_id=r.id, user_id=uid,
                              note=2, motif="contenu_faux",
                              commentaire="Le chiffre de marché est faux."))
        db.commit()
        assert db.scalar(select(ReportFeedback).where(
            ReportFeedback.report_id == r.id)) is not None

        db.delete(r)
        db.commit()
        assert db.scalars(select(ReportFeedback)).all() == []


def test_migration_0023_chainee_et_reversible():
    """La migration existe, s'enchaîne à 0022 et sait redescendre."""
    import importlib.util
    import pathlib

    chemin = pathlib.Path(__file__).resolve().parents[1] / (
        "alembic/versions/0023_rapports_v2.py")
    spec = importlib.util.spec_from_file_location("m0023", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "0023_rapports_v2"
    assert mod.down_revision == "0022_conversations_v2"
    source = chemin.read_text(encoding="utf-8")
    corps_downgrade = source.split("def downgrade()")[1]
    # Chaque colonne ajoutée doit être retirée : un downgrade partiel est pire
    # qu'absent — il laisse la base dans un état qu'aucune révision ne décrit.
    for nom in ("statut", "etape", "progression", "detail", "question",
                "termine_at", "annulation_demandee", "archived_at", "pinned_at",
                "project_id", "jeton_partage", "partage_at",
                "legacy_verifie_at"):
        assert f'"{nom}"' in corps_downgrade, f"downgrade : {nom} non retiré"
    assert "report_feedback" in corps_downgrade
    # Concurrent UNIQUEMENT sous PostgreSQL et dans un autocommit_block.
    assert 'op.get_bind().dialect.name == "postgresql"' in source
    assert "autocommit_block" in source


# --- Step 2 : rapport offert, une seule fois -------------------------------

def test_action_offerte_identique_partout():
    """Le nom de l'action est dupliqué en trois endroits : ils doivent coller."""
    from app.modules.analysis import onboarding

    assert onboarding.ACTION == ACTION_PREMIER_RAPPORT_OFFERT == "premier_rapport_offert"


def test_index_partiel_bloque_un_second_rapport_offert():
    engine = _base()
    uid = uuidlib.uuid4()
    with Session(engine) as db:
        db.add(CreditEvent(user_id=uid, delta=0,
                           action=ACTION_PREMIER_RAPPORT_OFFERT))
        db.commit()
        with pytest.raises(IntegrityError):
            db.add(CreditEvent(user_id=uid, delta=0,
                               action=ACTION_PREMIER_RAPPORT_OFFERT))
            db.commit()
        db.rollback()


def test_index_partiel_laisse_le_registre_append_only():
    """Les autres actions restent multiples : c'est un registre, pas un état."""
    engine = _base()
    uid = uuidlib.uuid4()
    with Session(engine) as db:
        for _ in range(3):
            db.add(CreditEvent(user_id=uid, delta=-2, action="agent_message"))
        db.add(CreditEvent(user_id=uid, delta=40, action="essai_bienvenue"))
        db.commit()
        assert len(db.scalars(select(CreditEvent)).all()) == 4
    # Et deux comptes différents ont chacun droit à leur rapport offert.
    with Session(engine) as db:
        for _ in range(2):
            db.add(CreditEvent(user_id=uuidlib.uuid4(), delta=0,
                               action=ACTION_PREMIER_RAPPORT_OFFERT))
        db.commit()


def test_offrir_perd_la_course_sans_generer_de_second_rapport(monkeypatch):
    """Concurrence simulée : deux appels passent `deja_offert` avant l'écriture.

    C'est exactement le scénario que la vérification applicative laissait
    passer. On force `deja_offert` à répondre False pour les deux appels — ce
    que deux processus simultanés observent réellement — et on vérifie que le
    second ne produit RIEN : pas de rapport, pas de second événement.
    """
    from app.modules.analysis import onboarding

    engine = _base()
    uid = str(uuidlib.uuid4())
    generations: list[str] = []

    monkeypatch.setattr(onboarding, "deja_offert", lambda db, u: False)
    monkeypatch.setattr(onboarding, "profil_utilisable",
                        lambda db, u: {"company_name": "Axial", "sector": "SaaS"})

    def _jamais_appele(db, user_id, **kw):
        generations.append(kw.get("query", ""))
        raise AssertionError("La génération ne doit pas être lancée deux fois")

    with Session(engine) as db1, Session(engine) as db2:
        # Premier appel : marque l'offre, puis on coupe avant la génération.
        # `offrir` passe désormais par le moteur suivi (`lancer_rapport`), pas
        # par `run_analysis` : c'est le même pipeline pour tout le monde.
        import app.modules.analysis.service as service
        from app.modules.memory import service as memory
        monkeypatch.setattr(service, "lancer_rapport", _jamais_appele)
        monkeypatch.setattr(memory, "build_context", lambda db, u: "")
        monkeypatch.setattr(service, "_profile_dict", lambda db, u: {})
        with pytest.raises(AssertionError):
            onboarding.offrir(db1, uid)
        assert len(generations) == 1  # le premier a bien atteint la génération

        # Second appel concurrent : l'index tranche, retour None sans génération.
        assert onboarding.offrir(db2, uid) is None
        assert len(generations) == 1  # aucune seconde génération

    with Session(engine) as db:
        evenements = db.scalars(select(CreditEvent).where(
            CreditEvent.action == ACTION_PREMIER_RAPPORT_OFFERT)).all()
        assert len(evenements) == 1, "un seul rapport offert par compte"


# --- Step 3 : import hérité, une seule fois --------------------------------

def test_import_herite_ne_tourne_quune_fois(monkeypatch):
    from app.modules.billing import service as billing
    from app.modules.reports import legacy

    engine = _base()
    uid = str(uuidlib.uuid4())
    appels: list[str] = []

    monkeypatch.setattr(legacy, "restore_for",
                        lambda db, u, e: appels.append("restore") or 0)
    monkeypatch.setattr(legacy, "grant_return_bonus",
                        lambda db, u, e: appels.append("bonus") or 0)
    monkeypatch.setattr(billing, "FREE_BETA_CREDITS", 40, raising=False)

    with Session(engine) as db:
        premier = legacy.verifier_une_fois(db, uid, "jean@exemple.fr")
        assert premier["deja_verifie"] is False
        assert appels == ["restore", "bonus"]

        balance = db.get(CreditBalance, uuidlib.UUID(uid))
        assert balance.legacy_verifie_at is not None

        # Connexions suivantes : plus aucune requête sur `legacy_reports`.
        for _ in range(3):
            suivant = legacy.verifier_une_fois(db, uid, "jean@exemple.fr")
            assert suivant["deja_verifie"] is True
        assert appels == ["restore", "bonus"], "l'import a été rejoué"


def test_marqueur_pose_meme_sans_rapport_a_restaurer(monkeypatch):
    """« Rien à restaurer » est un résultat définitif, pas un échec à retenter."""
    from app.modules.reports import legacy

    engine = _base()
    uid = str(uuidlib.uuid4())
    monkeypatch.setattr(legacy, "restore_for", lambda db, u, e: 0)
    monkeypatch.setattr(legacy, "grant_return_bonus", lambda db, u, e: 0)

    with Session(engine) as db:
        legacy.verifier_une_fois(db, uid, "inconnue@exemple.fr")
        balance = db.get(CreditBalance, uuidlib.UUID(uid))
        assert balance.legacy_verifie_at is not None
        assert isinstance(balance.legacy_verifie_at, dt.datetime)


def test_reset_password_ne_relance_plus_limport_herite():
    """La route de réinitialisation n'appelle plus `_restore_legacy`."""
    import inspect

    from app.modules.auth import router as auth_router

    assert "_restore_legacy(" not in inspect.getsource(auth_router.reset_password)
    # Inscription et connexion le gardent.
    assert "_restore_legacy(" in inspect.getsource(auth_router.register)
    assert "_restore_legacy(" in inspect.getsource(auth_router.login)


# --- Step 4 : dette --------------------------------------------------------

def test_une_seule_table_dalias():
    from app.modules.analysis import prompts
    from app.modules.billing import catalog

    assert catalog._ALIASES is prompts._ALIASES, "le catalog tient encore sa copie"
    # Et un alias reste facturé au prix de son type canonique.
    assert catalog.cost_for("market_study") == catalog.cost_for("etude_marche")


def test_analysis_prompts_supprime():
    from app.modules.analysis import prompts

    assert not hasattr(prompts, "ANALYSIS_PROMPTS")
    assert prompts.get_prompt_template("market_study") == \
        prompts.get_prompt_template("etude_marche")


def test_tarifs_de_recherche_en_configuration():
    from app.config import get_settings
    from app.modules.billing import couts

    s = get_settings()
    # Valeurs actuelles conservées comme défauts (à confirmer, cf. config).
    assert s.tarif_recherche_exa_micro_eur == 4_600
    assert s.tarif_recherche_tavily_micro_eur == 7_400
    assert s.tarif_recherche_linkup_micro_eur == 4_600
    assert s.tarif_recherche_serper_micro_eur == 920

    assert couts.cout_recherche_micro_eur({"exa": 2, "serper": 1}) == 2 * 4_600 + 920
    assert couts.cout_recherche_micro_eur(None) == 0
    # Fournisseur inconnu : repli, jamais zéro — sous-estimer un coût le fait
    # disparaître des marges.
    assert couts.cout_recherche_micro_eur({"inconnu": 1}) == \
        s.tarif_recherche_defaut_micro_eur


def test_cache_investisseurs_borne_et_purgeable(monkeypatch):
    """Une seule entrée, un TTL, un verrou — et une purge qui fait repartir."""
    from app.modules.investors import client

    chargements: list[int] = []

    def _faux_fetch(table, select_):
        chargements.append(1)
        return [{"id": 1}]

    monkeypatch.setattr(client, "configured", lambda: True)
    monkeypatch.setattr(client, "_fetch_all", _faux_fetch)
    monkeypatch.setattr(client, "_TABLES", {"investisseur": "id",
                                            "societe_gestion": "id"})
    client.vider()
    try:
        client.dataset()
        premier = len(chargements)
        assert premier == 2  # une requête par table, pas plus

        # Le cache tient : deuxième appel sans réseau.
        client.dataset()
        assert len(chargements) == premier

        # Borné : le cache ne contient QUE les tables déclarées, jamais une
        # entrée par requête utilisateur — il ne peut pas croître avec le trafic.
        assert set(client._cache) == {"investisseur", "societe_gestion"}

        # Purge (ou expiration du TTL) : la requête suivante recharge.
        client.vider()
        assert client._cache is None
        client.dataset()
        assert len(chargements) == premier * 2
    finally:
        client.vider()


def test_cache_investisseurs_expire_avec_le_ttl(monkeypatch):
    from app.modules.investors import client

    chargements: list[int] = []
    monkeypatch.setattr(client, "configured", lambda: True)
    monkeypatch.setattr(client, "_fetch_all",
                        lambda t, s: chargements.append(1) or [{"id": 1}])
    monkeypatch.setattr(client, "_TABLES", {"investisseur": "id",
                                            "societe_gestion": "id"})
    client.vider()
    try:
        client.dataset()
        # On vieillit le cache au-delà du TTL plutôt que d'attendre une heure.
        client._cache_at -= client.CACHE_TTL_SECONDS + 1
        client.dataset()
        assert len(chargements) == 4, "le TTL n'a pas provoqué de rechargement"
    finally:
        client.vider()


# ===========================================================================
# Task 2 — moteur de génération suivi par identifiant (spec §1, §2, §3, §5.1)
# ===========================================================================
#
# Ces tests tournent sur une base SQLite **de fichier** et non en mémoire : le
# moteur ouvre sa propre session (c'est toute sa raison d'être) et l'annulation
# est relue depuis une troisième. Avec `StaticPool` en mémoire, ces sessions
# partageraient une seule connexion — donc une seule transaction — et le test
# vérifierait une propriété que la production n'a pas.

import json  # noqa: E402
import time  # noqa: E402

from app.modules.reports import models as rm  # noqa: E402


def _base_fichier(tmp_path):
    """Base SQLite de fichier + `app.db.SessionLocal` pointé dessus."""
    import app.db as app_db
    import app.modules.viz.models  # noqa: F401 — enregistre `viz_rendus`
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path}/rapports.db", future=True,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["projects"],
        Base.metadata.tables["reports"],
        Base.metadata.tables["report_feedback"],
        Base.metadata.tables["credit_balances"],
        Base.metadata.tables["credit_events"],
        Base.metadata.tables["viz_rendus"],
    ])
    fabrique = sessionmaker(bind=engine, future=True)
    app_db.SessionLocal = fabrique  # restauré par la fixture ci-dessous
    return engine


@pytest.fixture
def base(tmp_path, monkeypatch):
    import app.db as app_db

    ancienne = app_db.SessionLocal
    engine = _base_fichier(tmp_path)
    yield engine
    app_db.SessionLocal = ancienne


class _Source:
    """Le minimum qu'`assemble` rend : une citation de rapport."""

    def __init__(self, i):
        self.i = i


def _citations(n: int) -> list[dict]:
    return [{"title": f"Source {i}", "url": f"https://exemple.fr/{i}",
             "domain": "exemple.fr", "source": "web",
             "excerpt": f"Extrait {i}"} for i in range(1, n + 1)]


def _brancher_moteur(monkeypatch, *, citations=None, couverture="oui",
                     chunks=None, stop_reason="end_turn", avant_chunk=None):
    """Neutralise tout ce qui sort du process : recherche, RAG, modèle.

    Ce qui reste sous test est exactement le moteur : les étapes, la détection
    de section, l'annulation et la transaction de clôture.
    """
    from app.modules.analysis import service
    from app.modules.memory import service as memory
    from app.modules.reports import notification
    from app.shared import grounding, llm_client
    from app.shared import search as web_search

    cits = _citations(8) if citations is None else citations
    monkeypatch.setattr(memory, "build_context", lambda db, u: "")
    monkeypatch.setattr(service, "_profile_dict", lambda db, u: {})
    monkeypatch.setattr(llm_client, "generation_available", lambda: True)
    monkeypatch.setattr(web_search, "search_multi",
                        lambda angles, **kw: [_Source(i) for i in range(len(cits))])
    monkeypatch.setattr(service, "_retrieve_context", lambda *a, **k: ("", []))
    monkeypatch.setattr(grounding, "assemble",
                        lambda *a, **k: ("contexte numéroté", list(cits)))
    monkeypatch.setattr(service, "_evaluer_couverture", lambda q, c: couverture)
    monkeypatch.setattr(notification, "prevenir", lambda *a, **k: True)

    morceaux = chunks if chunks is not None else ["# Titre\n", "## 1. A\n", "texte "]

    def _flux(*, system, prompt, tier="chat", max_tokens=4000, history=None,
              mesure=None, **kw):
        if mesure is not None:
            mesure.update({"model": "modele-test", "provider": "test",
                           "input_tokens": 100, "output_tokens": 200})
        for m in morceaux:
            if avant_chunk is not None:
                avant_chunk(m)
            yield m
        return stop_reason

    monkeypatch.setattr(llm_client, "stream_text", _flux)
    return cits


def _lancer(base, uid, monkeypatch, *, analysis_type="analyse_risques",
            credits=200, **kw):
    """Solde crédité puis rapport lancé en ATTENTE (moteur synchrone)."""
    from app.modules.analysis import service
    from app.modules.billing import service as billing

    with Session(base) as db:
        billing.get_or_create_balance(db, str(uid))
        billing.grant_purchased(db, str(uid), credits)
    with Session(base) as db:
        return service.lancer_rapport(db, str(uid), query="ma question",
                                      analysis_type=analysis_type,
                                      attendre=True, **kw)


def _relire(base, rapport_id):
    with Session(base) as db:
        return db.get(Report, rapport_id)


def _solde(base, uid):
    from app.modules.billing import service as billing

    with Session(base) as db:
        return billing.available_credits(billing.get_or_create_balance(db, str(uid)))


# --- Step 1 : statuts et transaction unique --------------------------------

def test_statuts_declares_une_seule_fois():
    """Task 1 n'a posé aucun CHECK : la constante EST le contrat."""
    assert rm.STATUTS == ("en_cours", "termine", "echec", "degrade", "annule",
                          "sources_insuffisantes")
    assert rm.EN_COURS not in rm.STATUTS_TERMINAUX
    assert set(rm.STATUTS_TERMINAUX) | {rm.EN_COURS} == set(rm.STATUTS)


def test_la_ligne_est_creee_en_cours_avant_toute_generation(base, monkeypatch):
    """Le rapport existe dès le lancement, question comprise (spec §1)."""
    from app.modules.analysis import service
    from app.modules.billing import service as billing
    from app.modules.memory import service as memory

    uid = uuidlib.uuid4()
    monkeypatch.setattr(memory, "build_context", lambda db, u: "")
    monkeypatch.setattr(service, "_profile_dict", lambda db, u: {})
    lances: list[str] = []
    monkeypatch.setattr(service.threading, "Thread",
                        lambda **kw: type("T", (), {
                            "start": lambda s: lances.append(kw["args"][0])})())
    with Session(base) as db:
        billing.get_or_create_balance(db, str(uid))
        rapport = service.lancer_rapport(db, str(uid), query="ma question",
                                         analysis_type="analyse_risques")
    assert rapport.statut == rm.EN_COURS
    assert rapport.progression == 0
    assert rapport.content == ""
    assert rapport.question == "ma question"
    assert lances == [str(rapport.id)], "la tâche doit être lancée en thread"


def test_rapport_termine_debite_et_archive_ensemble(base, monkeypatch):
    _brancher_moteur(monkeypatch)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.TERMINE
    assert rapport.progression == 100
    assert "# Titre" in rapport.content
    assert rapport.termine_at is not None
    assert rapport.tokens_entree == 100 and rapport.tokens_sortie == 200
    assert rapport.detail["credits"] == 25          # coût d'une analyse_risques
    assert _solde(base, uid) == 40 + 200 - 25


def test_echec_darchivage_ne_debite_rien(base, monkeypatch):
    """La régression que Task 2 corrige : le débit committait EN PREMIER.

    Jusqu'au 12/09, `consume_credits` clôturait sa transaction avant que
    `create_report` n'ouvre la sienne. Une panne entre les deux laissait le
    compte débité sans rapport. Ici l'archivage explose : rien ne doit bouger.

    PORTÉE DU TEST — ce socle est SQLite, où `with_for_update()` est un no-op :
    ce qui est prouvé ici est l'atomicité APPLICATIVE (débit et archivage dans
    une seule transaction, un seul commit, un rollback qui emporte les deux),
    pas le verrou de ligne concurrent de PostgreSQL. Deux débits réellement
    simultanés sur la même ligne de solde ne sont pas exerçables ici et ne
    doivent pas être lus comme couverts.
    """
    from app.modules.analysis import service

    _brancher_moteur(monkeypatch)
    uid = uuidlib.uuid4()

    def _archivage_impossible(db, rapport, result, *, statut, charged, viz=None):
        if statut == rm.TERMINE:
            raise RuntimeError("disque plein")
        return None

    monkeypatch.setattr(service, "_cloturer", _archivage_impossible)
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.ECHEC
    assert rapport.detail["raison"] == "echec_generation"
    assert _solde(base, uid) == 40 + 200, "des crédits ont été débités pour rien"
    with Session(base) as db:
        debits = db.scalars(select(CreditEvent).where(
            CreditEvent.action == "analyse_risques")).all()
    assert debits == [], "un événement de débit a survécu à l'échec"


def test_consume_credits_sans_commit_reste_annulable(base):
    """`commit=False` laisse le débit en attente : un rollback l'efface."""
    from app.modules.billing import service as billing

    uid = str(uuidlib.uuid4())
    with Session(base) as db:
        billing.get_or_create_balance(db, uid)
        res = billing.consume_credits(db, uid, "analyse_risques", commit=False)
        assert res["charged"] == 25
        db.rollback()
    assert _solde(base, uid) == 40


# --- Step 2 : étapes réelles et section en cours ---------------------------

def _etapes_observees(monkeypatch) -> list[tuple]:
    """Enregistre chaque écriture d'étape sans en changer l'effet."""
    from app.modules.analysis.service import Suivi

    vues: list[tuple] = []
    original = Suivi.etape

    def _espion(self, nom, progression, **detail):
        vues.append((nom, progression, detail.get("section")))
        return original(self, nom, progression, **detail)

    monkeypatch.setattr(Suivi, "etape", _espion)
    return vues


def test_sequence_des_etapes_et_section_en_cours(base, monkeypatch):
    """recherche → selection → couverture → redaction → finalisation."""
    # 3 titres `##` répartis dans 60 portions : la détection doit les voir au
    # fil du texte, et pas seulement à la fin.
    morceaux = ["## 1. Un\n"] + ["mot "] * 25 + ["## 2. Deux\n"] + ["mot "] * 25 \
        + ["## 3. Trois\n"] + ["fin"]
    _brancher_moteur(monkeypatch, chunks=morceaux)
    vues = _etapes_observees(monkeypatch)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    noms = [n for n, _, _ in vues]
    assert noms[0] == "recherche"
    for attendue in ("recherche", "selection", "couverture", "redaction",
                     "finalisation"):
        assert attendue in noms, noms
    # L'ordre des premières apparitions suit le pipeline.
    premieres = [noms.index(n) for n in ("recherche", "selection", "couverture",
                                         "redaction", "finalisation")]
    assert premieres == sorted(premieres), noms
    # Progression monotone, jamais au-dessus de 100.
    progressions = [p for _, p, _ in vues]
    assert progressions == sorted(progressions), progressions
    assert max(progressions) <= 100

    sections = [s for n, _, s in vues if n == "redaction" and s]
    assert sections, "aucune section détectée pendant la rédaction"
    assert all("/" in s for s in sections)
    total = int(sections[0].split("/")[1])
    assert [int(s.split("/")[0]) for s in sections] == sorted(
        int(s.split("/")[0]) for s in sections), sections
    assert all(int(s.split("/")[0]) <= total for s in sections), sections
    assert rapport.statut == rm.TERMINE


def test_le_denominateur_de_section_vient_de_la_directive():
    from app.modules.analysis.service import _sections_attendues

    # 3 axes + synthèse + conclusion + Sources pour l'analyse de risques.
    assert _sections_attendues("analyse_risques") == 6
    assert _sections_attendues("synthese_executive") == 8
    # Type inconnu : un dénominateur plancher, jamais une division par zéro.
    assert _sections_attendues("inexistant") >= 4


def test_evenements_sse_gardent_le_contrat_du_front(base, monkeypatch):
    """`step` et `progress` survivent jusqu'à Task 4 ; `etape` les double."""
    from app.modules.analysis import service
    from app.modules.billing import service as billing
    from app.modules.memory import service as memory

    uid = uuidlib.uuid4()
    monkeypatch.setattr(memory, "build_context", lambda db, u: "")
    monkeypatch.setattr(service, "_profile_dict", lambda db, u: {})
    monkeypatch.setattr(service, "INTERVALLE_SUIVI_SECONDES", 0.01)
    monkeypatch.setattr(service, "_solde", lambda db, u: 77)

    def _faux_moteur(rapport_id, **kw):
        """Avance la ligne étape par étape, puis la termine."""
        import app.db as app_db

        with app_db.SessionLocal() as db:
            r = db.get(Report, uuidlib.UUID(rapport_id))
            for nom, prog in (("recherche", 20), ("selection", 35),
                              ("redaction", 60)):
                r.etape, r.progression = nom, prog
                r.detail = {"message": f"étape {nom}"}
                db.commit()
                time.sleep(0.03)
            r.statut, r.progression, r.content = rm.TERMINE, 100, "corps"
            r.detail = {"credits": 25}
            db.commit()

    monkeypatch.setattr(service, "_executer_rapport", _faux_moteur)
    with Session(base) as db:
        billing.get_or_create_balance(db, str(uid))
        evts = [json.loads(e.removeprefix("data: ").strip())
                for e in service.stream_analysis(
                    db=db, user_id=str(uid), is_admin=False, query="q",
                    analysis_type="analyse_risques")]

    assert evts[0]["step"] == "start" and evts[0]["report_id"]
    assert all("progress" in e and "step" in e for e in evts), evts
    assert all("etape" in e for e in evts), evts
    # `detail` est présent partout, éventuellement vide : `start` et `done` le
    # portaient aux seuls événements intermédiaires, et Task 4 devait traiter
    # deux formes d'événement.
    assert all("detail" in e for e in evts), evts
    assert evts[0]["detail"] == {}
    etapes = [e["etape"] for e in evts if e.get("etape")]
    assert etapes[:3] == ["recherche", "selection", "redaction"], etapes
    # Anciens `step` conservés pour le front en production.
    assert {e["step"] for e in evts} <= {"start", "retrieve", "generate",
                                         "finalize", "done"}
    fin = evts[-1]
    assert fin["done"] is True and fin["progress"] == 100
    assert fin["statut"] == rm.TERMINE
    assert fin["data"]["content"] == "corps"
    assert fin["data"]["balance"] == 77
    assert fin["data"]["credits"] == 25
    assert fin["report_id"] == evts[0]["report_id"]


# --- Step 3 : annulation ---------------------------------------------------

def test_stop_pendant_la_redaction_nannule_aucun_credit(base, monkeypatch):
    """Le drapeau est posé par une AUTRE session, en pleine rédaction."""
    uid = uuidlib.uuid4()
    pose = {"fait": False}
    morceaux = ["## 1. Début\n"] + ["mot " for _ in range(200)]

    def _poser_le_stop(_chunk):
        if pose["fait"]:
            return
        pose["fait"] = True
        with Session(base) as autre:
            r = autre.scalars(select(Report)).one()
            r.annulation_demandee = True
            autre.commit()

    _brancher_moteur(monkeypatch, chunks=morceaux, avant_chunk=_poser_le_stop)
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.ANNULE
    assert rapport.content == "", "un rapport annulé ne se lit pas"
    assert rapport.detail["raison"] == "annule_par_utilisateur"
    partiel = rapport.detail.get("contenu_partiel") or ""
    assert partiel.startswith("## 1. Début")
    assert len(partiel) <= 2000
    assert _solde(base, uid) == 40 + 200, "un rapport annulé a été facturé"


def test_annuler_pose_le_drapeau_et_refuse_un_rapport_termine(base):
    from app.errors import AppError
    from app.modules.reports import service as reports

    uid = uuidlib.uuid4()
    with Session(base) as db:
        en_cours = _rapport(db, uid, statut=rm.EN_COURS, progression=10)
        fini = _rapport(db, uid, statut=rm.TERMINE)
        r = reports.demander_annulation(db, str(uid), str(en_cours.id))
        assert r.annulation_demandee is True
        # Idempotence : la tâche n'a pas encore rangé la ligne, un second clic
        # ne doit pas lever.
        reports.demander_annulation(db, str(uid), str(en_cours.id))
        with pytest.raises(AppError) as exc:
            reports.demander_annulation(db, str(uid), str(fini.id))
        assert exc.value.status_code == 409


# --- Step 4 : couverture, recherche élargie, génération forcée -------------

def test_couverture_non_ne_debite_rien_et_expose_les_sources(base, monkeypatch):
    _brancher_moteur(monkeypatch, couverture="non")
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.SOURCES_INSUFFISANTES
    assert rapport.detail["raison"] == "sources_insuffisantes"
    assert len(rapport.detail["sources"]) == 8
    assert rapport.detail["sources"][0]["url"].startswith("https://")
    assert _solde(base, uid) == 40 + 200, "une couverture nulle a été facturée"


def test_moins_de_cinq_sources_pertinentes_suffit_a_bloquer(base, monkeypatch):
    """Le seuil ne dépend pas du juge : 4 sources ne font pas un rapport."""
    _brancher_moteur(monkeypatch, citations=_citations(4), couverture="oui")
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.SOURCES_INSUFFISANTES
    assert _solde(base, uid) == 40 + 200


def test_couverture_partielle_genere_et_porte_la_raison(base, monkeypatch):
    _brancher_moteur(monkeypatch, couverture="partiel")
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.TERMINE
    assert rapport.detail["raison"] == "couverture_partielle"
    assert _solde(base, uid) == 40 + 200 - 25, "un rapport livré doit être facturé"


def test_forcer_genere_malgre_un_verdict_negatif(base, monkeypatch):
    """« Générer quand même » : débit normal, bandeau « couverture partielle »."""
    juges: list[int] = []
    _brancher_moteur(monkeypatch, citations=_citations(2), couverture="non")
    from app.modules.analysis import service

    monkeypatch.setattr(service, "_evaluer_couverture",
                        lambda q, c: juges.append(1) or "non")
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch, forcer=True)

    assert rapport.statut == rm.TERMINE
    assert rapport.detail["raison"] == "couverture_partielle"
    assert _solde(base, uid) == 40 + 200 - 25
    assert juges == [], "forcer doit court-circuiter le juge, pas le payer"


def test_elargir_ajoute_des_angles_une_seule_fois(base, monkeypatch):
    from app.modules.analysis import service
    from app.shared import search as web_search

    _brancher_moteur(monkeypatch)
    appels: list[list[str]] = []
    monkeypatch.setattr(web_search, "search_multi",
                        lambda angles, **kw: appels.append(list(angles))
                        or [_Source(i) for i in range(8)])
    monkeypatch.setattr(service, "_angles_elargis",
                        lambda t, q, p: ["angle A", "angle B"])
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch, elargir=True)

    assert rapport.statut == rm.TERMINE
    assert len(appels) == 1, "une seule passe de recherche, pas deux"
    assert "angle A" in appels[0] and "angle B" in appels[0]
    assert len(appels[0]) > 2, "les angles standards restent"


def test_le_juge_de_couverture_ne_bloque_jamais_un_rapport(monkeypatch):
    """Panne, quota, réponse illisible : on génère. Le juge n'est pas juge."""
    from app.modules.analysis import service
    from app.shared import llm_client
    from app.shared.llm_client.base import LLMResult

    cits = _citations(8)

    def _en_panne(**kw):
        raise RuntimeError("quota dépassé")

    monkeypatch.setattr(llm_client, "generate", _en_panne)
    assert service._evaluer_couverture("q", cits) == "oui"

    for texte, attendu in (("oui", "oui"), ("  Partiel.", "partiel"),
                           ("NON", "non"), ("je ne sais pas", "oui")):
        monkeypatch.setattr(llm_client, "generate",
                            lambda t=texte, **kw: LLMResult(text=t, model="m",
                                                            provider="p"))
        assert service._evaluer_couverture("q", cits) == attendu, texte
    # Aucune source : inutile de déranger un modèle pour le dire.
    assert service._evaluer_couverture("q", []) == "non"


def test_le_prompt_de_couverture_est_isole_et_ne_touche_pas_aux_directives():
    """Arbitrage §0 : les prompts de rapport ne bougent pas de ce chantier."""
    from app.modules.analysis import prompts
    from app.modules.analysis.service import PROMPT_COUVERTURE

    assert "{question}" in PROMPT_COUVERTURE and "{sources}" in PROMPT_COUVERTURE
    assert "partiel" in PROMPT_COUVERTURE
    assert PROMPT_COUVERTURE not in prompts.SYSTEM_PROMPT
    for directive in prompts.ANALYSIS_DIRECTIVES.values():
        assert "couverture" not in (directive.get("special_instructions") or "")


def test_relancer_cree_un_nouveau_rapport_sans_toucher_a_lancien(base, monkeypatch):
    from app.modules.analysis import service

    _brancher_moteur(monkeypatch, couverture="non")
    uid = uuidlib.uuid4()
    premier = _lancer(base, uid, monkeypatch)
    assert premier.statut == rm.SOURCES_INSUFFISANTES

    _brancher_moteur(monkeypatch, couverture="oui")
    with Session(base) as db:
        second = service.lancer_rapport(db, str(uid), query=premier.question,
                                        analysis_type=premier.analysis_type,
                                        forcer=True, attendre=True)
    assert str(second.id) != str(premier.id)
    assert second.statut == rm.TERMINE
    assert _relire(base, premier.id).statut == rm.SOURCES_INSUFFISANTES


# --- Step 5 : /run et /stream, un seul moteur ------------------------------

def test_run_et_stream_produisent_la_meme_ligne(base, monkeypatch):
    """Deux routes, un moteur : les deux lignes se ressemblent trait pour trait."""
    from app.modules.analysis import service

    _brancher_moteur(monkeypatch)
    monkeypatch.setattr(service, "INTERVALLE_SUIVI_SECONDES", 0.01)
    uid = uuidlib.uuid4()

    par_run = _lancer(base, uid, monkeypatch)
    with Session(base) as db:
        evts = [json.loads(e.removeprefix("data: ").strip())
                for e in service.stream_analysis(
                    db=db, user_id=str(uid), is_admin=False, query="ma question",
                    analysis_type="analyse_risques")]
    par_stream = _relire(base, uuidlib.UUID(evts[-1]["report_id"]))

    assert par_run.id != par_stream.id
    for champ in ("statut", "etape", "progression", "content", "analysis_type",
                  "question", "tokens_entree", "tokens_sortie", "modele"):
        assert getattr(par_run, champ) == getattr(par_stream, champ), champ
    assert par_run.detail["credits"] == par_stream.detail["credits"] == 25
    assert _solde(base, uid) == 40 + 200 - 50, "deux rapports, deux débits"


def test_run_attend_le_terme_sur_sa_propre_session(base, monkeypatch):
    """`/run` n'archive pas depuis la session de la requête (spec §0)."""

    _brancher_moteur(monkeypatch)
    sessions: list[int] = []
    import app.db as app_db

    fabrique = app_db.SessionLocal

    def _tracee():
        s = fabrique()
        sessions.append(id(s))
        return s

    monkeypatch.setattr(app_db, "SessionLocal", _tracee)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)
    assert rapport.statut == rm.TERMINE
    assert len(sessions) == 1, "le moteur doit ouvrir UNE session propre"


def test_routes_de_suivi_montees():
    from fastapi.testclient import TestClient

    from app.main import app

    chemins = TestClient(app).get("/openapi.json").json()["paths"]
    for chemin in ("/analysis/run", "/analysis/stream",
                   "/reports/{report_id}", "/reports/{report_id}/annuler",
                   "/reports/{report_id}/relancer"):
        assert chemin in chemins, chemin
    detail = chemins["/reports/{report_id}"]["get"]["responses"]["200"]
    ref = detail["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("ReportDetail")
    # `/run` rend le même ReportDetail : une seule forme de rapport côté front.
    assert chemins["/analysis/run"]["post"]["responses"]["200"]["content"][
        "application/json"]["schema"]["$ref"] == ref


# ===========================================================================
# Task 2 — relecture, correctifs (notification unique, échéance globale,
# viz hors transaction, reprise après troncature)
# ===========================================================================

def _compter_les_emails(monkeypatch) -> list[str]:
    """Compte les `notification.prevenir` sans en déclencher aucun."""
    from app.modules.reports import notification

    envois: list[str] = []
    monkeypatch.setattr(notification, "prevenir",
                        lambda db, uid, *, titre, contenu, sources=None:
                        envois.append(titre) or True)
    return envois


def test_un_seul_email_pour_le_rapport_offert(base, monkeypatch):
    """Le moteur prévient ; `offrir` ne prévient plus.

    `offrir` envoyait son propre email APRÈS que `_executer_rapport` ait déjà
    envoyé le sien : le seul rapport dont on soigne l'arrivée partait en
    double. La notification appartient au moteur — c'est le seul endroit qui
    tourne que le navigateur soit là ou non.
    """
    from app.modules.analysis import onboarding

    _brancher_moteur(monkeypatch)
    envois = _compter_les_emails(monkeypatch)
    uid = str(uuidlib.uuid4())
    monkeypatch.setattr(onboarding, "deja_offert", lambda db, u: False)
    monkeypatch.setattr(onboarding, "profil_utilisable",
                        lambda db, u: {"company_name": "Axial", "sector": "SaaS",
                                       "target_market": "France"})
    with Session(base) as db:
        rapport_id = onboarding.offrir(db, uid)

    assert rapport_id, "le rapport offert doit aboutir"
    assert _relire(base, uuidlib.UUID(rapport_id)).statut == rm.TERMINE
    assert len(envois) == 1, f"{len(envois)} email(s) pour un rapport : {envois}"


def test_un_seul_email_par_rapport_sur_le_chemin_run(base, monkeypatch):
    """`/run` attend le terme, mais ne notifie pas de son côté."""
    _brancher_moteur(monkeypatch)
    envois = _compter_les_emails(monkeypatch)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.TERMINE
    assert len(envois) == 1, f"{len(envois)} email(s) pour un rapport : {envois}"


def test_session_du_moteur_impossible_range_le_rapport_en_echec(base, monkeypatch):
    """Pool saturé à l'ouverture : la ligne ne doit pas rester `en_cours`.

    `with SessionLocal() as db` était hors de tout `try` : le thread mourait
    avant d'avoir pu écrire un statut, et rien ne rangeait la ligne. Une
    seconde session, très courte, s'en charge désormais.
    """
    import app.db as app_db

    _brancher_moteur(monkeypatch)
    fabrique = app_db.SessionLocal
    ouvertures = {"n": 0}

    def _premiere_ouverture_impossible():
        ouvertures["n"] += 1
        if ouvertures["n"] == 1:
            raise RuntimeError("QueuePool limit of size 5 overflow 10 reached")
        return fabrique()

    monkeypatch.setattr(app_db, "SessionLocal", _premiere_ouverture_impossible)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.ECHEC, "la ligne est restée en_cours"
    assert rapport.detail["raison"] == "echec_generation"
    assert ouvertures["n"] == 2, "la seconde session de secours n'a pas tourné"
    assert _solde(base, uid) == 40 + 200


def _echeance_depassee(monkeypatch, secondes=-1):
    """Échéance globale déjà dépassée — une valeur négative expire au premier
    contrôle, sans faire attendre le test une demi-heure."""
    from app import config as app_config

    monkeypatch.setattr(app_config, "DELAI_MAX_RAPPORT_SECONDES", secondes)


def test_echeance_globale_entre_deux_etapes_range_en_echec(base, monkeypatch):
    """Rien ne bornait la durée d'un rapport : les délais des fournisseurs
    sont des délais par lecture, et une reprise peut enchaîner quatre appels
    de 32 000 tokens. Le premier contrôle d'étape doit trancher."""
    _brancher_moteur(monkeypatch)
    _echeance_depassee(monkeypatch)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.ECHEC
    assert rapport.detail["raison"] == "delai_depasse"
    assert "délai" in rapport.detail["message"]
    assert rapport.content == ""
    assert _solde(base, uid) == 40 + 200, "un rapport abandonné a été facturé"


def test_echeance_globale_pendant_la_redaction_range_en_echec(base, monkeypatch):
    """L'échéance est relue toutes les 20 portions, comme le Stop."""
    from app import config as app_config

    etapes_vues: list[str] = []
    morceaux = ["## 1. Début\n"] + ["mot " for _ in range(200)]

    def _vieillir(_chunk):
        # Échéance franchie APRÈS le début de la rédaction : le contrôle des
        # 20 portions est le seul à pouvoir l'attraper.
        app_config.DELAI_MAX_RAPPORT_SECONDES = -1

    monkeypatch.setattr(app_config, "DELAI_MAX_RAPPORT_SECONDES", 1800)
    _brancher_moteur(monkeypatch, chunks=morceaux, avant_chunk=_vieillir)
    vues = _etapes_observees(monkeypatch)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)
    etapes_vues += [n for n, _, _ in vues]

    assert "redaction" in etapes_vues, "la rédaction n'a pas commencé"
    assert rapport.statut == rm.ECHEC
    assert rapport.detail["raison"] == "delai_depasse"
    assert _solde(base, uid) == 40 + 200


def test_le_flux_sse_sarrete_quand_lecheance_passe(base, monkeypatch):
    """La boucle de suivi ne tourne pas indéfiniment sur un rapport figé.

    Le cas qui compte : la tâche est morte sans avoir pu écrire son statut. La
    ligne reste `en_cours` pour toujours, et la boucle tenait une connexion —
    en aggravant la saturation qui l'avait causée.
    """
    from app.modules.analysis import service
    from app.modules.billing import service as billing
    from app.modules.memory import service as memory

    uid = uuidlib.uuid4()
    monkeypatch.setattr(memory, "build_context", lambda db, u: "")
    monkeypatch.setattr(service, "_profile_dict", lambda db, u: {})
    monkeypatch.setattr(service, "INTERVALLE_SUIVI_SECONDES", 0.01)
    # Tâche morte : la ligne ne quittera jamais `en_cours`.
    monkeypatch.setattr(service, "_executer_rapport", lambda rid, **kw: None)
    _echeance_depassee(monkeypatch)

    with Session(base) as db:
        billing.get_or_create_balance(db, str(uid))
        evts = [json.loads(e.removeprefix("data: ").strip())
                for e in service.stream_analysis(
                    db=db, user_id=str(uid), is_admin=False, query="q",
                    analysis_type="analyse_risques")]

    fin = evts[-1]
    assert fin["step"] == "done" and fin["done"] is True
    assert fin["code"] == "delai_depasse"
    assert "délai" in fin["error"]
    assert "detail" in fin
    # La ligne reste consultable : le flux abandonne le suivi, pas le rapport.
    assert _relire(base, uuidlib.UUID(evts[0]["report_id"])).statut == rm.EN_COURS


def _flux_par_appels(appels: list[dict], reponses):
    """Bouchon de `stream_text` qui enregistre chaque appel et joue `reponses`
    (liste de `(morceaux, stop_reason)`, la dernière rejouée indéfiniment)."""

    def _flux(*, system, prompt, tier="chat", max_tokens=4000, history=None,
              mesure=None, fournisseur=None, **kw):
        appels.append({"prompt": prompt, "history": history,
                       "fournisseur": fournisseur})
        morceaux, raison = reponses[min(len(appels) - 1, len(reponses) - 1)]
        if mesure is not None:
            mesure.update({"model": "claude-test", "provider": "claude",
                           "input_tokens": mesure.get("input_tokens", 0) + 100,
                           "output_tokens": mesure.get("output_tokens", 0) + 200})
        for m in morceaux:
            yield m
        return raison

    return _flux


def test_reprise_apres_troncature_recolle_et_epingle_le_fournisseur(base, monkeypatch):
    """La panne du 24/08, sur le NOUVEAU chemin de rédaction.

    Les tests de troncature existants portaient sur `claude.generate`, que la
    production n'emprunte plus pour les rapports : la reprise de `_rediger`
    (historique, plafond, cumul de la mesure) n'était couverte par rien.
    """
    from app.shared import llm_client
    from app.shared.llm_client.claude import SUITE_CONSIGNE

    _brancher_moteur(monkeypatch)
    appels: list[dict] = []
    monkeypatch.setattr(llm_client, "stream_text", _flux_par_appels(appels, [
        (["## 1. Début\n", "coupé"], "max_tokens"),
        (["## 2. Suite\n", "fin"], "end_turn"),
    ]))
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.TERMINE
    # Le texte des deux passes est RECOLLÉ, dans l'ordre, sans rien perdre.
    assert rapport.content == "## 1. Début\ncoupé## 2. Suite\nfin"
    assert len(appels) == 2, "une reprise et une seule : la 2e passe a conclu"

    # Alternance de l'historique de reprise : user (prompt initial) / assistant
    # (ce qui a été écrit) / user (la consigne de suite). Une alternance cassée
    # est refusée par Claude et acceptée en silence par Gemini.
    historique = appels[1]["history"]
    assert [m["role"] for m in historique] + ["user"] == ["user", "assistant", "user"]
    assert historique[0]["content"] == appels[0]["prompt"]
    assert historique[1]["content"] == "## 1. Début\ncoupé"
    assert appels[1]["prompt"] == SUITE_CONSIGNE

    # Fournisseur épinglé sur celui qui a commencé : sans épingle, `stream_text`
    # rejoue sa chaîne de repli et la fin du rapport peut être écrite par
    # l'autre modèle — deux styles recollés dans un même document.
    assert appels[0]["fournisseur"] is None
    assert appels[1]["fournisseur"] == "claude"

    # La mesure est cumulée d'un appel à l'autre : deux passes payées, deux
    # passes comptées.
    assert rapport.tokens_entree == 200 and rapport.tokens_sortie == 400


def test_les_reprises_sont_plafonnees_et_le_rapport_nest_pas_facture(base, monkeypatch):
    """Au-delà du plafond, aucune reprise supplémentaire n'est tentée."""
    from app.modules.analysis import service
    from app.shared import llm_client

    _brancher_moteur(monkeypatch)
    appels: list[dict] = []
    monkeypatch.setattr(llm_client, "stream_text", _flux_par_appels(appels, [
        (["## 1. Encore\n"], "max_tokens"),  # rejoué à chaque appel
    ]))
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert len(appels) == service.REPRISES_REDACTION_MAX + 1 == 4, appels
    # Une quatrième reprise (le 5e appel) n'est jamais tentée.
    assert rapport.statut == rm.DEGRADE
    assert rapport.detail["raison"] == "truncated_generation"
    assert _solde(base, uid) == 40 + 200, "un rapport tronqué n'est pas facturé"
    # Toutes les reprises restent chez le fournisseur de la première passe.
    assert {a["fournisseur"] for a in appels[1:]} == {"claude"}


def test_attendre_relit_la_ligne_sans_laisser_de_transaction_ouverte(base, monkeypatch):
    """`attendre=True` faisait `expire_all()` sans `rollback()`.

    `expire_all` vide le cache d'identité mais LAISSE la transaction de lecture
    ouverte : plusieurs minutes d'« idle in transaction » par appel `/run`, et
    sous une isolation plus stricte que READ COMMITTED la relecture rendait la
    ligne encore `en_cours` — `offrir` concluait alors « non abouti » sur un
    rapport réussi. Un rollback clôt la transaction ET expire les objets.
    """
    from app.modules.analysis import service
    from app.modules.billing import service as billing

    _brancher_moteur(monkeypatch)
    uid = uuidlib.uuid4()
    with Session(base) as db:
        billing.get_or_create_balance(db, str(uid))
        billing.grant_purchased(db, str(uid), 200)
    with Session(base) as db:
        gestes: list[str] = []
        rollback_original, expire_original = db.rollback, db.expire_all
        monkeypatch.setattr(db, "rollback",
                            lambda: gestes.append("rollback") or rollback_original())
        monkeypatch.setattr(db, "expire_all",
                            lambda: gestes.append("expire_all") or expire_original())
        rapport = service.lancer_rapport(db, str(uid), query="ma question",
                                         analysis_type="analyse_risques",
                                         attendre=True)
        assert "rollback" in gestes, gestes
        assert "expire_all" not in gestes, "expire_all seul laisse la transaction"
        assert rapport.statut == rm.TERMINE, "relecture non rafraîchie"


def test_get_or_create_balance_ne_commit_pas_sous_commit_false(base, monkeypatch):
    """Un seul commit, celui de la clôture (invariant annoncé par `finalize`).

    La création du solde committait toujours : inoffensif tant que rien
    n'attendait dans la session, mais c'était un piège pour le prochain
    appelant — le commit aurait emporté la moitié d'une transaction de clôture.
    """
    from app.modules.billing import service as billing

    uid = str(uuidlib.uuid4())  # aucun solde en base : la création aura lieu
    with Session(base) as db:
        commits: list[int] = []
        commit_original = db.commit
        monkeypatch.setattr(db, "commit",
                            lambda: commits.append(1) or commit_original())

        res = billing.consume_credits(db, uid, "analyse_risques", commit=False)
        assert res["charged"] == 25
        assert commits == [], "un commit est parti avant la clôture"

        db.commit()  # LA clôture, la seule
        assert len(commits) == 1

    # Le solde créé et le débit sont bien acquis par ce commit unique.
    assert _solde(base, uid) == 40 - 25


def test_une_course_sur_une_viz_ne_fait_pas_echouer_le_rapport(base, monkeypatch):
    """Les `VizRendu` sont partagés par empreinte : deux rapports concurrents
    peuvent produire la même. Dans la transaction de clôture, cette collision
    laissait la session en `PendingRollbackError`, le commit explosait et un
    rapport de 32 000 tokens entièrement produit partait en `echec`."""
    from app.modules.viz import service as viz_service
    from app.modules.viz.models import VizRendu

    _brancher_moteur(monkeypatch)
    with Session(base) as autre:  # l'empreinte est déjà prise par un AUTRE rapport
        autre.add(VizRendu(empreinte="e" * 64, vl={"mark": "bar"}))
        autre.commit()

    def _preparer_en_course(db, markdown):
        db.add(VizRendu(empreinte="e" * 64, vl={"mark": "line"}))
        db.flush()  # IntegrityError : la clé primaire existe déjà
        return []

    monkeypatch.setattr(viz_service, "preparer", _preparer_en_course)
    uid = uuidlib.uuid4()
    rapport = _lancer(base, uid, monkeypatch)

    assert rapport.statut == rm.TERMINE, "la course a fait échouer le rapport"
    assert rapport.viz is None, "aucune viz, mais le rapport est là"
    assert "# Titre" in rapport.content
    assert rapport.detail["credits"] == 25
    assert _solde(base, uid) == 40 + 200 - 25


def test_run_transmet_elargir_et_forcer(base, monkeypatch):
    """« Recherche élargie » et « Générer quand même » sur les DEUX chemins.

    `AnalysisRequest` portait déjà les deux drapeaux et `/analysis/run` les
    jetait : la reprise après « sources insuffisantes » ne marchait que par
    `/stream` ou `/reports/{id}/relancer`.
    """
    from app.modules.analysis import router as analysis_router
    from app.modules.analysis import service
    from app.modules.analysis.schemas import AnalysisRequest
    from app.modules.auth.schemas import AuthUser

    vus: dict = {}
    uid = uuidlib.uuid4()
    with Session(base) as db:
        ligne = _rapport(db, uid, statut=rm.TERMINE, content="corps",
                         analysis_type="analyse_risques")
        monkeypatch.setattr(service, "lancer_rapport",
                            lambda db_, user_id, **kw: vus.update(kw) or ligne)
        reponse = analysis_router.run(
            AnalysisRequest(query="q", analysis_type="analyse_risques",
                            elargir=True, forcer=True),
            user=AuthUser(id=str(uid), email="fondateur@exemple.fr"), db=db)

    assert vus["elargir"] is True and vus["forcer"] is True
    assert vus["attendre"] is True
    assert reponse.id == str(ligne.id)
    # Même schéma que `/stream` : un seul contrat d'entrée pour les deux routes.
    assert {"elargir", "forcer"} <= set(AnalysisRequest.model_fields)


# ===========================================================================
# Task 3 — gestion, partage public, export, signalement, balayage
# ===========================================================================

def _base_http():
    """Base SQLite PARTAGÉE entre le test et le client HTTP.

    `sqlite://` seul rend une base neuve PAR connexion : le `TestClient` en
    ouvre une autre que le test et n'y trouverait aucune table.
    """
    import app.modules.viz.models  # noqa: F401 — enregistre `viz_rendus`

    engine = create_engine("sqlite://", future=True,
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["projects"],
        # Les dossiers sont ceux des conversations : supprimer un dossier
        # compte les deux contenus (spec §4).
        Base.metadata.tables["conversations"],
        Base.metadata.tables["messages"],
        Base.metadata.tables["reports"],
        Base.metadata.tables["report_feedback"],
        Base.metadata.tables["credit_balances"],
        Base.metadata.tables["credit_events"],
        Base.metadata.tables["viz_rendus"],
    ])
    return engine


def _client(engine, uid, *, is_admin=False, full_name=None,
            email="fondateur@exemple.fr"):
    """`TestClient` sur l'app réelle : le seul moyen de prouver que les ROUTES
    (méthodes, codes, corps) tiennent, et pas seulement le service."""
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import (
        get_current_admin, get_current_user, get_current_user_optionnel)

    def _db():
        with Session(engine) as s:
            yield s

    utilisateur = AuthUser(id=str(uid), email=email, full_name=full_name,
                           is_admin=is_admin)
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: utilisateur
    # Les images de graphiques acceptent AUSSI l'anonyme (`?p=`) : leur
    # dépendance est distincte et doit être branchée séparément.
    app.dependency_overrides[get_current_user_optionnel] = lambda: utilisateur
    app.dependency_overrides[get_current_admin] = lambda: (
        utilisateur if is_admin else _refus_admin())
    return TestClient(app)


def _refus_admin():
    from app.errors import AppError

    raise AppError("Accès réservé aux administrateurs.", 403, code="forbidden")


def _anonyme() -> None:
    """Coupe l'authentification : ce que voit un visiteur de la page publique."""
    from app.main import app
    from app.modules.auth.security import get_current_user_optionnel

    app.dependency_overrides[get_current_user_optionnel] = lambda: None


@pytest.fixture
def http():
    """Engine partagé + client authentifié, dépendances restaurées à la fin."""
    from app.main import app

    engine = _base_http()
    uid = uuidlib.uuid4()
    try:
        yield engine, uid
    finally:
        app.dependency_overrides.clear()


def _datee(db, uid, jours, **kw):
    """Rapport daté : l'ordre de liste se vérifie sur des dates explicites,
    pas sur la vitesse d'insertion."""
    r = _rapport(db, uid, created_at=dt.datetime(2026, 9, 1, 12, 0,
                                                 tzinfo=dt.timezone.utc)
                 - dt.timedelta(days=jours), **kw)
    return r


# --- Liste, tri, pagination (§4) -------------------------------------------

def test_liste_en_cours_puis_epingles_puis_date(http):
    engine, uid = http
    with Session(engine) as db:
        attendus = {str(_datee(db, uid, 5, title="Vieux", statut=rm.TERMINE).id),
                    str(_datee(db, uid, 1, title="Récent", statut=rm.TERMINE).id),
                    str(_datee(db, uid, 9, title="Épinglé", statut=rm.TERMINE,
                               pinned_at=dt.datetime(2026, 9, 1,
                                                     tzinfo=dt.timezone.utc)).id),
                    str(_datee(db, uid, 30, title="En cours", statut=rm.EN_COURS,
                               progression=62).id)}
    page = _client(engine, uid).get("/reports").json()
    assert [i["title"] for i in page["items"]] == [
        "En cours", "Épinglé", "Récent", "Vieux"]
    assert page["has_more"] is False
    # Un rapport en cours reste en tête MÊME s'il est le plus ancien : c'est
    # celui que l'utilisateur cherche à rouvrir.
    assert page["items"][0]["progression"] == 62
    assert {i["id"] for i in page["items"]} == attendus


def test_pagination_par_curseur_ne_saute_ni_ne_repete_aucun_rapport(http):
    engine, uid = http
    with Session(engine) as db:
        # Deux rapports à la MÊME date : sans départage sur l'identifiant, le
        # jumeau du rapport borne disparaissait de la fenêtre suivante.
        meme = dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.timezone.utc)
        for i in range(7):
            _rapport(db, uid, title=f"R{i}", statut=rm.TERMINE,
                     created_at=meme - dt.timedelta(days=i // 2))
        _rapport(db, uid, title="P", statut=rm.TERMINE, created_at=meme,
                 pinned_at=meme)
        _rapport(db, uid, title="E", statut=rm.EN_COURS, created_at=meme)
    client = _client(engine, uid)

    vus, before, tours = [], None, 0
    while True:
        tours += 1
        assert tours < 20, "pagination qui ne termine pas"
        url = "/reports?limit=3" + (f"&before={before}" if before else "")
        page = client.get(url).json()
        vus.extend(i["id"] for i in page["items"])
        if not page["has_more"]:
            break
        before = page["items"][-1]["id"]
    assert len(vus) == 9, vus
    assert len(set(vus)) == 9, "un rapport a été rendu deux fois"
    # L'ordre complet est celui d'une liste non paginée.
    entier = client.get("/reports?limit=100").json()["items"]
    assert vus == [i["id"] for i in entier]
    # La première page traverse bien les rangs : en cours, épinglé, puis date.
    # R0 et R1 partagent leur date — leur ordre relatif est celui des
    # identifiants, donc indéterminé ici ; c'est le rang qui est sous test.
    tete = [i["title"] for i in client.get("/reports?limit=3").json()["items"]]
    assert tete[:2] == ["E", "P"] and tete[2] in ("R0", "R1")


def test_liste_ecarte_les_archives_sauf_demande_explicite(http):
    engine, uid = http
    with Session(engine) as db:
        _datee(db, uid, 1, title="Actif", statut=rm.TERMINE)
        _datee(db, uid, 2, title="Rangé", statut=rm.TERMINE,
               archived_at=dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc))
    client = _client(engine, uid)
    assert [i["title"] for i in client.get("/reports").json()["items"]] == ["Actif"]
    page = client.get("/reports?inclure_archives=true").json()
    assert [i["title"] for i in page["items"]] == ["Actif", "Rangé"]
    assert page["items"][1]["archived_at"] is not None


def test_la_liste_porte_le_cout_paye_et_le_dossier_sans_le_contenu(http):
    """`ReportOut` doit suffire à la liste : statut, crédits, tokens, dossier.
    Sans eux, le front rechargeait chaque rapport pour afficher une pastille."""
    import app.modules.intelligence.service as intel

    engine, uid = http
    with Session(engine) as db:
        projet = intel.create_project(db, str(uid), "Dossier", None)
        _rapport(db, uid, statut=rm.TERMINE, content="x" * 5000,
                 project_id=projet.id, tokens_entree=31000, tokens_sortie=9000,
                 detail={"credits": 25})
        pid = str(projet.id)
    item = _client(engine, uid).get("/reports").json()["items"][0]
    assert item["credits"] == 25 and item["tokens_entree"] == 31000
    assert item["tokens_sortie"] == 9000 and item["project_id"] == pid
    assert item["statut"] == rm.TERMINE
    assert "content" not in item, "le contenu n'a rien à faire dans la liste"


# --- PATCH : renommer, archiver, épingler, classer (§4) --------------------

def test_patch_renomme_archive_epingle_et_deplace(http):
    import app.modules.intelligence.service as intel

    engine, uid = http
    with Session(engine) as db:
        r = _rapport(db, uid, statut=rm.TERMINE, content="corps")
        projet = intel.create_project(db, str(uid), "Fusions", None)
        rid, pid = str(r.id), str(projet.id)
    client = _client(engine, uid)

    assert client.patch(f"/reports/{rid}",
                        json={"title": "  Marché   du   lithium  "}
                        ).json()["title"] == "Marché du lithium"
    # Un titre vide est refusé : « Sans titre » serait une invention du serveur.
    vide = client.patch(f"/reports/{rid}", json={"title": "   "})
    assert (vide.status_code, vide.json()["error"]["code"]) == (400, "titre_vide")

    assert client.patch(f"/reports/{rid}", json={"pinned": True}
                        ).json()["pinned_at"] is not None
    # Archiver dépingle : un rapport rangé n'occupe plus la tête de liste.
    archive = client.patch(f"/reports/{rid}", json={"archived": True}).json()
    assert archive["archived_at"] is not None and archive["pinned_at"] is None
    assert client.patch(f"/reports/{rid}", json={"archived": False}
                        ).json()["archived_at"] is None

    assert client.patch(f"/reports/{rid}", json={"project_id": pid}
                        ).json()["project_id"] == pid
    # Champ ABSENT du corps : le dossier ne bouge pas (sémantique PATCH).
    assert client.patch(f"/reports/{rid}", json={"title": "Titre"}
                        ).json()["project_id"] == pid
    # Champ à `null` EXPLICITE : « Retirer du dossier ».
    assert client.patch(f"/reports/{rid}", json={"project_id": None}
                        ).json()["project_id"] is None


def test_deplacer_vers_le_dossier_dun_autre_rend_404(http):
    """404 et non 403 : on ne confirme pas l'existence d'un dossier qui n'est
    pas le sien, et un identifiant deviné ne déplace rien."""
    import app.modules.intelligence.service as intel

    engine, uid = http
    with Session(engine) as db:
        r = _rapport(db, uid, statut=rm.TERMINE, content="corps")
        autre = intel.create_project(db, str(uuidlib.uuid4()), "Privé", None)
        rid, pid = str(r.id), str(autre.id)
    client = _client(engine, uid)
    res = client.patch(f"/reports/{rid}", json={"project_id": pid})
    assert res.status_code == 404
    res = client.patch(f"/reports/{rid}", json={"project_id": "pas-un-uuid"})
    assert res.status_code == 404
    with Session(engine) as db:
        assert db.get(Report, uuidlib.UUID(rid)).project_id is None


def test_un_rapport_actif_empeche_la_suppression_du_dossier(http):
    """Même refus que pour les conversations (`projet_non_vide`) : la FK est
    SET NULL, le rapport survivrait, mais il quitterait son dossier sans que
    personne ne l'ait demandé."""
    import app.modules.intelligence.service as intel

    engine, uid = http
    with Session(engine) as db:
        # SQLite n'applique les clés étrangères que sur demande : sans ce
        # PRAGMA, le SET NULL de `reports.project_id` ne serait pas exercé.
        db.execute(text("PRAGMA foreign_keys=ON"))
        projet = intel.create_project(db, str(uid), "Dossier", None)
        r = _rapport(db, uid, statut=rm.TERMINE, content="c",
                     project_id=projet.id)
        pid, rid = str(projet.id), str(r.id)

        with pytest.raises(intel.AppError) as e:
            intel.delete_project(db, str(uid), pid)
        assert (e.value.status_code, e.value.code) == (409, "projet_non_vide")
        assert "1 rapport" in e.value.message

        # Archivé = plus actif : la suppression passe et le rapport survit.
        db.get(Report, uuidlib.UUID(rid)).archived_at = dt.datetime.now(
            dt.timezone.utc)
        db.commit()
        intel.delete_project(db, str(uid), pid)
        assert db.get(intel.Project, uuidlib.UUID(pid)) is None
        db.expire_all()
        survivant = db.get(Report, uuidlib.UUID(rid))
        assert survivant is not None and survivant.project_id is None


# --- Coût de revient réservé à l'administration (§4) ----------------------

def test_le_prix_de_revient_nest_lisible_que_par_un_admin(http):
    engine, uid = http
    with Session(engine) as db:
        r = _rapport(db, uid, statut=rm.TERMINE, content="corps",
                     cout_micro_eur=71_000, cout_recherche_micro_eur=13_800,
                     detail={"credits": 25})
        rid = str(r.id)

    normal = _client(engine, uid).get(f"/reports/{rid}").json()
    assert normal["credits"] == 25, "les crédits payés restent visibles"
    assert normal["cout_micro_eur"] is None
    assert normal["cout_recherche_micro_eur"] is None

    admin = _client(engine, uid, is_admin=True).get(f"/reports/{rid}").json()
    assert admin["cout_micro_eur"] == 71_000
    assert admin["cout_recherche_micro_eur"] == 13_800

    # Le dict lui-même ne PORTE pas la clé pour un non-admin : un appelant qui
    # sérialise autrement que par `ReportDetail` ne peut pas la fuiter.
    with Session(engine) as db:
        ligne = db.get(Report, uuidlib.UUID(rid))
        assert "cout_micro_eur" not in reports_service.detail_dict(ligne)
        assert "cout_micro_eur" in reports_service.detail_dict(ligne, is_admin=True)


# --- Recherche (§4) --------------------------------------------------------

def test_recherche_titre_et_contenu_avec_extrait_borne(http):
    engine, uid = http
    with Session(engine) as db:
        _rapport(db, uid, title="Marché du lithium", statut=rm.TERMINE,
                 content="Rien de pertinent ici.")
        _rapport(db, uid, title="Autre sujet", statut=rm.TERMINE,
                 content="A" * 300 + " lithium " + "B" * 300)
        _rapport(db, uid, title="Rangé lithium", statut=rm.TERMINE, content="x",
                 archived_at=dt.datetime.now(dt.timezone.utc))
    client = _client(engine, uid)

    res = client.get("/reports/search?q=lithium").json()
    titres = {r["title"] for r in res}
    assert titres == {"Marché du lithium", "Autre sujet"}
    assert "Rangé lithium" not in titres, "un rapport archivé est hors périmètre"
    trouve = next(r for r in res if r["title"] == "Autre sujet")
    # ±80 caractères autour de la première occurrence, coupes marquées.
    assert "lithium" in trouve["extrait"]
    assert trouve["extrait"].startswith("…") and trouve["extrait"].endswith("…")
    assert len(trouve["extrait"]) <= 2 * 80 + len("lithium") + 2

    for court in ("", "li"):
        res = client.get(f"/reports/search?q={court}")
        assert (res.status_code, res.json()["error"]["code"]) \
            == (400, "requete_trop_courte")

    # `%` et `_` sont les jokers du LIKE : échappés, ils ne ramènent pas tout.
    assert client.get("/reports/search?q=%25%25%25").json() == []


def test_recherche_plafonnee_a_vingt_resultats(http):
    engine, uid = http
    with Session(engine) as db:
        for i in range(25):
            _rapport(db, uid, title=f"Lithium {i}", statut=rm.TERMINE, content="x")
    assert len(_client(engine, uid).get("/reports/search?q=lithium").json()) == 20


# --- Partage public (§0, §4) ----------------------------------------------

def test_partage_rend_un_jeton_de_22_caracteres_et_une_url_lisible(http):
    engine, uid = http
    with Session(engine) as db:
        r = _rapport(db, uid, title="Marché du lithium en Europe",
                     statut=rm.TERMINE, content="# Corps\n\nTexte.")
        rid = str(r.id)
    client = _client(engine, uid, full_name="Miradie Buranturu")

    ouvert = client.post(f"/reports/{rid}/partage").json()
    jeton = ouvert["jeton"]
    assert len(jeton) == 22, jeton
    assert ouvert["url"] == f"/p/miradie-buranturu/marche-du-lithium-en-europe-{jeton}"
    # Idempotent : un second clic ne doit pas invalider le lien déjà transmis.
    assert client.post(f"/reports/{rid}/partage").json() == ouvert

    public = client.get(f"/partage/{jeton}")
    assert public.status_code == 200
    assert public.json()["pseudo"] == "miradie-buranturu"

    assert client.delete(f"/reports/{rid}/partage").status_code == 204
    assert client.get(f"/partage/{jeton}").status_code == 404
    # Révoquer deux fois est un succès : le lien ne marche pas, c'est l'objet.
    assert client.delete(f"/reports/{rid}/partage").status_code == 204
    # Repartager rend un jeton NEUF : l'ancien lien reste mort.
    assert client.post(f"/reports/{rid}/partage").json()["jeton"] != jeton


def test_pseudo_replie_sur_la_partie_locale_de_lemail(http):
    engine, uid = http
    with Session(engine) as db:
        rid = str(_rapport(db, uid, title="Étude", statut=rm.TERMINE,
                           content="corps").id)
    # Aucun `full_name` dans les métadonnées Supabase : c'est le cas le plus
    # courant sur les comptes créés par lien magique.
    url = _client(engine, uid, email="Miradie.B@exemple.fr").post(
        f"/reports/{rid}/partage").json()["url"]
    assert url.startswith("/p/miradie-b/etude-")
    assert reports_service.pseudo_de(None, None) == "axial"
    # Accents et ponctuation ne survivent pas à une URL.
    assert reports_service.pseudo_de("Élodie Ké-Ñan", None) == "elodie-ke-nan"


def test_la_page_publique_ne_montre_ni_couts_ni_documents_internes(http):
    """Liste blanche stricte : un lien transmis par erreur ne doit rien dire du
    coffre de l'utilisateur, ni de ce que le rapport a coûté."""
    engine, uid = http
    sources = [
        {"title": "INSEE", "url": "https://insee.fr", "source": "web"},
        {"title": "business-plan-confidentiel.pdf", "source": "documents"},
        {"title": "Notes internes", "source": "notion"},
    ]
    with Session(engine) as db:
        r = _rapport(db, uid, title="Étude", statut=rm.DEGRADE,
                     content="# Corps", sources=sources,
                     viz=[{"index": 0, "empreinte": "a" * 64, "vl": {"x": 1},
                           "statut": "ok", "kind": "bar", "spec": {}}],
                     question="Quelle est la marge de ACME ?",
                     cout_micro_eur=71_000, tokens_entree=31_000,
                     detail={"credits": 25, "raison": "couverture_partielle"})
        rid = str(r.id)
    client = _client(engine, uid)
    jeton = client.post(f"/reports/{rid}/partage").json()["jeton"]
    vue = client.get(f"/partage/{jeton}").json()

    assert set(vue) == {"title", "content", "sources", "viz", "analysis_type",
                        "created_at", "pseudo"}
    assert [s["title"] for s in vue["sources"]] == ["INSEE"]
    brut = json.dumps(vue, default=str)
    for interdit in ("business-plan-confidentiel", "Notes internes", "71000",
                     "credits", "marge de ACME", str(uid), rid):
        assert interdit not in brut, interdit
    # Les graphiques, eux, font partie du rapport (spec §0).
    assert vue["viz"][0]["empreinte"] == "a" * 64


def test_partage_refuse_un_rapport_sans_contenu(http):
    """Partager une génération en cours publierait une page vide, et le lien
    serait transmis avant que le rapport n'existe."""
    engine, uid = http
    with Session(engine) as db:
        encours = str(_rapport(db, uid, statut=rm.EN_COURS, content="",
                               progression=40).id)
        annule = str(_rapport(db, uid, statut=rm.ANNULE, content="").id)
    client = _client(engine, uid)
    for rid in (encours, annule):
        res = client.post(f"/reports/{rid}/partage")
        assert (res.status_code, res.json()["error"]["code"]) \
            == (409, "rapport_non_partageable"), rid


def test_la_route_publique_nest_pas_authentifiee(http):
    """Le contrat tient dans le schéma : `GET /partage/{jeton}` ne porte AUCUNE
    exigence de sécurité, contrairement à tout le reste des rapports."""
    from fastapi.testclient import TestClient

    from app.main import app

    schema = TestClient(app).get("/openapi.json").json()
    publique = schema["paths"]["/partage/{jeton}"]["get"]
    assert not publique.get("security"), publique.get("security")
    assert schema["paths"]["/reports/{report_id}"]["get"].get("security")
    # Un jeton inexistant, trop long ou vide ne fait pas tomber la route.
    engine, uid = http
    client = _client(engine, uid)
    for jeton in ("inconnu", "x" * 500, "%20"):
        assert client.get(f"/partage/{jeton}").status_code == 404


# --- Images des graphiques (§5.3) -----------------------------------------

def _viz_en_base(db, uid, *, empreinte="b" * 64, partage=False):
    from app.modules.viz.models import VizRendu

    db.add(VizRendu(empreinte=empreinte, vl={"mark": "bar"}))
    r = _rapport(db, uid, title="Étude", statut=rm.TERMINE, content="# Corps",
                 viz=[{"index": 0, "empreinte": empreinte, "vl": {"mark": "bar"},
                       "statut": "ok", "kind": "bar", "spec": {}}])
    if partage:
        r.jeton_partage = "jeton-de-partage-123"
        r.detail = {"partage": {"pseudo": "miradie", "slug": "etude"}}
    db.commit()
    return r


def test_image_viz_exige_une_authentification_ou_un_jeton(http, monkeypatch):
    from app.modules.viz import render

    engine, uid = http
    monkeypatch.setattr(render, "vers_svg", lambda vl: "<svg/>")
    with Session(engine) as db:
        _viz_en_base(db, uid, partage=True)
        # Graphique d'un AUTRE rapport, non partagé : le jeton ne doit pas
        # l'ouvrir — un jeton autorise les images de SON rapport, pas toutes.
        _viz_en_base(db, uuidlib.uuid4(), empreinte="c" * 64)
    client = _client(engine, uid)

    # 1. Authentifié : passe.
    ok = client.get(f"/viz/{'b' * 64}.svg")
    assert ok.status_code == 200
    assert ok.headers["cache-control"] == "private, max-age=3600"
    assert "public" not in ok.headers["cache-control"]

    # 2. Jeton de partage valide, empreinte du rapport partagé : passe.
    _anonyme()
    anonyme = client

    avec = anonyme.get(f"/viz/{'b' * 64}.svg?p=jeton-de-partage-123")
    assert avec.status_code == 200
    assert avec.headers["cache-control"] == "private, max-age=3600"

    # 3. Jeton valide mais empreinte d'un AUTRE rapport : 404.
    assert anonyme.get(
        f"/viz/{'c' * 64}.svg?p=jeton-de-partage-123").status_code == 404
    # 4. Jeton inconnu : 404.
    assert anonyme.get(f"/viz/{'b' * 64}.svg?p=inconnu").status_code == 404
    # 5. Ni authentification ni jeton : 401, et non une image.
    nu = anonyme.get(f"/viz/{'b' * 64}.svg")
    assert nu.status_code == 401
    assert nu.json()["error"]["code"] == "not_authenticated"
    # 6. Empreinte mal formée : 404 sans requête.
    assert anonyme.get("/viz/pas-une-empreinte.svg").status_code == 404


def test_le_png_suit_la_meme_regle_que_le_svg(http, monkeypatch):
    from app.modules.viz import render

    engine, uid = http
    monkeypatch.setattr(render, "vers_png", lambda vl, scale=2.0: b"\x89PNG")
    with Session(engine) as db:
        _viz_en_base(db, uid, partage=True)
    client = _client(engine, uid)
    assert client.get(f"/viz/{'b' * 64}.png").status_code == 200

    _anonyme()
    assert client.get(f"/viz/{'b' * 64}.png").status_code == 401
    assert client.get(
        f"/viz/{'b' * 64}.png?p=jeton-de-partage-123").status_code == 200


def test_le_pdf_et_lemail_nobtiennent_pas_leurs_images_par_http(http):
    """La restriction des images ne doit rien casser ailleurs.

    Le PDF appelle `render.vers_png` en direct (pas de requête HTTP, donc pas
    d'authentification à porter) et l'email de notification est du texte sans
    aucune balise `<img>`. Ce test tomberait le jour où quelqu'un remplacerait
    l'un des deux par une URL `/viz/…`.
    """
    import inspect

    from app.modules.reports import export as exp
    from app.modules.reports import notification, pdf

    for module in (pdf, exp):
        source = inspect.getsource(module)
        assert "vers_png" in source
        assert "/viz/" not in source, f"{module.__name__} passe par HTTP"
    for corps in notification.CORPS.values():
        assert "/viz/" not in corps and "<img" not in corps

    # Et le PDF sort bel et bien, avec un graphique réel, sans jeton.
    engine, uid = http
    with Session(engine) as db:
        r = _rapport(db, uid, title="Étude", statut=rm.TERMINE,
                     content="# Titre\n\n```viz\n"
                             '{"intent":"comparaison","title":"CA","unit":"M€",'
                             '"series":[{"label":"2025","value":3},'
                             '{"label":"2026","value":5}]}\n```\n')
        rid = str(r.id)
    res = _client(engine, uid).get(f"/reports/{rid}/pdf")
    assert res.status_code == 200 and res.content[:5] == b"%PDF-"


# --- Export (§4) -----------------------------------------------------------

_MARKDOWN = """# Étude

Un paragraphe.

## Constats

- Premier point
- Second point

| Année | CA |
| --- | --- |
| 2025 | 3 |
| 2026 | 5 |

### Détail

## Sources

Le modèle a écrit sa propre liste, qui ferait doublon.
"""


def _avec_contenu(db, uid, **kw):
    return _rapport(db, uid, title="Étude", statut=rm.TERMINE,
                    content=_MARKDOWN,
                    sources=[{"title": "INSEE", "url": "https://insee.fr",
                              "domain": "insee.fr", "source": "web"},
                             {"title": "bp.pdf", "source": "documents"}], **kw)


def test_export_markdown_rend_le_contenu_et_une_section_sources(http):
    engine, uid = http
    with Session(engine) as db:
        rid = str(_avec_contenu(db, uid).id)
    res = _client(engine, uid).get(f"/reports/{rid}/export?format=md")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert 'filename="etude.md"' in res.headers["content-disposition"]
    texte = res.text
    # Le contenu n'est pas retouché : c'est le texte exact lu à l'écran.
    assert _MARKDOWN.strip() in texte
    assert "## Sources" in texte
    assert "1. INSEE — insee.fr — https://insee.fr" in texte
    # Un export destiné au propriétaire : ses documents y restent, signalés.
    assert "2. bp.pdf — document interne" in texte


def test_export_docx_reprend_titres_puces_tableaux_et_sources(http):
    engine, uid = http
    with Session(engine) as db:
        rid = str(_avec_contenu(db, uid).id)
    res = _client(engine, uid).get(f"/reports/{rid}/export?format=docx")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml")
    assert 'filename="etude.docx"' in res.headers["content-disposition"]
    # Un `.docx` est un ZIP : la signature le prouve avant de l'ouvrir.
    assert res.content[:2] == b"PK"

    import io as _io

    from docx import Document

    doc = Document(_io.BytesIO(res.content))
    textes = [p.text for p in doc.paragraphs]
    assert "Étude" in textes
    assert "Un paragraphe." in textes
    assert "Constats" in textes and "Détail" in textes
    assert "Premier point" in textes and "Second point" in textes
    styles = {p.text: p.style.name for p in doc.paragraphs}
    assert styles["Premier point"] == "List Bullet"
    assert len(doc.tables) == 1
    grille = [[c.text for c in ligne.cells] for ligne in doc.tables[0].rows]
    assert grille == [["Année", "CA"], ["2025", "3"], ["2026", "5"]]
    # La section « Sources » du modèle est écartée au profit de celle qu'on
    # génère depuis les données — sinon le document en porterait deux.
    assert "Le modèle a écrit sa propre liste, qui ferait doublon." not in textes
    assert any("INSEE" in t for t in textes)


def test_export_pdf_et_son_alias_rendent_le_meme_document(http):
    engine, uid = http
    with Session(engine) as db:
        rid = str(_avec_contenu(db, uid).id)
    client = _client(engine, uid)
    par_format = client.get(f"/reports/{rid}/export?format=pdf")
    alias = client.get(f"/reports/{rid}/pdf")
    assert par_format.status_code == alias.status_code == 200
    for res in (par_format, alias):
        assert res.content[:5] == b"%PDF-"
        assert res.headers["content-type"] == "application/pdf"
    # Le format par défaut est le PDF : `?format=` absent ne casse rien.
    assert client.get(f"/reports/{rid}/export").content[:5] == b"%PDF-"


def test_format_dexport_inconnu_refuse_sans_rien_produire(http):
    engine, uid = http
    with Session(engine) as db:
        rid = str(_avec_contenu(db, uid).id)
    res = _client(engine, uid).get(f"/reports/{rid}/export?format=xlsx")
    assert (res.status_code, res.json()["error"]["code"]) == (400, "format_inconnu")
    assert reports_service.FORMATS_EXPORT == ("pdf", "md", "docx")


def test_export_dun_rapport_dun_autre_compte_rend_404(http):
    engine, uid = http
    with Session(engine) as db:
        rid = str(_avec_contenu(db, uuidlib.uuid4()).id)
    client = _client(engine, uid)
    for chemin in (f"/reports/{rid}/export?format=md", f"/reports/{rid}/pdf",
                   f"/reports/{rid}", f"/reports/{rid}/partage"):
        res = (client.post(chemin) if chemin.endswith("/partage")
               else client.get(chemin))
        assert res.status_code == 404, chemin


# --- Signalement (§3) ------------------------------------------------------

@pytest.fixture
def notif(monkeypatch):
    """Notifications d'erreur actives, envoi SYNCHRONE et observé.

    Le cache de `get_settings` est vidé des deux côtés : le laisser chaud
    laisserait les notifications actives pour les tests suivants.
    """
    from app.config import get_settings
    from app.shared import notifier

    monkeypatch.setenv("ERREURS_NOTIF_ACTIVES", "true")
    get_settings.cache_clear()
    notifier._reinitialiser()
    monkeypatch.setattr(notifier, "ENVOI_SYNCHRONE", True)
    envois: list = []
    monkeypatch.setattr(notifier, "envoyer_brut",
                        lambda *a, **k: envois.append(a) or (True, "id"))
    yield envois
    notifier._reinitialiser()
    get_settings.cache_clear()


def test_signalement_archive_et_envoie_lemail_technique(http, notif):
    from app.modules.reports.feedback import ReportFeedback

    envois = notif
    engine, uid = http
    with Session(engine) as db:
        rid = str(_rapport(db, uid, title="Marché du lithium", statut=rm.DEGRADE,
                           content="corps").id)
    client = _client(engine, uid, email="fondateur@exemple.fr")

    res = client.post(f"/reports/{rid}/feedback",
                      json={"note": 2, "motif": "incomplet",
                            "commentaire": "Il manque les volumes 2026."})
    assert res.status_code == 201
    assert res.json()["motif"] == "incomplet" and res.json()["note"] == 2

    with Session(engine) as db:
        lignes = db.scalars(select(ReportFeedback)).all()
        assert len(lignes) == 1
        assert str(lignes[0].report_id) == rid
        assert str(lignes[0].user_id) == str(uid)
        assert lignes[0].commentaire == "Il manque les volumes 2026."

    assert len(envois) == 1, "l'email technique doit partir"
    corps = "\n".join(str(x) for x in envois[0])
    for attendu in (rid, "Marché du lithium", "fondateur@exemple.fr",
                    "incomplet", "Il manque les volumes 2026.",
                    "Signalement sur un rapport"):
        assert attendu in corps, attendu
    assert "Relire le rapport" in corps


def test_deux_signalements_de_la_meme_heure_envoient_deux_emails(http, notif):
    """Le dédoublonnage de `notifier_erreur` porte sur (route + type
    d'exception) pendant une heure. Sans l'identifiant du signalement dans la
    route, le second avis de la journée serait avalé en silence."""
    envois = notif
    engine, uid = http
    with Session(engine) as db:
        a = str(_rapport(db, uid, title="A", statut=rm.TERMINE, content="c").id)
        b = str(_rapport(db, uid, title="B", statut=rm.TERMINE, content="c").id)
    client = _client(engine, uid)
    for rid in (a, b, a):
        assert client.post(f"/reports/{rid}/feedback",
                           json={"motif": "hors_sujet"}).status_code == 201
    assert len(envois) == 3


def test_motifs_valides_alias_et_refus(http, notif):
    from app.modules.reports.feedback import MOTIFS, ReportFeedback

    engine, uid = http
    with Session(engine) as db:
        rid = str(_rapport(db, uid, statut=rm.TERMINE, content="c").id)
    client = _client(engine, uid)

    for motif in MOTIFS:
        assert client.post(f"/reports/{rid}/feedback",
                           json={"motif": motif}).status_code == 201
    # « faux » est le libellé du formulaire, `contenu_faux` celui de la base.
    assert client.post(f"/reports/{rid}/feedback",
                       json={"motif": "faux"}).json()["motif"] == "contenu_faux"
    res = client.post(f"/reports/{rid}/feedback", json={"motif": "parce_que"})
    assert (res.status_code, res.json()["error"]["code"]) == (400, "motif_inconnu")
    # Note hors bornes : refusée par le schéma, rien n'est écrit.
    assert client.post(f"/reports/{rid}/feedback",
                       json={"motif": "autre", "note": 9}).status_code == 422
    with Session(engine) as db:
        assert len(db.scalars(select(ReportFeedback)).all()) == len(MOTIFS) + 1


def test_un_email_en_panne_nempeche_pas_denregistrer_lavis(http, notif,
                                                           monkeypatch):
    """L'avis de l'utilisateur est la donnée ; l'email n'est qu'une alerte.

    Resend indisponible ne doit pas rendre un 500 au fondateur qui vient de
    signaler un problème — ce serait un second problème à la place du premier.
    """
    from app.modules.reports.feedback import ReportFeedback
    from app.shared import notifier

    engine, uid = http
    monkeypatch.setattr(notifier, "envoyer_brut",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("HS")))
    with Session(engine) as db:
        rid = str(_rapport(db, uid, statut=rm.TERMINE, content="c").id)
    assert _client(engine, uid).post(f"/reports/{rid}/feedback",
                                    json={"motif": "autre"}).status_code == 201
    with Session(engine) as db:
        assert len(db.scalars(select(ReportFeedback)).all()) == 1


def test_signalement_sur_le_rapport_dun_autre_rend_404(http, notif):
    engine, uid = http
    with Session(engine) as db:
        rid = str(_rapport(db, uuidlib.uuid4(), statut=rm.TERMINE, content="c").id)
    assert _client(engine, uid).post(f"/reports/{rid}/feedback",
                                    json={"motif": "autre"}).status_code == 404


# --- `POST /reports` réservé aux administrateurs (§5.2) -------------------

def test_post_reports_est_reserve_aux_administrateurs(http):
    """Depuis Task 2, chaque rapport naît d'une ligne créée par le moteur : le
    seul appelant restant (le repli « sauvegarder avant de livrer » de
    l'éditeur front) est devenu inutile. La route survit pour l'import manuel,
    donc `is_admin`."""
    engine, uid = http
    corps = {"title": "Import manuel", "content": "# Corps",
             "analysis_type": "synthese_executive"}
    refus = _client(engine, uid).post("/reports", json=corps)
    assert (refus.status_code, refus.json()["error"]["code"]) == (403, "forbidden")

    accepte = _client(engine, uid, is_admin=True).post("/reports", json=corps)
    assert accepte.status_code == 200 and accepte.json()["title"] == "Import manuel"


# --- Balayage des orphelins au démarrage ----------------------------------

def test_balayage_range_les_rapports_interrompus_par_un_redemarrage(http):
    """Le thread de génération meurt avec le processus sans ranger sa ligne :
    sans balayage, le rapport reste « en cours » à 62 % pour toujours et le
    front y poll indéfiniment."""
    from app.config import DELAI_MAX_RAPPORT_SECONDES

    engine, uid = http
    maintenant = dt.datetime.now(dt.timezone.utc)
    with Session(engine) as db:
        vieux = _rapport(db, uid, title="Interrompu", statut=rm.EN_COURS,
                         progression=62, etape="redaction",
                         detail={"section": "3/8"},
                         created_at=maintenant - dt.timedelta(
                             seconds=DELAI_MAX_RAPPORT_SECONDES + 60))
        # Une génération encore dans les temps ne doit PAS être rangée : elle
        # tourne peut-être dans un autre worker.
        jeune = _rapport(db, uid, title="En vol", statut=rm.EN_COURS,
                         progression=20, created_at=maintenant)
        fini = _rapport(db, uid, title="Fini", statut=rm.TERMINE, content="c",
                        created_at=maintenant - dt.timedelta(days=3))
        ids = (str(vieux.id), str(jeune.id), str(fini.id))

    with Session(engine) as db:
        assert reports_service.balayer_orphelins(db) == 1
        # Idempotent : un second démarrage ne trouve plus rien.
        assert reports_service.balayer_orphelins(db) == 0

    with Session(engine) as db:
        range_, en_vol, termine = (db.get(Report, uuidlib.UUID(i)) for i in ids)
        assert range_.statut == rm.ECHEC
        assert range_.progression == 100 and range_.termine_at is not None
        assert range_.detail["raison"] == "interrompu_par_redemarrage"
        assert "redémarrage" in range_.detail["message"]
        # Le contexte de l'étape survit : on veut savoir où ça s'est arrêté.
        assert range_.detail["section"] == "3/8"
        assert en_vol.statut == rm.EN_COURS and en_vol.progression == 20
        assert termine.statut == rm.TERMINE


def test_le_demarrage_de_lapi_balaie_les_orphelins(monkeypatch):
    """Le balayage est branché sur le `lifespan` : c'est le seul moment où l'on
    sait qu'aucun thread de génération de CE processus ne tourne encore."""
    from fastapi.testclient import TestClient

    import app.db as app_db
    import app.main as main
    from sqlalchemy.orm import sessionmaker

    engine = _base_http()
    uid = uuidlib.uuid4()
    with Session(engine) as db:
        rid = str(_rapport(
            db, uid, statut=rm.EN_COURS, progression=62,
            created_at=dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(days=1)).id)

    ancienne = app_db.SessionLocal
    app_db.SessionLocal = sessionmaker(bind=engine, future=True)
    try:
        # Le `with` déclenche le lifespan de l'app réelle.
        with TestClient(main.app) as client:
            assert client.get("/health").json()["status"] == "ok"
    finally:
        app_db.SessionLocal = ancienne

    with Session(engine) as db:
        assert db.get(Report, uuidlib.UUID(rid)).statut == rm.ECHEC


def test_le_balayage_ne_bloque_jamais_le_demarrage(monkeypatch):
    """Une base injoignable au démarrage ne doit pas empêcher l'API de monter :
    les routes répondront 503 d'elles-mêmes, avec un message."""
    import app.db as app_db
    import app.main as main

    def _explose():
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(app_db, "SessionLocal", _explose)
    assert main.balayer_rapports_orphelins() == 0


# --- Routes publiées -------------------------------------------------------

def test_routes_de_gestion_des_rapports_montees():
    from fastapi.testclient import TestClient

    from app.main import app

    chemins = TestClient(app).get("/openapi.json").json()["paths"]
    attendus = {
        "/reports": {"get", "post"},
        "/reports/search": {"get"},
        "/reports/{report_id}": {"get", "patch", "delete"},
        "/reports/{report_id}/partage": {"post", "delete"},
        "/reports/{report_id}/feedback": {"post"},
        "/reports/{report_id}/export": {"get"},
        "/reports/{report_id}/pdf": {"get"},
        "/reports/{report_id}/annuler": {"post"},
        "/reports/{report_id}/relancer": {"post"},
        "/partage/{jeton}": {"get"},
        "/viz/{empreinte}.svg": {"get"},
        "/viz/{empreinte}.png": {"get"},
    }
    for chemin, methodes in attendus.items():
        assert chemin in chemins, chemin
        assert methodes <= set(chemins[chemin]), (chemin, chemins[chemin].keys())
    # La liste rend un objet paginé et non un tableau : le front doit lire
    # `items` / `has_more` (Task 4).
    liste = chemins["/reports"]["get"]["responses"]["200"]["content"]
    assert liste["application/json"]["schema"]["$ref"].endswith("ReportPage")
