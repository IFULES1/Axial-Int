"""Conversations v2 — socle backend (Task 1).

Les tests de routage appellent `_prepare_turn` POUR DE VRAI sur SQLite en
mémoire : `personas.route` était déjà couvert unitairement, et il l'était
pendant que le pipeline le court-circuitait. Seul un test qui traverse le
pipeline garde la propriété qui intéresse l'utilisateur — « ma question de
concurrence arrive chez Competitor Radar ».
"""
from __future__ import annotations

import uuid as uuidlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.modules.intelligence.models  # noqa: F401 — enregistre les tables
import app.modules.memory.models  # noqa: F401 — company_profiles (build_context)
from app.db import Base
from app.modules.intelligence import personas
from app.modules.intelligence import service as intel


# --- socle de test ---------------------------------------------------------

def _base():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["projects"],
        Base.metadata.tables["conversations"],
        Base.metadata.tables["messages"],
        Base.metadata.tables["company_profiles"],
    ])
    return engine


def _hors_reseau(monkeypatch, *, compteur_faux=None):
    """Neutralise tout ce qui sortirait de la machine, en laissant le routage,
    l'assemblage du prompt et le comptage de recherche intacts."""
    from app.modules.integrations import notion_context
    from app.shared import search as web_search

    monkeypatch.setattr(intel.llm_client, "generation_available", lambda: True)
    monkeypatch.setattr(intel, "_retrieve_context", lambda *a, **k: ("", []))
    monkeypatch.setattr(intel, "_assemble_sources", lambda *a, **k: ("", []))
    monkeypatch.setattr(notion_context, "passages_pour", lambda *a, **k: [])

    def _recherche(query, top_k=6, compteur=None):
        if compteur is not None and compteur_faux:
            for nom, n in compteur_faux.items():
                compteur[nom] = compteur.get(nom, 0) + n
        return []

    monkeypatch.setattr(web_search, "search", _recherche)


def _tour(db, question: str, agent_override=None):
    uid = str(uuidlib.uuid4())
    projet = intel.create_project(db, uid, "Projet test", None)
    conv = intel.create_conversation(db, uid, str(projet.id), None, None)
    turn = intel._prepare_turn(db, uid, str(conv.id), question, agent_override,
                               is_admin=True, document_ids=None)
    return uid, conv, turn


# --- Step 1 : colonnes -----------------------------------------------------

def test_colonnes_conversations_v2_presentes():
    msg = Base.metadata.tables["messages"].c
    for nom in ("statut", "cle_idempotence", "cout_recherche_micro_eur",
                "appels_recherche"):
        assert nom in msg, f"messages.{nom} manquant"
    assert msg["cle_idempotence"].unique, "cle_idempotence doit être unique"

    conv = Base.metadata.tables["conversations"].c
    for nom in ("resume", "pinned_at", "archived_at"):
        assert nom in conv, f"conversations.{nom} manquant"


def test_defaut_conversation_est_auto():
    """Une conversation créée sans agent laisse le routeur décider."""
    assert personas.DEFAULT_AGENT == personas.AUTO
    engine = _base()
    with Session(engine) as db:
        uid = str(uuidlib.uuid4())
        projet = intel.create_project(db, uid, "P", None)
        assert intel.create_conversation(db, uid, str(projet.id), None,
                                         None).default_agent == personas.AUTO
        # Un choix explicite reste respecté.
        assert intel.create_conversation(db, uid, str(projet.id), None,
                                         "competitor_radar").default_agent == "competitor_radar"


# --- Step 2 : routage réel dans le pipeline --------------------------------

def test_auto_route_macro_vers_market_scanner(monkeypatch):
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        _, _, turn = _tour(db, "Quelles sont les tendances de régulation et "
                               "l'attractivité du marché européen ?")
    assert turn.agent_key == "market_scanner"
    # Un spécialiste retenu par le routeur répond avec son cadre complet.
    assert "AXIAL Recommande" in turn.system
    assert turn.tier == "chat"


def test_auto_route_concurrence_vers_competitor_radar(monkeypatch):
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        _, _, turn = _tour(db, "Qui sont mes concurrents et quel est leur "
                               "positionnement pricing ?")
    assert turn.agent_key == "competitor_radar"
    assert "AXIAL Recommande" in turn.system


def test_auto_generique_vers_conseiller(monkeypatch):
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        _, _, turn = _tour(db, "Bonjour, aide-moi à structurer mon pitch pour "
                               "un premier rendez-vous investisseur.")
    assert turn.agent_key == personas.AXIAL_CONSEIL.key
    # Conversation : ni cadre imposé, ni bloc « AXIAL Recommande ».
    assert "AXIAL Recommande" not in turn.system
    assert personas.REGISTRE_INSTRUCTION in turn.system


def test_choix_explicite_respecte_dans_le_pipeline(monkeypatch):
    """Le sélecteur garde le dernier mot : agent demandé conservé, note de
    redirection quand la question relève nettement de l'autre spécialiste."""
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        _, _, turn = _tour(db, "Analyse la rivalité concurrentielle et les "
                               "barrières à l'entrée de mes concurrents",
                           agent_override="market_scanner")
    assert turn.agent_key == "market_scanner"
    assert turn.redirect_note and "Competitor Radar" in turn.redirect_note


# --- Step 4 : coût de recherche -------------------------------------------

