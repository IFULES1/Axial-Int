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

    def _jamais_appele(**kw):
        generations.append(kw.get("query", ""))
        raise AssertionError("La génération ne doit pas être lancée deux fois")

    with Session(engine) as db1, Session(engine) as db2:
        # Premier appel : marque l'offre, puis on coupe avant la génération.
        import app.modules.analysis.service as service
        from app.modules.memory import service as memory
        monkeypatch.setattr(service, "run_analysis", _jamais_appele)
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