def test_cout_de_recherche_persiste_sur_le_message(monkeypatch):
    """Deux fournisseurs interrogés = 2 appels, et un coût non nul archivé sur
    la réponse. Sans ça, `metrics` comptait la recherche des conversations à 0
    alors que chaque tour interroge tous les fournisseurs actifs."""
    _hors_reseau(monkeypatch, compteur_faux={"exa": 1, "tavily": 1})
    # Facturation et visualisations ne sont pas le sujet de ce test.
    from app.modules.viz import service as viz_service

    monkeypatch.setattr(viz_service, "preparer_sans_faute", lambda *a, **k: None)

    with Session(_base()) as db:
        uid, _, turn = _tour(db, "Quel est l'état de la concurrence sur le "
                                 "marché du logiciel RH en France ?")
        assert turn.appels_recherche == 2
        assert turn.cout_recherche_micro_eur > 0

        msg = intel._finalize_turn(db, uid, turn, "Réponse.", is_admin=True,
                                   degraded=False)

    assert msg.appels_recherche == 2
    assert msg.cout_recherche_micro_eur == turn.cout_recherche_micro_eur > 0
    assert msg.statut == "complet"


def test_message_trivial_ne_cherche_rien(monkeypatch):
    """« merci » ne doit ni chercher ni coûter : un 0 mesuré serait un faux
    positif d'instrumentation, on garde None."""
    _hors_reseau(monkeypatch, compteur_faux={"exa": 1})
    with Session(_base()) as db:
        _, _, turn = _tour(db, "merci")
    assert turn.appels_recherche is None
    assert turn.cout_recherche_micro_eur is None


def test_couts_totaux_lit_la_colonne_des_messages():
    """`couts_totaux` codait en dur `0` pour le poste conversations, faute de
    colonne. La requête est en SQL PostgreSQL (`make_interval`) : on vérifie
    qu'elle n'a plus de cas particulier plutôt que de l'exécuter sur SQLite."""
    import inspect

    from app.modules.metrics import service as metrics

    source = inspect.getsource(metrics.couts_totaux)
    assert "sum(cout_recherche_micro_eur)" in source
    assert "table != 'messages'" not in source


def test_cout_recherche_micro_eur_par_fournisseur():
    from app.modules.billing.couts import cout_recherche_micro_eur

    assert cout_recherche_micro_eur({"exa": 1, "tavily": 1}) == 4_600 + 7_400
    assert cout_recherche_micro_eur({}) == 0
    assert cout_recherche_micro_eur(None) == 0


# --- Step 5 : dette simple -------------------------------------------------

def test_export_utilise_les_titres_generiques_du_service():
    from app.modules.intelligence import export

    assert export.TITRES_GENERIQUES is intel.TITRES_GENERIQUES
    assert not hasattr(export, "_TITRES_PAR_DEFAUT"), (
        "la copie locale des titres par défaut est de retour")
    # Les valeurs que seul l'export connaissait sont dans la constante unique.
    for titre in ("nouvelle analyse", "new analysis", "workspace"):
        assert titre in intel.TITRES_GENERIQUES

    messages = [{"role": "user", "content": "Combien coûte un CDI en Espagne ?"}]
    assert export._titre_utile("Nouvelle analyse", messages).startswith("Combien")
    assert export._titre_utile("Coût d'un CDI en Espagne", messages) == \
        "Coût d'un CDI en Espagne"


def test_cache_notion_borne():
    from app.modules.integrations import notion_context as nc

    assert nc.CACHE_SECONDES == 600
    assert nc.CACHE_ENTREES_MAX == 200
    nc._cache.clear()
    try:
        # 250 comptes vus il y a longtemps : le cache ne doit pas les garder.
        for i in range(250):
            nc._cache[f"vieux-{i}"] = (0.0, [])
        nc._ranger_cache("frais", ["corpus"], 10_000.0)
        assert len(nc._cache) <= nc.CACHE_ENTREES_MAX
        assert nc._cache["frais"] == (10_000.0, ["corpus"])
    finally:
        nc._cache.clear()


def test_recompter_recale_message_count():
    """`message_count` était incrémenté de 2 par tour et jamais corrigé."""
    with Session(_base()) as db:
        uid = str(uuidlib.uuid4())
        projet = intel.create_project(db, uid, "P", None)
        conv = intel.create_conversation(db, uid, str(projet.id), None, None)
        conv.message_count = 42  # compteur devenu faux
        for role in ("user", "assistant", "user"):
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role=role, content="x"))
        db.commit()
        assert intel._recompter(db, conv) == 3
        assert conv.message_count == 3


# --- Step 3 : /agents authentifié, /agents/route supprimé -----------------

def test_agents_authentifie_et_route_supprimee():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/intelligence/agents/route" not in paths
    assert "/intelligence/agents" in paths
    assert client.get("/intelligence/agents").status_code in (401, 403)


def test_route_in_supprime():
    from app.modules.intelligence import router as intel_router

    assert not hasattr(intel_router, "RouteIn")


@pytest.mark.parametrize("statut", ["complet", "partiel", "degrade"])
def test_statut_accepte_les_trois_valeurs(statut):
    """La colonne existe pour Task 4 ; ici on vérifie seulement qu'elle
    accepte le vocabulaire de la spec et vaut `complet` par défaut."""
    with Session(_base()) as db:
        uid = str(uuidlib.uuid4())
        projet = intel.create_project(db, uid, "P", None)
        conv = intel.create_conversation(db, uid, str(projet.id), None, None)
        m = intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                          role="assistant", content="x", statut=statut)
        db.add(m)
        defaut = intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                               role="assistant", content="y")
        db.add(defaut)
        db.commit()
        assert m.statut == statut
        assert defaut.statut == "complet"
