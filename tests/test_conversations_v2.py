"""Conversations v2 — socle backend (Task 1).

Les tests de routage appellent `_prepare_turn` POUR DE VRAI sur SQLite en
mémoire : `personas.route` était déjà couvert unitairement, et il l'était
pendant que le pipeline le court-circuitait. Seul un test qui traverse le
pipeline garde la propriété qui intéresse l'utilisateur — « ma question de
concurrence arrive chez Competitor Radar ».
"""
from __future__ import annotations

import sys
import uuid as uuidlib

import pytest
from sqlalchemy import UniqueConstraint, create_engine, func, select
from sqlalchemy.pool import StaticPool
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
    # Unicité COMPOSITE : une clé dérivée d'autre chose qu'un uuid (hash du
    # message, compteur de composer) est réutilisable d'un fil à l'autre, et
    # une unicité globale y répondait par un IntegrityError 500.
    contraintes = {tuple(c.columns.keys())
                   for c in Base.metadata.tables["messages"].constraints
                   if isinstance(c, UniqueConstraint)}
    assert ("conversation_id", "cle_idempotence") in contraintes
    assert not msg["cle_idempotence"].unique, "l'unicité globale est levée"

    conv = Base.metadata.tables["conversations"].c
    for nom in ("resume", "resume_messages", "pinned_at", "archived_at"):
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

        msg = intel._finalize_turn(db, uid, turn, "Réponse.", is_admin=True)

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

    source = inspect.getsource(metrics._poste)
    assert "sum(COALESCE(cout_recherche_micro_eur, 0))" in source
    assert "table != 'messages'" not in inspect.getsource(metrics.couts_totaux)


def test_couts_totaux_tolere_un_schema_en_retard(monkeypatch):
    """Finding 4 — le backend peut démarrer AVANT `alembic upgrade head`. Le
    poste se lit alors sans son coût de recherche, plutôt que de rendre tout
    `/metrics/tableau` en 500."""
    from app.modules.metrics import service as metrics

    class _DB:
        def __init__(self):
            self.requetes, self.rollbacks = [], 0

        def execute(self, requete, params):
            sql = str(requete)
            self.requetes.append(sql)
            if "cout_recherche_micro_eur" in sql:
                raise RuntimeError('column "cout_recherche_micro_eur" does not exist')

            class _R:
                def mappings(self_inner):
                    return self_inner

                def first(self_inner):
                    return {"lignes": 3, "mesurees": 2, "modele_micro": 120,
                            "recherche_micro": 0}

            return _R()

        def rollback(self):
            self.rollbacks += 1

    db = _DB()
    poste = metrics._poste(db, "messages", 30)
    assert poste["recherche_micro"] == 0
    assert poste["lignes"] == 3
    # La transaction avortée est rembobinée avant la seconde requête, sinon
    # PostgreSQL refuse tout jusqu'au `ROLLBACK`.
    assert db.rollbacks == 1 and len(db.requetes) == 2


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


# ==========================================================================
# Task 2 — pipeline de message : mémoire de fil, flux par étapes, statuts,
# idempotence, coût exposé.
# ==========================================================================

import datetime as dt  # noqa: E402
import json  # noqa: E402

import jwt  # noqa: E402

from app.errors import AppError  # noqa: E402
from app.shared.llm_client.base import LLMResult  # noqa: E402


def _base_complete(*, partagee: bool = False):
    """Même socle, plus les tables de facturation : les tests de flux passent
    par `consume_credits`, et un solde inexistant lèverait avant l'archivage.

    `partagee` : une seule connexion pour tout le monde (`StaticPool`), pour
    les tests qui passent par un client HTTP — il ouvre sa propre connexion.
    """
    import app.modules.billing.models  # noqa: F401

    extra = ({"poolclass": StaticPool,
              "connect_args": {"check_same_thread": False}} if partagee else {})
    engine = create_engine("sqlite://", future=True, **extra)
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["projects"],
        Base.metadata.tables["conversations"],
        Base.metadata.tables["messages"],
        Base.metadata.tables["company_profiles"],
        Base.metadata.tables["credit_balances"],
        Base.metadata.tables["credit_events"],
    ])
    return engine


def _socle_partage(monkeypatch):
    """Engine partagé, `app.db.SessionLocal` pointé dessus.

    L'archivage d'une réponse interrompue ouvre SA session (finding 1) : sans
    ce branchement, elle viserait une autre base SQLite en mémoire.
    """
    from sqlalchemy.orm import sessionmaker

    import app.db as app_db

    engine = _base_complete(partagee=True)
    monkeypatch.setattr(app_db, "SessionLocal",
                        sessionmaker(bind=engine, autoflush=False, future=True))
    return engine


def _fil(db):
    """Un utilisateur, un projet, une conversation vides."""
    uid = str(uuidlib.uuid4())
    projet = intel.create_project(db, uid, "Projet test", None)
    conv = intel.create_conversation(db, uid, str(projet.id), None, None)
    return uid, conv


def _remplir(db, conv, paires: int, *, reponse=None):
    """`paires` tours user/assistant horodatés, du plus ancien au plus récent."""
    base = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
    for i in range(paires):
        for décalage, role, texte in (
            (0, "user", f"Question {i}"),
            (1, "assistant", reponse(i) if reponse else f"Réponse {i}"),
        ):
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role=role, content=texte,
                                 created_at=base + dt.timedelta(minutes=2 * i + décalage)))
    conv.message_count = 2 * paires
    db.commit()


def _sans_effets(monkeypatch, *, contexte="", solde=42):
    """Neutralise facturation, analytics, visualisations et solde — ce que ces
    tests observent, c'est le pipeline, pas ses dépendances."""
    from app.modules.analytics import client as analytics
    from app.modules.billing import service as billing
    from app.modules.memory import service as memory
    from app.modules.viz import service as viz_service

    debits: list[dict] = []
    monkeypatch.setattr(billing, "consume_credits",
                        lambda db, uid, action, *, is_admin=False:
                        (debits.append({"action": action}), {"charged": 2})[1])
    monkeypatch.setattr(billing, "check_credits",
                        lambda *a, **k: {"affordable": True, "available": 99, "cost": 2})
    monkeypatch.setattr(analytics, "increment_usage", lambda *a, **k: None)
    monkeypatch.setattr(viz_service, "preparer_sans_faute", lambda *a, **k: None)
    monkeypatch.setattr(memory, "build_context", lambda *a, **k: contexte)
    monkeypatch.setattr(intel, "_solde", lambda *a, **k: solde)
    return debits


def _stub_flux(monkeypatch, sequences):
    """`stream_text` simulé : une entrée `(morceaux, stop_reason)` par appel.

    La valeur de retour du générateur EST le `stop_reason` — c'est le contrat
    que Task 2 ajoute à `llm_client.stream_text`, et ce que la reprise lit.
    """
    suite = iter(sequences)
    appels: list[dict] = []

    def _stream_text(*, system, prompt, tier="chat", max_tokens=0, history=None,
                     mesure=None, **kw):
        morceaux, raison = next(suite)
        appels.append({"system": system, "prompt": prompt, "tier": tier,
                       "history": [dict(h) for h in (history or [])]})
        if mesure is not None:
            # Ce que fait un vrai fournisseur : il cumule sa consommation.
            from app.shared.llm_client.base import cumuler_mesure

            cumuler_mesure(mesure, "gemini-flash-test", "gemini", 100, 40)

        def _gen():
            yield from morceaux
            return raison

        return _gen()

    monkeypatch.setattr(intel.llm_client, "stream_text", _stream_text)
    return appels


def _evenements(generateur) -> list[dict]:
    return [json.loads(bloc[len("data: "):]) for bloc in generateur]


# --- Step 1 : mémoire de fil ----------------------------------------------

def test_historique_8_derniers_messages_envoyes(monkeypatch):
    """Le modèle reçoit les 8 derniers messages — pas 6, pas tout le fil — et
    JAMAIS la question courante (elle est déjà le prompt)."""
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 6)  # 12 messages
        turn = intel._prepare_turn(db, uid, str(conv.id), "Et pour l'Allemagne ?",
                                   None, is_admin=True, document_ids=None)

    assert len(turn.history) == intel.HISTORIQUE_MESSAGES
    # Les 8 derniers = paires 2 à 5.
    assert turn.history[0] == {"role": "user", "content": "Question 2"}
    assert turn.history[-1] == {"role": "assistant", "content": "Réponse 5"}
    # Alternance stricte, commence par l'utilisateur, finit par l'assistant :
    # c'est ce que l'API de Claude exige.
    assert [h["role"] for h in turn.history] == ["user", "assistant"] * 4
    assert "Et pour l'Allemagne" not in json.dumps(turn.history)


def test_historique_tronque_a_1500_caracteres(monkeypatch):
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 1, reponse=lambda i: "x" * 5000)
        turn = intel._prepare_turn(db, uid, str(conv.id), "Suite ?", None,
                                   is_admin=True, document_ids=None)
    assert len(turn.history[-1]["content"]) == intel.HISTORIQUE_CARACTERES


def test_viz_retire_de_l_historique(monkeypatch):
    """Un bloc ```viz est une consigne de rendu et `> ℹ️` une note d'interface :
    les renvoyer au modèle l'incite à les recopier."""
    _hors_reseau(monkeypatch)
    reponse = ("> ℹ️ Cette question relève de Competitor Radar.\n\n"
               "Voici la répartition.\n\n```viz\n{\"type\": \"bar\"}\n```\n\nConclusion.")
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 1, reponse=lambda i: reponse)
        turn = intel._prepare_turn(db, uid, str(conv.id), "Suite ?", None,
                                   is_admin=True, document_ids=None)
    texte = turn.history[-1]["content"]
    assert "```viz" not in texte and "bar" not in texte
    assert "ℹ️" not in texte
    assert "Voici la répartition." in texte and "Conclusion." in texte


def test_historique_desalign_e_reste_acceptable(monkeypatch):
    """Un fil réel n'alterne pas toujours (génération échouée, message
    supprimé) : l'historique doit rester conforme plutôt que faire échouer
    tout le tour côté API."""
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        uid, conv = _fil(db)
        base = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        for i, role in enumerate(("assistant", "user", "user", "assistant", "user")):
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role=role, content=f"m{i}",
                                 created_at=base + dt.timedelta(minutes=i)))
        conv.message_count = 5
        db.commit()
        turn = intel._prepare_turn(db, uid, str(conv.id), "Suite ?", None,
                                   is_admin=True, document_ids=None)
    roles = [h["role"] for h in turn.history]
    assert roles and roles[0] == "user" and roles[-1] == "assistant"
    assert all(a != b for a, b in zip(roles, roles[1:]))


def test_resume_injecte_au_dela_de_8(monkeypatch):
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 6)
        conv.resume = "L'utilisateur dirige une PME de logistique à Lyon."
        db.commit()
        turn = intel._prepare_turn(db, uid, str(conv.id), "Et ensuite ?", None,
                                   is_admin=True, document_ids=None)
    assert turn.prompt.startswith("Résumé de la conversation jusqu'ici :\n")
    assert "PME de logistique à Lyon" in turn.prompt
    assert turn.prompt.endswith("Question: Et ensuite ?")


def test_history_transmis_aux_deux_fournisseurs():
    """`history` doit arriver chez Claude (`messages`) et Gemini (`contents`)
    sans que l'appelant ait à connaître leurs formats."""
    from app.shared.llm_client import claude, gemini

    hist = [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "R1"}]
    assert claude._messages(hist, "Q2") == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "R1"},
        {"role": "user", "content": "Q2"},
    ]
    assert gemini._contents(hist, "Q2") == [
        {"role": "user", "parts": [{"text": "Q1"}]},
        {"role": "model", "parts": [{"text": "R1"}]},
        {"role": "user", "parts": [{"text": "Q2"}]},
    ]
    # Sans historique, la requête est exactement celle d'avant Task 2.
    assert claude._messages(None, "Q") == [{"role": "user", "content": "Q"}]
    assert gemini._contents(None, "Q") == [{"role": "user", "parts": [{"text": "Q"}]}]


# --- Step 2 : résumé roulant ----------------------------------------------

def test_resume_roulant_resume_les_messages_sortis_de_la_fenetre(monkeypatch):
    with Session(_base()) as db:
        uid, conv = _fil(db)
        del uid
        _remplir(db, conv, 6)  # 12 messages → 4 sortent de la fenêtre
        vus: list[str] = []

        def _generate(*, system, prompt, tier="chat", max_tokens=0, history=None):
            vus.append(prompt)
            return LLMResult(text="L'utilisateur cherche un marché.",
                             model="m", provider="p")

        monkeypatch.setattr(intel.llm_client, "generate", _generate)
        intel._mettre_a_jour_resume(db, conv)

        assert conv.resume == "L'utilisateur cherche un marché."
        assert len(vus) == 1
        # Seuls les messages 0..N-8 sont résumés : les 8 derniers sont déjà
        # envoyés en clair, les résumer serait payer deux fois la même
        # information.
        assert "Question 0" in vus[0] and "Question 1" in vus[0]
        assert "Question 2" not in vus[0]


def test_resume_roulant_ignore_les_fils_courts(monkeypatch):
    with Session(_base()) as db:
        _, conv = _fil(db)
        _remplir(db, conv, 3)  # 6 messages
        monkeypatch.setattr(intel.llm_client, "generate",
                            lambda **k: pytest.fail("le modèle ne doit pas être appelé"))
        intel._mettre_a_jour_resume(db, conv)
    assert conv.resume is None


def test_resume_roulant_absorbe_les_echecs(monkeypatch):
    """Un résumé raté dégrade la mémoire longue ; il ne casse pas le tour."""
    with Session(_base()) as db:
        _, conv = _fil(db)
        _remplir(db, conv, 6)

        def _boom(**kwargs):
            raise RuntimeError("503")

        monkeypatch.setattr(intel.llm_client, "generate", _boom)
        intel._mettre_a_jour_resume(db, conv)  # ne lève pas
    assert conv.resume is None


def test_resume_borne_a_600_mots(monkeypatch):
    with Session(_base()) as db:
        _, conv = _fil(db)
        _remplir(db, conv, 6)
        monkeypatch.setattr(intel.llm_client, "generate",
                            lambda **k: LLMResult(text=" ".join(["mot"] * 900),
                                                  model="m", provider="p"))
        intel._mettre_a_jour_resume(db, conv)
        assert len(conv.resume.split(" ")) == intel.RESUME_MOTS_MAX
        # L'ellipse dit que le résumé a été coupé, elle n'est pas un mot.
        assert conv.resume.endswith("…")


# --- Step 3 : étapes et avertissements ------------------------------------

def test_ordre_des_evenements_du_flux(monkeypatch):
    """Ce que l'utilisateur voit : « Recherche web… » → « N sources lues » →
    « Rédaction… » → le texte → le payload final. Dans cet ordre."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="Contexte entreprise (mémoire)\nACME")
    _stub_flux(monkeypatch, [(["Bonjour ", "le monde."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id),
            "Quelles sont les tendances de régulation du marché européen des "
            "logiciels RH et leur impact sur mon positionnement ?",
            is_admin=False))

    etiquettes = [(e["step"], e.get("etape")) for e in evts]
    assert etiquettes[:3] == [("etape", "recherche"), ("etape", "sources"),
                              ("sources", None)]
    assert etiquettes[3] == ("etape", "redaction")
    assert [e for e in etiquettes[4:-1]] == [("delta", None), ("delta", None)]
    assert etiquettes[-1] == ("done", None)
    # Contexte entreprise présent : pas d'avertissement.
    assert not [e for e in evts if e["step"] == "avertissement"]
    assert evts[1]["detail"] == {"nombre": 0}
    assert "fournisseurs" in evts[0]["detail"]


def test_avertissement_contexte_absent(monkeypatch):
    """Profil entreprise vide : le dire AVANT la réponse, pas la laisser
    paraître décevante."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="")
    _stub_flux(monkeypatch, [(["Texte."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id),
            "Comment structurer mon plan de recrutement pour 2027 ?",
            is_admin=False))

    assert evts[0] == {"step": "avertissement", "code": "contexte_absent"}


def test_message_trivial_n_annonce_pas_de_recherche(monkeypatch):
    """« merci » ne cherche rien : annoncer « Recherche web… » serait faux."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Avec plaisir."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        evts = _evenements(intel.stream_message(db, uid, str(conv.id), "merci",
                                                is_admin=False))
    etapes = [e.get("etape") for e in evts if e["step"] == "etape"]
    assert etapes == ["sources", "redaction"]


# --- Step 4 : statut partiel + Stop ---------------------------------------

def test_enveloppe_du_routeur_archive_a_la_deconnexion(monkeypatch):
    """La déconnexion passe par l'enveloppe ASYNC du routeur — le seul chemin
    de production. Le client lit deux morceaux puis part ; Starlette ferme le
    générateur async, dont le `finally` ferme le générateur du service, ce qui
    y lève `GeneratorExit` alors que la session de la requête vit encore.

    Le sondage `request.is_disconnected()` a été retiré : il lisait le même
    `receive` que la tâche `listen_for_disconnect` de Starlette (course non
    déterministe) et son `GeneratorExit` n'arrivait qu'au ramasse-miettes,
    après la fermeture de la session.
    """
    import asyncio

    from app.modules.intelligence import router as intel_router

    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [([f"mot{i} " for i in range(40)], "end_turn")])

    # `partagee` : le générateur du service est itéré dans un thread du pool.
    engine = _socle_partage(monkeypatch)
    with Session(engine) as db:
        uid, conv = _fil(db)
        # `cid` retenu AVANT le flux : le générateur referme la session en
        # sortant (elle n'appartient plus à personne d'autre), donc `conv` en
        # ressort détaché — l'appelant de production ne le relit jamais.
        cid = conv.id
        generateur = intel.stream_message(
            db, uid, str(cid), "Analyse détaillée du marché du logiciel RH",
            is_admin=False, cle_idempotence="cle-coupee")
        flux = intel_router._flux_sse(generateur)

        async def _lire_deux_puis_partir():
            deltas = 0
            async for bloc in flux:
                if '"delta"' in bloc:
                    deltas += 1
                    if deltas == 2:
                        break
            # ORDRE DE PRODUCTION, mesuré (finding 1) : uvicorn annule le
            # scope, `get_db` ferme la session, et le générateur n'est fermé
            # QU'ENSUITE. On ferme donc la session AVANT `aclose()`.
            db.close()
            await flux.aclose()

        asyncio.run(_lire_deux_puis_partir())

    # Lecture dans une session neuve : celle de la requête est morte, comme en
    # production. Ce qui est asserté est donc bien ce qui est EN BASE.
    with Session(engine) as db:
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == cid,
            intel.Message.role == "assistant")).one()
        assert reponse.statut == "partiel"
        assert reponse.content.startswith("mot0")
        assert reponse.content.endswith(intel.NOTE_INTERROMPUE)
        assert "mot39" not in reponse.content
        assert debits == [], "un flux coupé a été facturé"
        # Le fil reste cohérent : la question ET la réponse partielle sont là.
        conv = db.get(intel.Conversation, cid)
        assert conv.message_count == 2
        assert db.scalar(select(func.count()).select_from(intel.Message)
                         .where(intel.Message.conversation_id == cid)) == 2
        assert db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == cid,
            intel.Message.role == "user")).one().content.startswith("Analyse")
        # Rien n'est absorbé par l'idempotence : la même clé doit pouvoir
        # redonner une réponse complète (finding 3).
        assert reponse.cle_idempotence is None


def test_flux_survit_a_la_deconnexion_du_client(monkeypatch):
    """Le navigateur part pendant la rédaction et FastAPI FERME le générateur,
    sans attendre le prochain test de déconnexion. Le texte déjà écrit doit
    être en base, pas perdu — c'est ce qui avait coûté un rapport le 25/08.
    """
    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [([f"mot{i} " for i in range(40)], "end_turn")])

    engine = _socle_partage(monkeypatch)
    with Session(engine) as db:
        uid, conv = _fil(db)
        cid = conv.id
        flux = intel.stream_message(db, uid, str(cid),
                                    "Analyse détaillée du marché du logiciel RH",
                                    is_admin=False)
        # On avance jusqu'en pleine rédaction, puis on coupe comme FastAPI.
        deltas = 0
        for bloc in flux:
            if '"delta"' in bloc:
                deltas += 1
                if deltas == 3:
                    break
        # La session de la requête est FERMÉE avant la fermeture du générateur :
        # c'est l'ordre de production (finding 1). L'archivage ne doit plus
        # rien lui devoir.
        db.close()
        flux.close()

    with Session(engine) as db:
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == cid,
            intel.Message.role == "assistant")).one()
        assert reponse.statut == "partiel"
        assert reponse.content.startswith("mot0")
        assert reponse.content.endswith(intel.NOTE_INTERROMPUE)
        # Rien n'a été écrit après la coupure : le modèle n'a pas fini.
        assert "mot39" not in reponse.content
        assert debits == [], "un flux coupé a été facturé"


def test_flux_coupe_par_le_fournisseur_est_partiel(monkeypatch):
    """Une exception APRÈS le premier morceau : réponse partielle conservée,
    non facturée — pas un tour dégradé sans texte."""
    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")

    def _stream_text(**kwargs):
        def _gen():
            yield "Début de réponse. "
            raise RuntimeError("connexion coupée")

        return _gen()

    monkeypatch.setattr(intel.llm_client, "stream_text", _stream_text)

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        cid = conv.id
        evts = _evenements(intel.stream_message(
            db, uid, str(cid), "Analyse du marché du logiciel RH en France",
            is_admin=False))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == cid,
            intel.Message.role == "assistant")).one()

    assert reponse.statut == "partiel"
    assert "Début de réponse." in reponse.content
    assert debits == []
    assert evts[-1]["data"]["statut"] == "partiel"


def test_tour_degrade_non_facture_et_signale(monkeypatch):
    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")

    def _stream_text(**kwargs):
        raise RuntimeError("503")

    monkeypatch.setattr(intel.llm_client, "stream_text", _stream_text)

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        cid = conv.id
        evts = _evenements(intel.stream_message(
            db, uid, str(cid), "Analyse du marché du logiciel RH en France",
            is_admin=False))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == cid,
            intel.Message.role == "assistant")).one()

    assert reponse.statut == "degrade"
    assert debits == []
    assert evts[-1]["degraded"] is True
    assert evts[-1]["data"]["credits"] == 0


# --- Step 5 : reprise sur troncature en flux ------------------------------

def test_reprise_sur_troncature_en_flux(monkeypatch):
    """`stop_reason == max_tokens` : le flux reste ouvert et le modèle continue
    là où il s'est arrêté. Le lecteur voit un texte continu."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    appels = _stub_flux(monkeypatch, [
        (["Première partie, coupée au milieu du m"], "max_tokens"),
        (["ot puis la suite."], "end_turn"),
    ])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse détaillée du marché du logiciel RH",
            is_admin=False))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == conv.id,
            intel.Message.role == "assistant")).one()

    assert len(appels) == 2
    assert appels[1]["prompt"] == intel.SUITE_FLUX_CONSIGNE
    # La reprise rend au modèle ce qu'il a écrit, en tour assistant.
    assert appels[1]["history"][-1] == {
        "role": "assistant",
        "content": "Première partie, coupée au milieu du m"}
    assert appels[1]["history"][-2]["role"] == "user"
    assert reponse.content == "Première partie, coupée au milieu du mot puis la suite."
    assert reponse.statut == "complet"
    assert len([e for e in evts if e["step"] == "delta"]) == 2


def test_reprise_limitee_a_deux(monkeypatch):
    """Un modèle qui renvoie éternellement `max_tokens` ne doit pas boucler."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    appels = _stub_flux(monkeypatch, [(["morceau. "], "max_tokens")] * 5)

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        list(intel.stream_message(db, uid, str(conv.id),
                                  "Analyse détaillée du marché du logiciel RH",
                                  is_admin=False))
    assert len(appels) == intel.REPRISES_FLUX_MAX + 1


def test_stop_reason_remonte_du_flux_gemini(monkeypatch):
    """`gemini.stream` doit RENDRE son `finishReason` normalisé : sans lui, le
    service ne peut pas reprendre une réponse coupée."""
    import types

    from app.shared.llm_client import gemini

    lignes = [
        'data: {"candidates":[{"content":{"parts":[{"text":"Bonjour"}]}}]}',
        'data: {"candidates":[{"content":{"parts":[{"text":" monde"}]},'
        '"finishReason":"MAX_TOKENS"}]}',
    ]

    class _Reponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter(lignes)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(gemini, "get_settings",
                        lambda: types.SimpleNamespace(gemini_api_key="k",
                                                      llm_chat_model="gemini-flash"))
    monkeypatch.setattr(gemini.httpx, "stream", lambda *a, **k: _Reponse())

    morceaux = []
    flux = gemini.stream(system="s", prompt="p")
    while True:
        try:
            morceaux.append(next(flux))
        except StopIteration as fin:
            raison = fin.value
            break
    assert morceaux == ["Bonjour", " monde"]
    assert raison == "max_tokens"


def test_stream_text_relaie_le_stop_reason(monkeypatch):
    """La façade doit transmettre la valeur de retour du fournisseur, sinon la
    reprise du service ne voit jamais `max_tokens`."""
    from app.shared.llm_client import claude, gemini

    def _stream(**kwargs):
        def _gen():
            yield "a"
            return "max_tokens"

        return _gen()

    monkeypatch.setattr(gemini, "available", lambda: True)
    monkeypatch.setattr(gemini, "stream", _stream)
    monkeypatch.setattr(claude, "available", lambda: False)

    flux = intel.llm_client.stream_text(system="s", prompt="p", tier="chat")
    assert next(flux) == "a"
    try:
        next(flux)
        raise AssertionError("le flux devait être terminé")
    except StopIteration as fin:
        assert fin.value == "max_tokens"


# --- Step 6 : idempotence -------------------------------------------------

def test_idempotence_un_seul_debit_et_un_seul_tour(monkeypatch):
    """Le frontend renvoie la même clé après une coupure réseau : le rejeu
    rend le message déjà produit, sans second débit ni tour en double."""
    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Réponse unique."], "end_turn"),
                             (["NE DOIT PAS ÊTRE APPELÉ"], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        question = "Analyse du marché du logiciel RH en France"
        premier = _evenements(intel.stream_message(
            db, uid, str(conv.id), question, is_admin=False,
            cle_idempotence="cle-abc"))
        second = _evenements(intel.stream_message(
            db, uid, str(conv.id), question, is_admin=False,
            cle_idempotence="cle-abc"))
        messages = list(db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == conv.id)))

    assert len(debits) == 1, "la même clé a été facturée deux fois"
    assert len(messages) == 2, "le tour a été enregistré deux fois"
    assert [e["step"] for e in second] == ["done"]
    assert second[0]["rejeu"] is True
    assert second[0]["data"]["id"] == premier[-1]["data"]["id"]
    assert second[0]["data"]["content"] == "Réponse unique."


def test_idempotence_sur_la_route_bloquante(monkeypatch):
    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")
    monkeypatch.setattr(intel.llm_client, "generate",
                        lambda **k: LLMResult(text="Une seule fois.", model="m",
                                              provider="p"))

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        a = intel.post_message(db, uid, str(conv.id), "Analyse du marché RH",
                               cle_idempotence="cle-xyz")
        b = intel.post_message(db, uid, str(conv.id), "Analyse du marché RH",
                               cle_idempotence="cle-xyz")
        assert a.id == b.id
        assert len(debits) == 1
        assert db.scalar(select(func.count()).select_from(intel.Message)
                         .where(intel.Message.conversation_id == conv.id)) == 2


def test_cle_idempotence_stockee_sur_la_reponse(monkeypatch):
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Texte."], "end_turn")])
    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        list(intel.stream_message(db, uid, str(conv.id), "Analyse du marché RH",
                                  is_admin=False, cle_idempotence="k1"))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant")).one()
        assert reponse.cle_idempotence == "k1"


# --- Step 7 : taille, solde, coût, pagination -----------------------------

def test_message_trop_long_est_un_413_nomme():
    intel.verifier_longueur("x" * intel.LONGUEUR_MAX_MESSAGE)  # la limite passe
    with pytest.raises(AppError) as e:
        intel.verifier_longueur("x" * (intel.LONGUEUR_MAX_MESSAGE + 1))
    assert e.value.status_code == 413
    assert e.value.code == "message_trop_long"
    assert intel.LONGUEUR_MAX_MESSAGE == 6000


def test_solde_et_statut_dans_le_payload_final(monkeypatch):
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME", solde=17)
    _stub_flux(monkeypatch, [(["Texte."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse du marché du logiciel RH",
            is_admin=False))
    data = evts[-1]["data"]
    assert data["balance"] == 17
    assert data["statut"] == "complet"
    assert data["credits"] == 2


def test_cout_micro_eur_reserve_aux_admins(monkeypatch):
    """Le coût réel est une donnée de marge : jamais dans la réponse d'un
    client, même si la colonne est renseignée."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        msg = intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                            role="assistant", content="x", cout_micro_eur=1234,
                            tokens_entree=100, tokens_sortie=200)
        db.add(msg)
        db.commit()

        from app.modules.intelligence import router as intel_router

        assert intel_router._msg_out(msg, is_admin=True).cout_micro_eur == 1234
        assert intel_router._msg_out(msg, is_admin=False).cout_micro_eur is None
        assert intel_router._msg_out(msg).credits == 2

        assert intel.cout_conversation(db, uid, str(conv.id),
                                       is_admin=True)["cout_micro_eur"] == 1234
        assert intel.cout_conversation(db, uid, str(conv.id),
                                       is_admin=False)["cout_micro_eur"] is None


def test_cout_conversation_totalise_le_fil():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        lignes = [
            ("complet", 100, 200, 10, 5),
            ("complet", 50, 60, 7, 0),
            ("partiel", 30, 40, 3, 0),   # non facturé
            ("degrade", 0, 0, 0, 0),     # non facturé
        ]
        for statut, e, s, modele, recherche in lignes:
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role="assistant", content="x", statut=statut,
                                 tokens_entree=e, tokens_sortie=s,
                                 cout_micro_eur=modele,
                                 cout_recherche_micro_eur=recherche))
        db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                             role="user", content="q"))
        db.commit()
        total = intel.cout_conversation(db, uid, str(conv.id), is_admin=True)

    assert total["messages"] == 4          # les réponses, pas les questions
    assert total["credits"] == 4           # 2 tours complets × 2 crédits
    assert total["tokens_entree"] == 180
    assert total["tokens_sortie"] == 300
    assert total["cout_micro_eur"] == 25


def test_messages_pagines():
    """Un fil de 400 messages renvoyait 400 messages à chaque ouverture."""
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 5)  # 10 messages, « Question 0 » … « Réponse 4 »

        derniers, has_more = intel.list_messages(db, uid, str(conv.id), limit=4)
        assert [m.content for m in derniers] == ["Question 3", "Réponse 3",
                                                 "Question 4", "Réponse 4"]
        assert has_more is True

        avant, has_more = intel.list_messages(db, uid, str(conv.id), limit=4,
                                              before=str(derniers[0].id))
        assert [m.content for m in avant] == ["Question 1", "Réponse 1",
                                              "Question 2", "Réponse 2"]
        assert has_more is True

        debut, has_more = intel.list_messages(db, uid, str(conv.id), limit=4,
                                              before=str(avant[0].id))
        assert [m.content for m in debut] == ["Question 0", "Réponse 0"]
        assert has_more is False, "plus rien au-dessus : pas de bouton « précédents »"


def test_messages_pagines_borne_introuvable():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        with pytest.raises(AppError) as e:
            intel.list_messages(db, uid, str(conv.id), before="pas-un-uuid")
        assert e.value.status_code == 404


def test_routes_de_messages_publient_le_nouveau_contrat():
    """413, en-tête d'idempotence, pagination enveloppée et `GET …/cout`
    doivent être visibles dans le schéma : c'est ce que le frontend lit."""
    from fastapi.testclient import TestClient

    from app.main import app

    schema = TestClient(app).get("/openapi.json").json()
    chemins = schema["paths"]
    assert "/intelligence/conversations/{conversation_id}/cout" in chemins

    liste = chemins["/intelligence/conversations/{conversation_id}/messages"]["get"]
    params = {p["name"] for p in liste.get("parameters", [])}
    assert {"limit", "before"} <= params
    reponse = liste["responses"]["200"]["content"]["application/json"]["schema"]
    assert reponse["$ref"].endswith("MessagesPage")

    for chemin in ("/intelligence/conversations/{conversation_id}/messages",
                   "/intelligence/conversations/{conversation_id}/messages/stream"):
        noms = {p["name"] for p in chemins[chemin]["post"].get("parameters", [])}
        assert "x-idempotency-key" in noms, chemin

    props = schema["components"]["schemas"]["MessageOut"]["properties"]
    assert {"statut", "tokens_entree", "tokens_sortie", "credits",
            "cout_micro_eur"} <= set(props)


def test_413_reel_sur_les_deux_routes(monkeypatch):
    """Le 413 doit sortir en HTTP, pas en événement SSE dans une 200 : un
    client qui teste `res.status` doit le voir. `MessageIn` laisse passer la
    longueur (sinon pydantic rendrait 422, que le frontend ne sait pas nommer).
    """
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user

    # `sqlite://` seul rend une base neuve PAR connexion : le client HTTP en
    # ouvre une autre que le test et n'y trouverait aucune table.
    engine = _base_complete(partagee=True)
    uid = str(uuidlib.uuid4())

    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=uid, email="test@axial-ia.fr", is_admin=False)
    try:
        client = TestClient(app)
        with Session(engine) as db:
            projet = intel.create_project(db, uid, "P", None)
            conv = intel.create_conversation(db, uid, str(projet.id), None, None)
            conv_id = str(conv.id)

        trop_long = {"content": "x" * (intel.LONGUEUR_MAX_MESSAGE + 1)}
        for chemin in (f"/intelligence/conversations/{conv_id}/messages",
                       f"/intelligence/conversations/{conv_id}/messages/stream"):
            res = client.post(chemin, json=trop_long)
            assert res.status_code == 413, (chemin, res.status_code, res.text)
            assert res.json()["error"]["code"] == "message_trop_long"

        # Pagination et coût répondent bien sur un fil vide.
        page = client.get(f"/intelligence/conversations/{conv_id}/messages").json()
        assert page == {"items": [], "has_more": False}
        cout = client.get(f"/intelligence/conversations/{conv_id}/cout").json()
        assert cout == {"messages": 0, "credits": 0, "tokens_entree": 0,
                        "tokens_sortie": 0, "cout_micro_eur": None}
    finally:
        app.dependency_overrides.clear()


def test_tokens_et_cout_archives_sur_une_reponse_en_flux(monkeypatch):
    """Le flux est le chemin NORMAL du chat : sans mesure, `MessageOut` et
    `GET …/cout` afficheraient 0 token pour toutes les conversations."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Première partie."], "max_tokens"),
                             ([" Suite."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse détaillée du marché du logiciel RH",
            is_admin=True))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant")).one()

        # Deux appels (reprise) : les tokens des deux sont comptés.
        assert reponse.tokens_entree == 200
        assert reponse.tokens_sortie == 80
        assert reponse.modele == "gemini-flash-test"
        assert reponse.cout_micro_eur is not None
        total = intel.cout_conversation(db, uid, str(conv.id), is_admin=True)
        assert total["tokens_entree"] == 200 and total["tokens_sortie"] == 80

    assert evts[-1]["data"]["tokens_sortie"] == 80


def test_cumul_de_mesure_et_resultat():
    from app.shared.llm_client.base import cumuler_mesure, resultat_de_mesure

    assert resultat_de_mesure(None) is None
    assert resultat_de_mesure({}) is None
    # Un fournisseur muet ne doit pas produire un coût faux.
    assert resultat_de_mesure({"input_tokens": 5}) is None

    mesure: dict = {}
    cumuler_mesure(mesure, "m", "gemini", 10, 3)
    cumuler_mesure(mesure, "m", "gemini", 7, 2)
    res = resultat_de_mesure(mesure)
    assert (res.input_tokens, res.output_tokens, res.tokens) == (17, 5, 22)
    assert res.model == "m" and res.provider == "gemini"



# --- Fix round 1 : garde-fous ---------------------------------------------

def test_historique_retronque_apres_fusion(monkeypatch):
    """Finding 7 — deux messages consécutifs de même rôle sont CONCATÉNÉS par
    `_alterner` ; la limite doit être appliquée après la fusion, sinon une
    entrée d'historique atteint 3 000 caractères ou plus."""
    _hors_reseau(monkeypatch)
    with Session(_base()) as db:
        uid, conv = _fil(db)
        base = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        tours = (("user", "Question"), ("assistant", "a" * 1400),
                 ("assistant", "b" * 1400), ("assistant", "c" * 1400))
        for i, (role, texte) in enumerate(tours):
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role=role, content=texte,
                                 created_at=base + dt.timedelta(minutes=i)))
        conv.message_count = len(tours)
        db.commit()
        turn = intel._prepare_turn(db, uid, str(conv.id), "Suite ?", None,
                                   is_admin=True, document_ids=None)
    assert [h["role"] for h in turn.history] == ["user", "assistant"]
    assert all(len(h["content"]) <= intel.HISTORIQUE_CARACTERES
               for h in turn.history)
    # La fusion a bien eu lieu (trois réponses en une), mais tronquée.
    assert len(turn.history[-1]["content"]) == intel.HISTORIQUE_CARACTERES


def test_resume_roulant_est_incremental(monkeypatch):
    """Finding 2 — le résumé n'intègre que la tranche nouvellement sortie de la
    fenêtre, avec le résumé précédent comme contexte. La version qui relisait
    tout le fil envoyait ~35 k tokens d'entrée au 100ᵉ message, à chaque tour.
    """
    with Session(_base()) as db:
        _, conv = _fil(db)
        _remplir(db, conv, 6)  # 12 messages → 4 sortent de la fenêtre
        vus: list[str] = []

        def _generate(*, system, prompt, tier="chat", max_tokens=0, history=None):
            vus.append(prompt)
            return LLMResult(text="Résumé.", model="m", provider="p")

        monkeypatch.setattr(intel.llm_client, "generate", _generate)

        intel._mettre_a_jour_resume(db, conv)
        assert conv.resume_messages == 12 - intel.HISTORIQUE_MESSAGES
        assert "Question 0" in vus[0] and "Question 1" in vus[0]

        # Un tour de plus : seule la paire qui vient de sortir est envoyée.
        base = dt.datetime(2026, 9, 2, tzinfo=dt.timezone.utc)
        for i, role in enumerate(("user", "assistant")):
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role=role, content=f"Nouveau {i}",
                                 created_at=base + dt.timedelta(minutes=i)))
        conv.message_count = 14
        db.commit()
        intel._mettre_a_jour_resume(db, conv)

        assert len(vus) == 2
        assert "Question 2" in vus[1] and "Réponse 2" in vus[1]
        assert "Question 0" not in vus[1] and "Question 1" not in vus[1]
        assert "Résumé précédent" in vus[1], "le résumé porte déjà le reste du fil"
        assert conv.resume_messages == 14 - intel.HISTORIQUE_MESSAGES

        # Rien de neuf n'est sorti de la fenêtre : pas de second appel payé.
        intel._mettre_a_jour_resume(db, conv)
        assert len(vus) == 2


def test_resume_roulant_sort_du_cycle_de_requete(monkeypatch):
    """Finding 4 — le résumé ne doit plus tourner dans le générateur de la
    réponse : Starlette n'envoie le dernier chunk qu'après `StopIteration`,
    donc la connexion SSE restait ouverte (et un worker occupé) le temps d'un
    second appel au modèle, APRÈS le `done`.
    """
    from sqlalchemy.orm import sessionmaker

    import app.db as app_db

    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Texte."], "end_turn")])
    monkeypatch.setattr(intel.llm_client, "generate",
                        lambda **k: LLMResult(text="Résumé du fil.", model="m",
                                              provider="p"))

    engine = _base_complete(partagee=True)
    # La tâche de fond ouvre SA session : `get_db` a déjà fermé celle de la
    # requête quand elle s'exécute.
    monkeypatch.setattr(app_db, "SessionLocal",
                        sessionmaker(bind=engine, autoflush=False, future=True))

    lancees: list = []

    reel = intel.threading.Thread

    class _Thread:
        """Intercepte le seul thread du résumé, laisse passer les autres."""

        def __new__(cls, *a, target=None, **kw):
            if target is not intel._mettre_a_jour_resume_en_tache:
                return reel(*a, target=target, **kw)
            return super().__new__(cls)

        def __init__(self, *, target, args=(), daemon=False, **kw):
            self.cible, self.args, self.daemon = target, args, daemon

        def start(self):
            lancees.append(self)

    monkeypatch.setattr(intel.threading, "Thread", _Thread)

    with Session(engine) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 5)  # 10 messages + le tour = 12
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse du marché du logiciel RH",
            is_admin=False))
        conv_id = conv.id
        # Le générateur est ÉPUISÉ sans avoir résumé : rien derrière le `done`.
        assert evts[-1]["step"] == "done"
        assert conv.resume is None
        assert len(lancees) == 1 and lancees[0].daemon is True

    # Le thread, exécuté ici synchroniquement.
    lancees[0].cible(*lancees[0].args)

    with Session(engine) as db:
        rechargee = db.get(intel.Conversation, conv_id)
        assert rechargee.resume == "Résumé du fil."
        assert rechargee.resume_messages == 12 - intel.HISTORIQUE_MESSAGES


def test_tache_de_fond_du_resume_ne_leve_jamais(monkeypatch):
    """Un thread qui lève ne prévient personne : la tâche absorbe tout, y
    compris une conversation supprimée entre-temps."""
    from sqlalchemy.orm import sessionmaker

    import app.db as app_db

    engine = _base_complete(partagee=True)
    monkeypatch.setattr(app_db, "SessionLocal",
                        sessionmaker(bind=engine, autoflush=False, future=True))
    intel._mettre_a_jour_resume_en_tache(uuidlib.uuid4())  # introuvable

    def _boom():
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(app_db, "SessionLocal", _boom)
    intel._mettre_a_jour_resume_en_tache(uuidlib.uuid4())  # ne lève pas


def test_cle_idempotence_absente_des_tours_non_complets(monkeypatch):
    """Finding 3 — une clé posée sur un `partiel` ou un `degrade` rendait le
    rejeu ABSORBANT : le frontend qui renvoyait la même clé après une coupure
    recevait définitivement le texte tronqué archivé par cette coupure, sans
    jamais rien facturer. La clé ne se pose que sur `complet`.
    """
    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")

    def _stream_coupe(**kwargs):
        def _gen():
            yield "Début. "
            raise RuntimeError("connexion coupée")

        return _gen()

    monkeypatch.setattr(intel.llm_client, "stream_text", _stream_coupe)

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        cid = conv.id
        question = "Analyse du marché du logiciel RH en France"
        list(intel.stream_message(db, uid, str(cid), question,
                                  is_admin=False, cle_idempotence="cle-1"))
        partiel = db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant")).one()
        assert partiel.statut == "partiel"
        assert partiel.cle_idempotence is None

        # Le tour dégradé non plus ne fixe pas la clé.
        monkeypatch.setattr(intel.llm_client, "stream_text",
                            lambda **k: (_ for _ in ()).throw(RuntimeError("503")))
        list(intel.stream_message(db, uid, str(cid), question,
                                  is_admin=False, cle_idempotence="cle-2"))
        degrade = db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant",
            intel.Message.statut == "degrade")).one()
        assert degrade.cle_idempotence is None

        # La même clé peut donc encore obtenir une réponse COMPLÈTE.
        _stub_flux(monkeypatch, [(["Réponse entière."], "end_turn")])
        evts = _evenements(intel.stream_message(
            db, uid, str(cid), question, is_admin=False,
            cle_idempotence="cle-1"))
        assert "rejeu" not in evts[-1]
        assert evts[-1]["data"]["content"] == "Réponse entière."
        assert evts[-1]["data"]["statut"] == "complet"
        complet = db.get(intel.Message, uuidlib.UUID(evts[-1]["data"]["id"]))
        assert complet.cle_idempotence == "cle-1"
        assert len(debits) == 1, "seul le tour complet est facturé"


def test_mesure_gemini_conservee_sur_interruption(monkeypatch):
    """Finding 8 — un Stop laissait la consommation dans `_dernier_usage` sans
    jamais la cumuler : le message partiel était archivé sans tokens ni coût,
    alors que le coût fournisseur, lui, a bien été payé."""
    import types

    from app.shared.llm_client import gemini

    lignes = [
        'data: {"candidates":[{"content":{"parts":[{"text":"Bonjour"}]}}],'
        '"usageMetadata":{"promptTokenCount":11,"candidatesTokenCount":3}}',
        'data: {"candidates":[{"content":{"parts":[{"text":" monde"}]}}]}',
    ]

    class _Reponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter(lignes)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(gemini, "get_settings",
                        lambda: types.SimpleNamespace(gemini_api_key="k",
                                                      llm_chat_model="gemini-flash"))
    monkeypatch.setattr(gemini.httpx, "stream", lambda *a, **k: _Reponse())

    mesure: dict = {}
    flux = gemini.stream(system="s", prompt="p", mesure=mesure)
    assert next(flux) == "Bonjour"
    flux.close()  # ce que fait le service sur une déconnexion

    assert mesure["model"] == "gemini-flash"
    assert (mesure["input_tokens"], mesure["output_tokens"]) == (11, 3)
    assert "_dernier_usage" not in mesure


def test_bascule_ferme_le_flux_du_fournisseur_en_echec(monkeypatch):
    """Finding 9 — sur un échec avant le premier morceau, le flux du
    fournisseur était abandonné sans `close()` : la connexion sortante
    (`with httpx.stream(...)`) ne se libérait qu'au ramasse-miettes."""
    from app.shared.llm_client import claude, gemini

    class _FluxEnEchec:
        def __init__(self):
            self.ferme = False

        def __iter__(self):
            return self

        def __next__(self):
            raise RuntimeError("503 avant le premier mot")

        def close(self):
            self.ferme = True

    abandonne = _FluxEnEchec()
    monkeypatch.setattr(gemini, "available", lambda: True)
    monkeypatch.setattr(gemini, "stream", lambda **k: abandonne)
    monkeypatch.setattr(claude, "available", lambda: True)

    def _claude_stream(**kwargs):
        def _gen():
            yield "repli"
            return "end_turn"

        return _gen()

    monkeypatch.setattr(claude, "stream", _claude_stream)

    assert list(intel.llm_client.stream_text(system="s", prompt="p",
                                             tier="chat")) == ["repli"]
    assert abandonne.ferme, "le flux du fournisseur en échec n'a pas été fermé"


# --- Fix round 2 : mesure sur interruption, garde de l'archivage -----------

def test_partiel_archive_avec_les_tokens_mesures(monkeypatch):
    """Issue A — le service doit FERMER le flux du fournisseur avant de lire la
    mesure. Sans ce `close()`, la frame du service tient encore le générateur,
    son `finally` de mesure n'a pas tourné et le partiel était archivé sans
    tokens ni coût — alors que le fournisseur les a bien facturés.
    """
    from app.shared.llm_client.base import cumuler_mesure

    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")

    def _stream_text(*, mesure=None, **kw):
        # Fournisseur réaliste : la mesure n'est cumulée QUE dans le `finally`,
        # donc uniquement si quelqu'un ferme le générateur.
        def _gen():
            try:
                for i in range(40):
                    yield f"mot{i} "
                return "end_turn"
            finally:
                if mesure is not None:
                    cumuler_mesure(mesure, "gemini-flash-test", "gemini", 120, 17)

        return _gen()

    monkeypatch.setattr(intel.llm_client, "stream_text", _stream_text)

    engine = _socle_partage(monkeypatch)
    with Session(engine) as db:
        uid, conv = _fil(db)
        cid = conv.id
        flux = intel.stream_message(db, uid, str(cid),
                                    "Analyse détaillée du marché du logiciel RH",
                                    is_admin=False)
        deltas = 0
        for bloc in flux:
            if '"delta"' in bloc:
                deltas += 1
                if deltas == 2:
                    break
        db.close()
        flux.close()

    with Session(engine) as db:
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == cid,
            intel.Message.role == "assistant")).one()

    assert reponse.statut == "partiel"
    assert reponse.tokens_sortie == 17, "partiel archivé sans tokens de sortie"
    assert reponse.tokens_entree == 120
    assert reponse.modele == "gemini-flash-test"
    assert reponse.cout_micro_eur is not None, "partiel archivé à coût nul"
    assert debits == [], "un flux coupé a été facturé"


def test_archivage_en_echec_ne_sort_pas_du_close(monkeypatch):
    """Issue B — une erreur base pendant l'archivage du partiel ne doit pas
    remplacer l'annulation par une exception bruyante : `close()` doit rendre
    la main normalement, l'incident reste dans les logs."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [([f"mot{i} " for i in range(40)], "end_turn")])

    def _archivage_casse(*a, **k):
        raise RuntimeError("IntegrityError simulée")


    with Session(_socle_partage(monkeypatch)) as db:
        uid, conv = _fil(db)
        flux = intel.stream_message(db, uid, str(conv.id),
                                    "Analyse détaillée du marché du logiciel RH",
                                    is_admin=False)
        for bloc in flux:
            if '"delta"' in bloc:
                break
        monkeypatch.setattr(intel, "_reponse_assistant", _archivage_casse)
        db.close()
        flux.close()  # ne doit PAS lever


def test_session_refermee_en_fin_de_flux(monkeypatch):
    """Issue D — `get_db` ferme la session avant que le corps du générateur ne
    démarre ; le premier accès ORM la ressuscite et personne ne la refermait,
    donc la transaction ouverte par `_finalize_turn` retenait sa connexion
    jusqu'au ramasse-miettes."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Réponse entière."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        fermetures = []
        vraie_fermeture = db.close

        def _close():
            fermetures.append(True)
            vraie_fermeture()

        monkeypatch.setattr(db, "close", _close)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse du marché du logiciel RH en France",
            is_admin=False))

        assert evts[-1]["step"] == "done"
        assert fermetures, "la session n'a pas été refermée en fin de flux"
        # Refermée, donc plus de transaction en cours : la connexion est rendue.
        assert not db.in_transaction()


def test_mesure_claude_conservee_sur_interruption(monkeypatch):
    """Issue C — côté Claude, `get_final_message()` est APRÈS le flux de texte :
    un Stop ne mesurait rien. On récupère l'instantané du SDK."""
    import types

    from app.shared.llm_client import claude

    class _Flux:
        def __init__(self):
            self.text_stream = iter(["Bonjour", " monde"])
            self.current_message_snapshot = types.SimpleNamespace(
                usage=types.SimpleNamespace(input_tokens=31, output_tokens=7))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            raise AssertionError("indisponible après une interruption")

    monkeypatch.setattr(claude, "get_settings",
                        lambda: types.SimpleNamespace(anthropic_api_key="k",
                                                      llm_report_model="claude-test"))
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(
        Anthropic=lambda api_key: types.SimpleNamespace(
            messages=types.SimpleNamespace(stream=lambda **k: _Flux()),
            beta=types.SimpleNamespace(messages=types.SimpleNamespace(
                stream=lambda **k: _Flux())))))

    mesure: dict = {}
    flux = claude.stream(system="s", prompt="p", mesure=mesure)
    assert next(flux) == "Bonjour"
    flux.close()  # ce que fait le service sur une déconnexion

    assert mesure["model"] == "claude-test"
    assert mesure["provider"] == "claude"
    assert (mesure["input_tokens"], mesure["output_tokens"]) == (31, 7)


def test_mesure_claude_estimee_si_le_sdk_ne_dit_rien(monkeypatch):
    """Issue C, repli — un SDK muet sur interruption ne doit pas produire un
    partiel à coût nul : la sortie est estimée depuis le texte livré."""
    import types

    from app.shared.llm_client import claude

    class _FluxMuet:
        def __init__(self):
            self.text_stream = iter(["x" * 400, "y" * 400])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @property
        def current_message_snapshot(self):
            raise RuntimeError("aucun instantané")

        def get_final_message(self):
            raise AssertionError("indisponible après une interruption")

    monkeypatch.setattr(claude, "get_settings",
                        lambda: types.SimpleNamespace(anthropic_api_key="k",
                                                      llm_report_model="claude-test"))
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(
        Anthropic=lambda api_key: types.SimpleNamespace(
            messages=types.SimpleNamespace(stream=lambda **k: _FluxMuet()),
            beta=types.SimpleNamespace(messages=types.SimpleNamespace(
                stream=lambda **k: _FluxMuet())))))

    mesure: dict = {}
    flux = claude.stream(system="s", prompt="p", mesure=mesure)
    assert len(next(flux)) == 400
    flux.close()

    assert mesure["input_tokens"] == 0, "l'entrée n'est pas devinable"
    assert mesure["output_tokens"] == 100, "≈ 4 caractères par token"


def test_stream_text_ferme_le_fournisseur_sur_interruption(monkeypatch):
    """Issue A, maillon intermédiaire — `stream_text` est un générateur : le
    `GeneratorExit` du service y arrive au `yield`, hors de portée de son
    `except Exception`. La fermeture du générateur du fournisseur doit donc être
    dans un `finally`, et pas seulement dans l'`except` : ici une référence
    extérieure empêche le ramassage immédiat du générateur, donc seul un
    `close()` explicite déclenche sa mesure — comme dans le service, dont la
    frame reste vivante pendant l'archivage du partiel."""
    from app.shared.llm_client import claude, gemini
    from app.shared.llm_client.base import cumuler_mesure

    monkeypatch.setattr(gemini, "available", lambda: True)
    monkeypatch.setattr(claude, "available", lambda: False)

    retenus = []  # empêche le ramassage du générateur du fournisseur

    def _gemini_stream(*, mesure=None, **kw):
        def _gen():
            try:
                yield "un "
                yield "deux "
            finally:
                if mesure is not None:
                    cumuler_mesure(mesure, "gemini-test", "gemini", 9, 2)

        g = _gen()
        retenus.append(g)
        return g

    monkeypatch.setattr(gemini, "stream", _gemini_stream)

    mesure: dict = {}
    flux = intel.llm_client.stream_text(system="s", prompt="p", tier="chat",
                                        mesure=mesure)
    assert next(flux) == "un "
    flux.close()

    assert (mesure["input_tokens"], mesure["output_tokens"]) == (9, 2)


# ===========================================================================
# Task 3 — gestion des conversations et des dossiers, recherche, régénérer,
# éditer, réindexer.
# ===========================================================================

def _client_http(engine, uid, *, is_admin=False):
    """`TestClient` sur l'app réelle, avec la base de test et un utilisateur
    connecté — le seul moyen de prouver que les ROUTES (méthodes, codes,
    corps) tiennent, et pas seulement le service."""
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user

    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=uid, email="test@axial-ia.fr", is_admin=is_admin)
    return TestClient(app)


def _sse_de(reponse) -> list[dict]:
    return [json.loads(ligne[len("data: "):])
            for ligne in reponse.text.split("\n\n") if ligne.startswith("data: ")]


# --- Step 1 : PATCH / DELETE conversations et dossiers ---------------------

def test_renommer_epingler_archiver_une_conversation():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        cid = str(conv.id)

        c = intel.update_conversation(db, uid, cid, title="  Levée   série A  ")
        # Espaces normalisés : un titre copié-collé depuis un document arrivait
        # avec des retours à la ligne et cassait la liste.
        assert c.title == "Levée série A"
        assert c.pinned_at is None and c.archived_at is None

        assert intel.update_conversation(db, uid, cid, pinned=True).pinned_at
        # PATCH partiel : épingler ne renomme pas.
        assert db.get(intel.Conversation, conv.id).title == "Levée série A"

        c = intel.update_conversation(db, uid, cid, archived=True)
        assert c.archived_at is not None
        # Archiver dépingle : la section « Épinglées » ne doit pas garder un
        # fil rangé hors de vue.
        assert c.pinned_at is None

        assert intel.update_conversation(db, uid, cid, archived=False).archived_at is None

        with pytest.raises(intel.AppError) as e:
            intel.update_conversation(db, uid, cid, title="   ")
        assert e.value.code == "titre_vide"


def test_supprimer_une_conversation_emporte_ses_messages():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 3)
        cid, autre = str(conv.id), intel.create_conversation(
            db, uid, str(conv.project_id), "Autre", None)
        _remplir(db, autre, 1)

        intel.delete_conversation(db, uid, cid)

        assert db.get(intel.Conversation, uuidlib.UUID(cid)) is None
        # Cascade ORM : aucun message orphelin, et le fil voisin intact.
        restants = db.scalars(select(intel.Message)).all()
        assert [m.conversation_id for m in restants] == [autre.id] * 2


def test_proprietaire_seul_gere_sa_conversation():
    """Un identifiant deviné ne doit rien laisser faire — et rendre 404, pas
    403 : on ne confirme pas l'existence d'un fil qui n'est pas le sien."""
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 1)
        cid = str(conv.id)
        mid = str(db.scalars(select(intel.Message)).first().id)
        intrus = str(uuidlib.uuid4())

        for appel in (
            lambda: intel.update_conversation(db, intrus, cid, title="volé"),
            lambda: intel.delete_conversation(db, intrus, cid),
            lambda: intel.preparer_regeneration(db, intrus, cid, mid, is_admin=True),
            lambda: intel.preparer_edition(db, intrus, cid, mid, "volé", is_admin=True),
            lambda: intel.list_conversations(db, intrus, str(conv.project_id)),
            lambda: intel.update_project(db, intrus, str(conv.project_id), name="volé"),
            lambda: intel.delete_project(db, intrus, str(conv.project_id)),
        ):
            with pytest.raises(intel.AppError) as e:
                appel()
            assert (e.value.status_code, e.value.code) == (404, "not_found")

        # Rien n'a bougé.
        assert db.get(intel.Conversation, conv.id).title == "Nouvelle conversation"


def test_deplacer_une_conversation_de_dossier():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        cible = intel.create_project(db, uid, "Levées", None)
        c = intel.update_conversation(db, uid, str(conv.id), project_id=str(cible.id))
        assert c.project_id == cible.id
        assert [x.id for x in intel.list_conversations(db, uid, str(cible.id))] == [conv.id]

        # Dossier d'un AUTRE utilisateur : 404, jamais un déplacement.
        etranger = intel.create_project(db, str(uuidlib.uuid4()), "Chez l'autre", None)
        with pytest.raises(intel.AppError) as e:
            intel.update_conversation(db, uid, str(conv.id),
                                      project_id=str(etranger.id))
        assert (e.value.status_code, e.value.code) == (404, "not_found")
        assert db.get(intel.Conversation, conv.id).project_id == cible.id


def test_liste_des_conversations_epinglees_puis_recentes():
    with Session(_base()) as db:
        uid, ancienne = _fil(db)
        pid = str(ancienne.project_id)
        recente = intel.create_conversation(db, uid, pid, "Récente", None)
        epinglee = intel.create_conversation(db, uid, pid, "Épinglée", None)
        archivee = intel.create_conversation(db, uid, pid, "Archivée", None)
        jamais = intel.create_conversation(db, uid, pid, "Jamais utilisée", None)

        base = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        ancienne.last_message_at = base
        recente.last_message_at = base + dt.timedelta(days=2)
        epinglee.last_message_at = base - dt.timedelta(days=5)  # la plus vieille
        archivee.last_message_at = base + dt.timedelta(days=3)  # la plus récente
        db.commit()
        intel.update_conversation(db, uid, str(epinglee.id), pinned=True)
        intel.update_conversation(db, uid, str(archivee.id), archived=True)

        titres = [c.title for c in intel.list_conversations(db, uid, pid)]
        # Épinglée en tête MALGRÉ son dernier message le plus ancien ;
        # archivée absente ; « jamais utilisée » (last_message_at NULL) en fin.
        assert titres == ["Épinglée", "Récente", "Nouvelle conversation",
                          "Jamais utilisée"]

        avec = [c.title for c in intel.list_conversations(db, uid, pid,
                                                          inclure_archivees=True)]
        assert "Archivée" in avec and avec[0] == "Épinglée"
        assert len(intel.list_conversations(db, uid, pid, limit=2)) == 2
        assert jamais.id in {c.id for c in intel.list_conversations(db, uid, pid)}


def test_dossier_renomme_et_archive():
    with Session(_base()) as db:
        uid = str(uuidlib.uuid4())
        proj = intel.create_project(db, uid, "Workspace", None)
        p = intel.update_project(db, uid, str(proj.id), name="  Général  ")
        assert p.name == "Général" and p.archived_at is None

        assert intel.update_project(db, uid, str(proj.id), archived=True).archived_at
        # `list_projects` ne rend que les dossiers actifs (comportement existant).
        assert intel.list_projects(db, uid) == []
        assert intel.update_project(db, uid, str(proj.id), archived=False).archived_at is None
        assert len(intel.list_projects(db, uid)) == 1

        with pytest.raises(intel.AppError) as e:
            intel.update_project(db, uid, str(proj.id), name="  ")
        assert e.value.code == "nom_vide"


def test_dossier_non_vide_refuse_la_suppression():
    """La cascade emporterait les conversations ET leurs messages : supprimer
    un dossier ne doit pas être une manière d'effacer trente fils par erreur.
    """
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 2)
        pid = str(conv.project_id)

        with pytest.raises(intel.AppError) as e:
            intel.delete_project(db, uid, pid)
        assert (e.value.status_code, e.value.code) == (409, "projet_non_vide")
        assert "2 conversation" not in e.value.message  # une seule, non archivée
        assert db.get(intel.Project, conv.project_id) is not None

        # Archivée = plus active : la suppression passe, et emporte le fil.
        intel.update_conversation(db, uid, str(conv.id), archived=True)
        intel.delete_project(db, uid, pid)
        assert db.get(intel.Project, uuidlib.UUID(pid)) is None
        assert db.scalars(select(intel.Conversation)).all() == []
        assert db.scalars(select(intel.Message)).all() == []


def test_routes_de_gestion_publiees_dans_le_schema():
    from app.main import app

    chemins = app.openapi()["paths"]
    attendus = {
        "/intelligence/projects/{project_id}": {"patch", "delete"},
        "/intelligence/conversations/{conversation_id}": {"patch", "delete"},
        "/intelligence/conversations/search": {"get"},
        "/intelligence/conversations/{conversation_id}/messages/{message_id}/regenerer": {"post"},
        "/intelligence/conversations/{conversation_id}/messages/{message_id}/editer": {"post"},
        "/documents/{doc_id}/reindexer": {"post"},
    }
    for chemin, methodes in attendus.items():
        assert chemin in chemins, chemin
        assert methodes <= set(chemins[chemin]), (chemin, list(chemins[chemin]))

    # `ConversationOut` porte enfin de quoi dessiner le panneau.
    props = app.openapi()["components"]["schemas"]["ConversationOut"]["properties"]
    assert {"project_id", "pinned_at", "archived_at", "message_count",
            "last_message_at"} <= set(props)
    # Filtre d'archivage et borne de liste sur la liste de conversations.
    liste = chemins["/intelligence/projects/{project_id}/conversations"]["get"]
    assert {"inclure_archivees", "limit"} <= {p["name"] for p in liste["parameters"]}
    # Régénérer ne prend PAS de corps (le contenu vient du fil) ; éditer si.
    regen = chemins[
        "/intelligence/conversations/{conversation_id}/messages/{message_id}/regenerer"]["post"]
    assert "requestBody" not in regen
    edit = chemins[
        "/intelligence/conversations/{conversation_id}/messages/{message_id}/editer"]["post"]
    assert edit["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "EditionIn")


def test_gestion_des_conversations_en_http():
    """Les codes de retour, vus par un vrai client : 200 sur PATCH, 204 sur
    DELETE, 409 nommé sur un dossier non vide."""
    engine = _base_complete(partagee=True)
    uid = str(uuidlib.uuid4())
    client = _client_http(engine, uid)
    try:
        with Session(engine) as db:
            uid_, conv = _fil(db)
            # Le fil doit appartenir à l'utilisateur connecté.
            conv.user_id = uuidlib.UUID(uid)
            proj = db.get(intel.Project, conv.project_id)
            proj.user_id = uuidlib.UUID(uid)
            db.commit()
            cid, pid = str(conv.id), str(proj.id)

        res = client.patch(f"/intelligence/conversations/{cid}",
                           json={"title": "Série A", "pinned": True})
        assert res.status_code == 200, res.text
        corps = res.json()
        assert corps["title"] == "Série A" and corps["pinned_at"]
        assert corps["project_id"] == pid and corps["archived_at"] is None

        assert client.patch(f"/intelligence/projects/{pid}",
                            json={"name": "Général"}).json()["name"] == "Général"

        refus = client.delete(f"/intelligence/projects/{pid}")
        assert refus.status_code == 409
        assert refus.json()["error"]["code"] == "projet_non_vide"

        assert client.delete(f"/intelligence/conversations/{cid}").status_code == 204
        assert client.delete(f"/intelligence/projects/{pid}").status_code == 204
        # Identifiant inconnu : 404 nommé, pas un 500.
        for chemin in (f"/intelligence/conversations/{cid}",
                       "/intelligence/conversations/pas-un-uuid"):
            assert client.delete(chemin).status_code == 404
    finally:
        client.app.dependency_overrides.clear()


# --- Step 2 : recherche ----------------------------------------------------

def test_recherche_extrait_de_80_caracteres_autour_du_terme():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        contenu = "A" * 200 + "TERME" + "B" * 200
        db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                             role="assistant", content=contenu))
        db.commit()

        (res,) = intel.rechercher(db, uid, "terme")  # insensible à la casse
        extrait = res["extrait"]
        assert extrait.startswith("…") and extrait.endswith("…")
        # ±80 caractères, en dur : le vérifier contre la constante rendrait
        # le test complice de sa modification.
        assert intel.RECHERCHE_MARGE == 80
        assert extrait.count("A") == 80 and extrait.count("B") == 80
        assert len(extrait) == 80 + len("TERME") + 80 + 2  # deux « … »
        assert "TERME" in extrait
        assert res["conversation_id"] == str(conv.id)
        assert res["project_id"] == str(conv.project_id)
        assert res["message_id"] is not None and res["created_at"] is not None


def test_recherche_trouve_par_titre_et_ignore_les_archivees():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        pid = str(conv.project_id)
        intel.update_conversation(db, uid, str(conv.id), title="Cartographie des fonds")
        archivee = intel.create_conversation(db, uid, pid, "Cartographie ancienne", None)
        db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=archivee.id,
                             role="user", content="Cartographie du marché"))
        db.commit()
        intel.update_conversation(db, uid, str(archivee.id), archived=True)

        res = intel.rechercher(db, uid, "cartographie")
        # Le fil archivé est écarté, titre ET contenu : on l'a rangé hors de vue.
        assert [r["conversation_id"] for r in res] == [str(conv.id)]
        # Trouvé par le TITRE : pas de message à surligner.
        assert res[0]["message_id"] is None
        assert "Cartographie" in res[0]["extrait"]

        # Un autre utilisateur ne voit rien.
        assert intel.rechercher(db, str(uuidlib.uuid4()), "cartographie") == []


def test_recherche_trop_courte_est_un_400_nomme():
    with Session(_base()) as db:
        uid, _ = _fil(db)
        for court in ("", "  ", "ab", " a "):
            with pytest.raises(intel.AppError) as e:
                intel.rechercher(db, uid, court)
            assert (e.value.status_code, e.value.code) == (400, "requete_trop_courte")


def test_recherche_echappe_les_jokers_du_like():
    """`%` et `_` sont les jokers du LIKE : sans échappement, chercher
    « 100 % » remontait tout le fil."""
    with Session(_base()) as db:
        uid, conv = _fil(db)
        for texte in ("Marge de 100 % sur le SaaS", "Aucun pourcentage ici"):
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role="user", content=texte))
        db.commit()

        assert len(intel.rechercher(db, uid, "100 %")) == 1
        assert intel.rechercher(db, uid, "___") == []


def test_recherche_bornee_a_20_resultats():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        base = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        for i in range(30):
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role="user", content=f"pricing numéro {i}",
                                 created_at=base + dt.timedelta(minutes=i)))
        db.commit()

        res = intel.rechercher(db, uid, "pricing")
        assert len(res) == intel.RECHERCHE_RESULTATS == 20
        # Les plus récents d'abord, un message = un point d'arrivée.
        assert "numéro 29" in res[0]["extrait"]
        assert len({r["message_id"] for r in res}) == 20
        dates = [r["created_at"] for r in res]
        assert dates == sorted(dates, reverse=True)


def test_recherche_en_http():
    engine = _base_complete(partagee=True)
    uid = str(uuidlib.uuid4())
    client = _client_http(engine, uid)
    try:
        with Session(engine) as db:
            proj = intel.create_project(db, uid, "P", None)
            conv = intel.create_conversation(db, uid, str(proj.id), None, None)
            db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                                 role="assistant",
                                 content="Le marché du logiciel RH est concentré."))
            db.commit()
            cid = str(conv.id)

        res = client.get("/intelligence/conversations/search", params={"q": "logiciel"})
        assert res.status_code == 200, res.text
        (ligne,) = res.json()
        assert ligne["conversation_id"] == cid and "logiciel" in ligne["extrait"]

        court = client.get("/intelligence/conversations/search", params={"q": "lo"})
        assert court.status_code == 400
        assert court.json()["error"]["code"] == "requete_trop_courte"
    finally:
        client.app.dependency_overrides.clear()


# --- Step 3 : régénérer / éditer -------------------------------------------

def test_regeneration_conserve_le_nombre_de_messages(monkeypatch):
    """Régénérer supprime la réponse ET sa question : le pipeline recrée
    toujours un message utilisateur, donc ne retirer que la réponse laissait
    la question en double et faisait grandir le fil à chaque essai."""
    _hors_reseau(monkeypatch)
    debits = _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Nouvelle ", "réponse."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 2)  # 4 messages
        cid = str(conv.id)
        derniere = intel._messages_ordonnes(db, conv)[-1]
        assert derniere.role == "assistant"

        question = intel.preparer_regeneration(db, uid, cid, str(derniere.id),
                                               is_admin=True)
        assert question == "Question 1"
        # Entre les deux : le fil est retombé à 2 messages, compteur recalé.
        assert db.get(intel.Conversation, uuidlib.UUID(cid)).message_count == 2

        evts = _evenements(intel.stream_message(db, uid, cid, question, is_admin=True))

    with Session(db.get_bind()) as apres:
        conv2 = apres.get(intel.Conversation, uuidlib.UUID(cid))
        fil = intel._messages_ordonnes(apres, conv2)
        assert conv2.message_count == len(fil) == 4
        assert [m.role for m in fil] == ["user", "assistant", "user", "assistant"]
        assert fil[-2].content == "Question 1"
        assert fil[-1].content == "Nouvelle réponse."
        assert "Réponse 1" not in [m.content for m in fil]
        # Un tour régénéré est un tour : même statut, même facturation.
        assert fil[-1].statut == "complet" and len(debits) == 1
    assert evts[-1]["step"] == "done" and evts[-1]["data"]["statut"] == "complet"


def test_regeneration_refuse_ce_qui_n_est_pas_la_derniere_reponse():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 2)
        cid = str(conv.id)
        fil = intel._messages_ordonnes(db, conv)

        cas = [
            (fil[1], 409, "pas_le_dernier_message"),   # réponse, mais pas la dernière
            (fil[2], 400, "pas_une_reponse"),          # message utilisateur
            (fil[0], 400, "pas_une_reponse"),
        ]
        for msg, code_http, code in cas:
            with pytest.raises(intel.AppError) as e:
                intel.preparer_regeneration(db, uid, cid, str(msg.id), is_admin=True)
            assert (e.value.status_code, e.value.code) == (code_http, code)

        for inconnu in (str(uuidlib.uuid4()), "pas-un-uuid"):
            with pytest.raises(intel.AppError) as e:
                intel.preparer_regeneration(db, uid, cid, inconnu, is_admin=True)
            assert (e.value.status_code, e.value.code) == (404, "not_found")

        # Aucun refus n'a supprimé quoi que ce soit.
        assert len(intel._messages_ordonnes(db, conv)) == 4


def test_regeneration_sans_question_d_origine():
    """Une réponse orpheline (fil abîmé) ne doit pas produire un tour sans
    question : mieux vaut un 409 lisible."""
    with Session(_base()) as db:
        uid, conv = _fil(db)
        db.add(intel.Message(id=uuidlib.uuid4(), conversation_id=conv.id,
                             role="assistant", content="Orpheline"))
        conv.message_count = 1
        db.commit()
        orpheline = intel._messages_ordonnes(db, conv)[-1]

        with pytest.raises(intel.AppError) as e:
            intel.preparer_regeneration(db, uid, str(conv.id), str(orpheline.id),
                                        is_admin=True)
        assert (e.value.status_code, e.value.code) == (409, "question_introuvable")


def test_edition_supprime_la_suite_et_relance(monkeypatch):
    """Éditer la question d'index 2 laisse 2 messages, plus le tour rejoué :
    4 au total. Garder les réponses suivantes produirait un fil qui se
    contredit — elles répondaient à l'ancienne formulation."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Réponse ", "révisée."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 3)  # 6 messages
        cid = str(conv.id)
        fil = intel._messages_ordonnes(db, conv)
        index = 2
        cible = fil[index]
        assert cible.role == "user"

        intel.preparer_edition(db, uid, cid, str(cible.id), "Question 1 corrigée",
                               is_admin=True)
        conv_apres = db.get(intel.Conversation, uuidlib.UUID(cid))
        assert conv_apres.message_count == index
        # `last_message_at` recalé : sinon la conversation vidée restait en
        # tête du panneau.
        assert conv_apres.last_message_at == fil[index - 1].created_at

        list(intel.stream_message(db, uid, cid, "Question 1 corrigée", is_admin=True))

    with Session(db.get_bind()) as apres:
        conv2 = apres.get(intel.Conversation, uuidlib.UUID(cid))
        fil2 = intel._messages_ordonnes(apres, conv2)
        assert conv2.message_count == len(fil2) == index + 2 == 4
        assert [m.content for m in fil2] == [
            "Question 0", "Réponse 0", "Question 1 corrigée", "Réponse révisée."]


def test_edition_refuse_une_reponse_et_un_message_trop_long():
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 1)
        cid = str(conv.id)
        fil = intel._messages_ordonnes(db, conv)

        with pytest.raises(intel.AppError) as e:
            intel.preparer_edition(db, uid, cid, str(fil[1].id), "x", is_admin=True)
        assert (e.value.status_code, e.value.code) == (400, "pas_un_message_utilisateur")

        with pytest.raises(intel.AppError) as e:
            intel.preparer_edition(db, uid, cid, str(fil[0].id),
                                   "x" * (intel.LONGUEUR_MAX_MESSAGE + 1),
                                   is_admin=True)
        assert (e.value.status_code, e.value.code) == (413, "message_trop_long")
        # Le 413 est levé AVANT toute suppression.
        assert len(intel._messages_ordonnes(db, conv)) == 2


def test_regenerer_et_editer_passent_par_le_meme_flux(monkeypatch):
    """Preuve de non-duplication : les trois routes produisent la MÊME
    séquence d'événements SSE, parce qu'elles appellent le même générateur et
    la même enveloppe `_flux_sse` du routeur."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Un.", " Deux."], "end_turn")] * 3)

    engine = _base_complete(partagee=True)
    uid = str(uuidlib.uuid4())
    client = _client_http(engine, uid)
    try:
        with Session(engine) as db:
            proj = intel.create_project(db, uid, "P", None)
            conv = intel.create_conversation(db, uid, str(proj.id), None, None)
            cid = str(conv.id)

        envoi = client.post(f"/intelligence/conversations/{cid}/messages/stream",
                            json={"content": "Analyse détaillée du marché RH"})
        assert envoi.status_code == 200, envoi.text
        assert envoi.headers["content-type"].startswith("text/event-stream")
        reference = [(e["step"], e.get("etape")) for e in _sse_de(envoi)]

        with Session(engine) as db:
            fil = intel._messages_ordonnes(db, db.get(intel.Conversation,
                                                      uuidlib.UUID(cid)))
            assert [m.role for m in fil] == ["user", "assistant"]
            reponse_id, question_id = str(fil[1].id), str(fil[0].id)

        regen = client.post(
            f"/intelligence/conversations/{cid}/messages/{reponse_id}/regenerer")
        assert regen.status_code == 200, regen.text
        assert regen.headers["content-type"].startswith("text/event-stream")
        assert [(e["step"], e.get("etape")) for e in _sse_de(regen)] == reference

        with Session(engine) as db:
            conv2 = db.get(intel.Conversation, uuidlib.UUID(cid))
            fil = intel._messages_ordonnes(db, conv2)
            assert conv2.message_count == len(fil) == 2  # inchangé
            question_id = str(fil[0].id)

        edit = client.post(
            f"/intelligence/conversations/{cid}/messages/{question_id}/editer",
            json={"content": "Analyse détaillée du marché de la paie"})
        assert edit.status_code == 200, edit.text
        assert [(e["step"], e.get("etape")) for e in _sse_de(edit)] == reference

        with Session(engine) as db:
            conv3 = db.get(intel.Conversation, uuidlib.UUID(cid))
            fil = intel._messages_ordonnes(db, conv3)
            assert conv3.message_count == len(fil) == 2  # index 0 + 2
            assert fil[0].content == "Analyse détaillée du marché de la paie"

        # Refus en HTTP, pas en événement d'erreur dans une 200 : un client qui
        # teste `res.status` doit le voir.
        rate = client.post(
            f"/intelligence/conversations/{cid}/messages/{fil[0].id}/regenerer")
        assert rate.status_code == 400
        assert rate.json()["error"]["code"] == "pas_une_reponse"
        trop_long = client.post(
            f"/intelligence/conversations/{cid}/messages/{fil[0].id}/editer",
            json={"content": "x" * (intel.LONGUEUR_MAX_MESSAGE + 1)})
        assert trop_long.status_code == 413
        assert trop_long.json()["error"]["code"] == "message_trop_long"
    finally:
        client.app.dependency_overrides.clear()


def test_suppression_de_messages_recale_le_resume_roulant():
    """Le résumé est un CURSEUR sur le fil (`resume_messages`) : laissé
    au-delà du nouveau nombre de messages, il ne se remettait plus jamais à
    jour et le modèle recevait un résumé de messages disparus."""
    with Session(_base()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 6)  # 12 messages
        conv.resume, conv.resume_messages = "Résumé des 4 premiers.", 4
        db.commit()
        fil = intel._messages_ordonnes(db, conv)

        intel.preparer_edition(db, uid, str(conv.id), str(fil[2].id), "Nouvelle",
                               is_admin=True)
        conv = db.get(intel.Conversation, conv.id)
        assert conv.message_count == 2
        # Curseur ramené au fil réel, résumé conservé (il porte sur le début).
        assert conv.resume_messages == 2 and conv.resume

        intel.preparer_edition(db, uid, str(conv.id), str(fil[0].id), "Nouvelle",
                               is_admin=True)
        conv = db.get(intel.Conversation, conv.id)
        # Fil vidé : le résumé n'a plus d'objet, et `last_message_at` non plus.
        assert (conv.message_count, conv.resume, conv.resume_messages,
                conv.last_message_at) == (0, None, 0, None)


# --- Step 4 : réindexation d'un document -----------------------------------

def _base_documents():
    import app.modules.documents.models  # noqa: F401

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["documents"]])
    return engine


def _document(db, uid, *, contenu="Texte du document. " * 50, chunks=0):
    from app.modules.documents.models import Document

    doc = Document(id=uuidlib.uuid4(), user_id=uuidlib.UUID(uid),
                   filename="note.txt", mime_type="text/plain",
                   size_bytes=len(contenu), content=contenu, chunk_count=chunks)
    db.add(doc)
    db.commit()
    return doc


def test_reindexation_met_a_jour_chunk_count(monkeypatch):
    """Le cas utile de « rafraîchir le RAG » : un import dont l'indexation a
    échoué (`chunk_count = 0`) est en base mais n'alimente aucune réponse."""
    from app.modules.documents import service as docs
    from app.modules.rag import embeddings, vector_store

    supprimes: list[str] = []
    envoyes: list[tuple] = []
    monkeypatch.setattr(vector_store, "delete_document",
                        lambda doc_id, **k: supprimes.append(doc_id))
    monkeypatch.setattr(embeddings, "embed_texts",
                        lambda morceaux: [[0.0] * 3 for _ in morceaux])
    monkeypatch.setattr(vector_store, "upsert_chunks",
                        lambda doc_id, uid, morceaux, vecteurs:
                        (envoyes.append((doc_id, len(morceaux))), len(morceaux))[1])

    with Session(_base_documents()) as db:
        uid = str(uuidlib.uuid4())
        doc = _document(db, uid)
        rendu = docs.reindex(db, uid, str(doc.id))

        assert rendu.chunk_count > 0
        assert db.get(type(doc), doc.id).chunk_count == rendu.chunk_count
        # Les anciens vecteurs partent AVANT les nouveaux : les identifiants de
        # points sont dérivés de l'index de chunk, donc un texte devenu plus
        # court laisserait la queue de l'ancienne version dans les réponses.
        assert supprimes == [str(doc.id)]
        assert envoyes == [(str(doc.id), rendu.chunk_count)]

        # Propriété : le document d'un autre utilisateur est introuvable.
        for mauvais in (str(uuidlib.uuid4()), "pas-un-uuid"):
            with pytest.raises(intel.AppError) as e:
                docs.reindex(db, uid, mauvais)
            assert (e.value.status_code, e.value.code) == (404, "not_found")
        with pytest.raises(intel.AppError):
            docs.reindex(db, str(uuidlib.uuid4()), str(doc.id))


def test_reindexation_en_echec_remet_chunk_count_a_zero(monkeypatch):
    from app.modules.documents import service as docs
    from app.modules.rag import embeddings, vector_store

    monkeypatch.setattr(vector_store, "delete_document", lambda *a, **k: None)
    monkeypatch.setattr(embeddings, "embed_texts",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("qdrant HS")))

    with Session(_base_documents()) as db:
        uid = str(uuidlib.uuid4())
        doc = _document(db, uid, chunks=12)

        with pytest.raises(intel.AppError) as e:
            docs.reindex(db, uid, str(doc.id))
        assert (e.value.status_code, e.value.code) == (503, "indexing_failed")
        # Les anciens vecteurs sont déjà partis : 0 dit la vérité et garde le
        # bouton « Réindexer » visible. Un compteur à 12 promettait des
        # vecteurs disparus.
        assert db.get(type(doc), doc.id).chunk_count == 0


def test_reindexation_d_un_document_sans_texte():
    from app.modules.documents import service as docs

    with Session(_base_documents()) as db:
        uid = str(uuidlib.uuid4())
        doc = _document(db, uid, contenu="   ")
        with pytest.raises(intel.AppError) as e:
            docs.reindex(db, uid, str(doc.id))
        assert (e.value.status_code, e.value.code) == (422, "extraction_failed")


def test_credits_verifies_avant_toute_suppression(monkeypatch):
    """Découvrir le 402 dans le flux aurait laissé le fil amputé de la question
    ET de sa réponse, sans rien avoir régénéré : la perte n'est pas
    rattrapable côté client, le message n'existe plus."""
    from app.modules.billing import service as billing

    monkeypatch.setattr(billing, "check_credits",
                        lambda *a, **k: {"affordable": False, "available": 0,
                                         "cost": 2})
    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        _remplir(db, conv, 2)
        cid = str(conv.id)
        fil = intel._messages_ordonnes(db, conv)

        for appel in (
            lambda: intel.preparer_regeneration(db, uid, cid, str(fil[-1].id)),
            lambda: intel.preparer_edition(db, uid, cid, str(fil[0].id), "Autre"),
        ):
            with pytest.raises(intel.AppError) as e:
                appel()
            assert (e.value.status_code, e.value.code) == (402, "insufficient_credits")

        assert len(intel._messages_ordonnes(db, conv)) == 4
        assert db.get(intel.Conversation, conv.id).message_count == 4


def test_les_dossiers_archives_restent_listables_sur_demande():
    """Sans `inclure_archives`, un dossier archivé disparaissait de l'API et ne
    pouvait plus être désarchivé."""
    import uuid as uuidlib

    from sqlalchemy.orm import Session

    engine = _base()
    with Session(engine) as db:
        uid = str(uuidlib.uuid4())
        actif = intel.create_project(db, uid, "Actif", None)
        archive = intel.create_project(db, uid, "Ancien", None)
        intel.update_project(db, uid, str(archive.id), archived=True)

        ids = {str(p.id) for p in intel.list_projects(db, uid)}
        assert ids == {str(actif.id)}
        tous = {str(p.id) for p in intel.list_projects(db, uid, inclure_archives=True)}
        assert tous == {str(actif.id), str(archive.id)}


# ==========================================================================
# Revue finale de branche — findings 1, 5, 6, 7 et trous de tests du §9.
# ==========================================================================

def _balance(db, uid: str, *, trial=0, free=0, purchased=0, jours=30):
    """Un solde EXPLICITE : `get_or_create_balance` en créerait un d'essai à
    120 crédits, ce qui masquerait tout test de refus."""
    from app.modules.billing.models import CreditBalance

    db.add(CreditBalance(user_id=uuidlib.UUID(uid), trial_credits=trial,
                         free_credits=free, purchased_credits=purchased,
                         trial_expires_at=dt.datetime.now(dt.timezone.utc)
                         + dt.timedelta(days=jours)))
    db.commit()


def _client_http(engine, uid: str, *, is_admin=False):
    """Client HTTP sur l'app réelle, session et identité surchargées."""
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app
    from app.modules.auth.schemas import AuthUser
    from app.modules.auth.security import get_current_user

    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=uid, email="test@axial-ia.fr", is_admin=is_admin)
    return TestClient(app)


# --- Finding 5 : débit et archivage dans la même unité de travail ----------

def test_facturation_en_echec_n_archive_aucune_reponse(monkeypatch):
    """Finding 5 — le débit avait lieu APRÈS le `commit` : un débit en échec
    laissait la réponse en base AVEC sa clé d'idempotence, donc facturable une
    seule fois… et le rejeu la rendait gratuitement pour toujours. Les deux
    forment désormais une seule transaction.
    """
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Réponse entière."], "end_turn")])

    from app.modules.billing import service as billing

    monkeypatch.setattr(billing, "consume_credits",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("compteur de crédits indisponible")))

    engine = _socle_partage(monkeypatch)
    with Session(engine) as db:
        uid, conv = _fil(db)
        cid = conv.id
        evts = _evenements(intel.stream_message(
            db, uid, str(cid), "Analyse détaillée du marché du logiciel RH",
            is_admin=False, cle_idempotence="cle-facturation"))

    # Erreur NOMMÉE : un flux qui s'arrête sans `done` s'afficherait comme une
    # coupure réseau, et l'utilisateur croirait la réponse perdue en route.
    assert evts[-1]["step"] == "error" and evts[-1]["done"] is True
    assert evts[-1]["code"] == "facturation_echec"
    assert evts[-1]["error"] == intel.ERREUR_FACTURATION
    # Vouvoiement (jamais de tutoiement dans un texte vu par l'utilisateur).
    assert "Réessayez" in evts[-1]["error"] and "réessaye " not in evts[-1]["error"]

    with Session(engine) as db:
        assert db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == cid,
            intel.Message.role == "assistant")).all() == []


def test_402_du_debit_garde_son_code(monkeypatch):
    """Un solde qui tombe à zéro entre la vérification et le débit reste un
    402 nommé — le frontend sait déjà l'afficher (`insufficient_credits`)."""
    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    _stub_flux(monkeypatch, [(["Réponse."], "end_turn")])

    from app.modules.billing import service as billing

    monkeypatch.setattr(billing, "consume_credits",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AppError("Crédits insuffisants.", 402,
                                     code="insufficient_credits")))

    engine = _socle_partage(monkeypatch)
    with Session(engine) as db:
        uid, conv = _fil(db)
        cid = conv.id
        evts = _evenements(intel.stream_message(
            db, uid, str(cid), "Analyse du marché du logiciel RH", is_admin=False))
    assert evts[-1]["code"] == "insufficient_credits"
    with Session(engine) as db:
        assert db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant")).all() == []


# --- §9 : facturation réelle de 2 crédits ---------------------------------

def test_debit_reel_de_deux_credits(monkeypatch):
    """§9 — tous les tests passaient par un `consume_credits` neutralisé, et
    les assertions `credits == 2` portaient sur le champ DÉRIVÉ. Ici le vrai
    débit tourne : 10 crédits achetés, 8 après un tour complet.
    """
    from app.modules.analytics import client as analytics
    from app.modules.billing import service as billing
    from app.modules.memory import service as memory
    from app.modules.viz import service as viz_service

    _hors_reseau(monkeypatch)
    monkeypatch.setattr(analytics, "increment_usage", lambda *a, **k: None)
    monkeypatch.setattr(viz_service, "preparer_sans_faute", lambda *a, **k: None)
    monkeypatch.setattr(memory, "build_context", lambda *a, **k: "ACME")
    _stub_flux(monkeypatch, [(["Réponse entière."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        _balance(db, uid, purchased=10)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse du marché du logiciel RH",
            is_admin=False))
        solde = billing.available_credits(billing.get_or_create_balance(db, uid))
        assert solde == 8, "le débit réel de 2 crédits n'a pas eu lieu"
        assert evts[-1]["data"]["credits"] == 2
        # Le solde renvoyé au frontend est celui d'APRÈS le débit.
        assert evts[-1]["data"]["balance"] == 8
        # Et l'événement est journalisé pour la facturation.
        from app.modules.billing.models import CreditEvent

        evenements = db.scalars(select(CreditEvent).where(
            CreditEvent.action == intel.AGENT_MESSAGE_ACTION)).all()
        assert [e.delta for e in evenements] == [-2]


def test_admin_n_est_pas_debite(monkeypatch):
    """Le bypass admin passe par le vrai `consume_credits` : aucun débit, et
    le message est archivé quand même (le commit ne dépend pas du débit)."""
    from app.modules.analytics import client as analytics
    from app.modules.memory import service as memory
    from app.modules.viz import service as viz_service

    _hors_reseau(monkeypatch)
    monkeypatch.setattr(analytics, "increment_usage", lambda *a, **k: None)
    monkeypatch.setattr(viz_service, "preparer_sans_faute", lambda *a, **k: None)
    monkeypatch.setattr(memory, "build_context", lambda *a, **k: "ACME")
    _stub_flux(monkeypatch, [(["Réponse entière."], "end_turn")])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        _balance(db, uid, purchased=10)
        _evenements(intel.stream_message(db, uid, str(conv.id),
                                         "Analyse du marché RH", is_admin=True))
        from app.modules.billing import service as billing

        assert billing.available_credits(
            billing.get_or_create_balance(db, uid)) == 10
        assert db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant")).one().statut == "complet"


# --- §9 : 402 sur un envoi NORMAL -----------------------------------------

def test_402_sur_un_envoi_normal_avant_tout_appel_llm(monkeypatch):
    """§9 — le seul test 402 portait sur régénérer/éditer. Sur un envoi
    normal, le refus doit tomber AVANT de payer un appel au modèle."""
    from app.modules.memory import service as memory
    from app.modules.viz import service as viz_service

    _hors_reseau(monkeypatch)
    monkeypatch.setattr(memory, "build_context", lambda *a, **k: "ACME")
    monkeypatch.setattr(viz_service, "preparer_sans_faute", lambda *a, **k: None)

    def _jamais(**kw):
        raise AssertionError("le modèle a été appelé malgré un solde nul")

    monkeypatch.setattr(intel.llm_client, "stream_text", _jamais)
    monkeypatch.setattr(intel.llm_client, "generate", _jamais)

    engine = _base_complete(partagee=True)
    with Session(engine) as db:
        uid, conv = _fil(db)
        _balance(db, uid)  # tout à zéro
        conv_id = str(conv.id)

    client = _client_http(engine, uid)
    try:
        # Chemin bloquant : 402 HTTP.
        res = client.post(f"/intelligence/conversations/{conv_id}/messages",
                          json={"content": "Analyse du marché RH"})
        assert res.status_code == 402, (res.status_code, res.text)
        assert res.json()["error"]["code"] == "insufficient_credits"

        # Chemin flux : le refus arrive en événement `error` nommé (le flux est
        # déjà ouvert en 200 quand la préparation tourne — seul le 413 est
        # testé avant l'ouverture). `lireFluxSSE` le rend en exception portant
        # ce code, et `decrireErreur` sait déjà l'afficher.
        res = client.post(f"/intelligence/conversations/{conv_id}/messages/stream",
                          json={"content": "Analyse du marché RH"})
        assert res.status_code == 200
        dernier = json.loads(res.text.strip().splitlines()[-1][len("data: "):])
        assert dernier["step"] == "error" and dernier["done"] is True
        assert dernier["code"] == "insufficient_credits"
    finally:
        from app.main import app

        app.dependency_overrides.clear()

    with Session(engine) as db:
        # Aucun message persisté : ni la question, ni une réponse.
        assert db.scalar(select(func.count()).select_from(intel.Message)) == 0


# --- §9 : 401 en cours de conversation, au niveau HTTP --------------------

def test_401_en_cours_de_conversation(monkeypatch):
    """§9 — un jeton expiré pendant la rédaction d'un message doit rendre un
    401 JSON nommé (que `decrireErreur` sait afficher), et ne rien persister."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import get_db
    from app.main import app

    # 32 octets : en dessous, PyJWT avertit à chaque encodage (RFC 7518 §3.2).
    secret = "secret-de-test-suffisamment-long-1234"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    get_settings.cache_clear()

    engine = _base_complete(partagee=True)
    uid = "11111111-2222-3333-4444-555555555555"
    with Session(engine) as db:
        projet = intel.create_project(db, uid, "P", None)
        conv = intel.create_conversation(db, uid, str(projet.id), None, None)
        conv_id = str(conv.id)

    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    try:
        expire = jwt.encode(
            {"sub": uid, "email": "ceo@startup.io",
             "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)},
            secret, algorithm="HS256")
        client = TestClient(app)
        for chemin in (f"/intelligence/conversations/{conv_id}/messages",
                       f"/intelligence/conversations/{conv_id}/messages/stream"):
            res = client.post(chemin, json={"content": "Analyse du marché RH"},
                              headers={"Authorization": f"Bearer {expire}"})
            assert res.status_code == 401, (chemin, res.status_code, res.text)
            assert res.json()["error"]["code"] in ("unauthorized", "invalid_token",
                                                   "token_expired")
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(intel.Message)) == 0


# --- §9 : documents joints, bornes 3 × 8 000 ------------------------------

def test_documents_joints_bornes_a_trois_et_8000_caracteres(monkeypatch):
    """§9 — `document_ids[:3]` et `[:8000]` n'étaient verrouillés par aucun
    test : un quatrième document ou un mémoire de 200 pages passait dans le
    prompt sans que rien ne s'en plaigne."""
    from app.modules.documents import service as documents

    class _Doc:
        def __init__(self, n):
            self.filename = f"doc{n}.pdf"
            self.content = f"D{n}" + ("x" * 20_000)

    docs = {f"id-{n}": _Doc(n) for n in range(4)}
    monkeypatch.setattr(documents, "get_document",
                        lambda db, uid, doc_id: docs[doc_id])

    contexte = intel._attached_docs_context(None, "u", list(docs))
    assert "doc0.pdf" in contexte and "doc2.pdf" in contexte
    assert "doc3.pdf" not in contexte, "plus de 3 pièces jointes acceptées"
    # Chaque document est borné à 8 000 caractères de contenu.
    for n in range(3):
        corps = contexte.split(f"### Document joint : doc{n}.pdf\n")[1].split("\n\n")[0]
        assert len(corps) == 8000, len(corps)
    assert contexte.startswith("## Documents joints par l'utilisateur")

    # Aucun document lisible → aucun bloc (et pas un en-tête orphelin).
    monkeypatch.setattr(documents, "get_document",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("404")))
    assert intel._attached_docs_context(None, "u", ["id-0"]) == ""
    assert intel._attached_docs_context(None, "u", None) == ""


# --- §9 : grounding.assemble depuis le pipeline de conversation -----------

def test_grounding_assemble_depuis_le_pipeline(monkeypatch):
    """§9 — `grounding.assemble` n'avait aucun test. C'est lui qui garantit
    que le [N] du texte et la N-ième citation désignent la MÊME source, web et
    interne confondus : le chemin rapport les numérotait séparément.
    """
    from app.modules.integrations import notion_context
    from app.modules.rag.vector_store import Passage
    from app.shared import search as web_search
    from app.shared.search import rerank
    from app.shared.search.base import SearchResult

    _sans_effets(monkeypatch, contexte="ACME")
    monkeypatch.setattr(notion_context, "passages_pour", lambda *a, **k: [])
    monkeypatch.setattr(intel.llm_client, "generation_available", lambda: True)
    _stub_flux(monkeypatch, [(["Réponse [1] et [2]."], "end_turn")])

    web = [
        SearchResult(title="Marché RH", url="https://a.fr/x", snippet="Web A",
                     provider="exa"),
        # DOUBLON : même domaine, même titre (deux moteurs rendent la page).
        SearchResult(title="Marché RH", url="https://a.fr/x?utm=1",
                     snippet="Web A", provider="tavily"),
        SearchResult(title="Autre étude", url="https://b.fr/y", snippet="Web B",
                     provider="exa"),
    ]
    passages = [Passage(text="Note interne sur la paie", score=0.9,
                        doc_id="d1", source="user",
                        meta={"filename": "paie.pdf"})]
    monkeypatch.setattr(web_search, "search",
                        lambda q, k=6, compteur=None: list(web))
    monkeypatch.setattr(intel, "_retrieve_context",
                        lambda *a, **k: ("", list(passages)))
    # Ordre imposé : l'interne d'abord, puis le doublon web, puis l'autre web.
    # `grounding` lit le réexport de `app.shared.search`, pas le module.
    assert rerank.rerank_indices is not None
    monkeypatch.setattr(web_search, "rerank_indices",
                        lambda q, docs, top_k: [(3, 0.9), (0, 0.8), (1, 0.7),
                                                (2, 0.6)])

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        turn = intel._prepare_turn(db, uid, str(conv.id),
                                   "Analyse du marché du logiciel RH", None,
                                   is_admin=True, document_ids=None)

    # Dédoublonnage : 3 sources sur 4 classées, le doublon web est tombé.
    assert len(turn.citations) == 3
    assert [c.get("source") for c in turn.citations] == ["document", "web", "web"]
    assert [c.get("url") for c in turn.citations][1:] == ["https://a.fr/x",
                                                          "https://b.fr/y"]
    # Numérotation 1..N dans le prompt, dans le MÊME ordre que les citations.
    bloc = turn.prompt.split("Sources (classées par pertinence) :\n")[1]
    assert bloc.splitlines()[0].startswith("[1] (réf. interne : paie.pdf)")
    assert "[2] (web : a.fr) Web A" in bloc
    assert "[3] (web : b.fr) Web B" in bloc
    assert "[4]" not in bloc


# --- §9 : citations persistées sur la réponse ----------------------------

def test_citations_persistees_sur_la_reponse(monkeypatch):
    """§9 — aucune assertion ne portait sur `Message.citations` après un tour.
    Sans elles en base, un fil rechargé perd ses sources : la réponse devient
    non vérifiable."""
    from app.shared.search.base import SearchResult

    _hors_reseau(monkeypatch)
    _sans_effets(monkeypatch, contexte="ACME")
    citations = [{"title": "Marché RH", "url": "https://a.fr/x", "domain": "a.fr",
                  "source": "web", "excerpt": "Web A"}]
    monkeypatch.setattr(intel, "_assemble_sources",
                        lambda *a, **k: ("[1] (web : a.fr) Web A", list(citations)))
    _stub_flux(monkeypatch, [(["Réponse [1]."], "end_turn")])
    assert SearchResult  # la forme des résultats vient bien du module réel

    engine = _base_complete()
    with Session(engine) as db:
        uid, conv = _fil(db)
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse du marché du logiciel RH",
            is_admin=True))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant")).one()
        assert reponse.citations == citations, "citations non persistées"
    # Et envoyées AVANT le premier mot, puis rappelées dans le `done`.
    sources = [e for e in evts if e["step"] == "sources"]
    assert sources and sources[0]["citations"] == citations
    assert evts[-1]["data"]["citations"] == citations


# --- Finding 6 : pagination départagée sur (created_at, id) --------------

def test_pagination_departage_sur_id_a_horodatage_egal(monkeypatch):
    """Finding 6 — la fenêtre triait sur `created_at` seul et bornait avec
    `created_at < borne.created_at` : deux messages écrits dans la même
    microseconde rendaient l'ordre instable, et le jumeau de la borne
    DISPARAISSAIT de la fenêtre — un tour perdu au milieu du fil.
    """
    instant = dt.datetime(2026, 9, 10, 12, 0, tzinfo=dt.timezone.utc)
    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        # 6 messages au MÊME horodatage, d'identifiants ordonnés.
        ids = sorted(uuidlib.uuid4() for _ in range(6))
        for n, mid in enumerate(ids):
            db.add(intel.Message(id=mid, conversation_id=conv.id,
                                 role="user",  # même rôle : seul l'id départage
                                 content=f"m{n}", created_at=instant))
        db.commit()

        page1, encore = intel.list_messages(db, uid, str(conv.id), limit=3)
        assert encore is True
        assert [m.id for m in page1] == ids[3:]

        page2, encore = intel.list_messages(db, uid, str(conv.id), limit=3,
                                            before=str(page1[0].id))
        # Aucun message n'a disparu, aucun n'est rendu deux fois.
        assert [m.id for m in page2] == ids[:3]
        assert encore is False
        assert [m.id for m in page2 + page1] == ids


# --- Finding 7 : un seul résumé à la fois par conversation ---------------

def test_un_seul_resume_par_conversation_a_la_fois(monkeypatch):
    """Finding 7 — un thread était lancé à CHAQUE tour complet au-delà de 8
    messages : sur une rafale, le même fil se faisait résumer autant de fois
    qu'il y avait de tours, chacun avec son appel au modèle."""
    lances: list = []
    reel = intel.threading.Thread

    class _Thread:
        def __new__(cls, *a, target=None, **kw):
            if target is not intel._mettre_a_jour_resume_en_tache:
                return reel(*a, target=target, **kw)
            return super().__new__(cls)

        def __init__(self, *, target, args=(), daemon=False, **kw):
            self.cible, self.args = target, args

        def start(self):
            lances.append(self)

    monkeypatch.setattr(intel.threading, "Thread", _Thread)

    class _Conv:
        id = uuidlib.uuid4()

    conv = _Conv()
    try:
        intel._programmer_resume(conv)
        intel._programmer_resume(conv)  # rafale : ignoré, un résumé court déjà
        intel._programmer_resume(conv)
        assert len(lances) == 1
        # Une AUTRE conversation n'est pas bloquée par la première.
        autre = _Conv()
        autre.id = uuidlib.uuid4()
        intel._programmer_resume(autre)
        assert len(lances) == 2
        # Le verrou est levé quand la tâche se termine (`finally`), donc le
        # tour suivant peut reprendre — le curseur `resume_messages` garantit
        # qu'il repart là où le précédent s'est arrêté.
        intel._liberer_resume(conv.id)
        intel._programmer_resume(conv)
        assert len(lances) == 3
    finally:
        intel._liberer_resume(conv.id)
        intel._resumes_en_cours.clear()


def test_la_tache_de_resume_libere_son_verrou(monkeypatch):
    """Même en échec, la tâche libère la conversation : sinon elle ne serait
    plus JAMAIS résumée pour la durée de vie du process."""
    import app.db as app_db

    cid = uuidlib.uuid4()
    intel._resumes_en_cours.add(cid)
    monkeypatch.setattr(app_db, "SessionLocal",
                        lambda: (_ for _ in ()).throw(RuntimeError("base HS")))
    intel._mettre_a_jour_resume_en_tache(cid)  # ne lève pas
    assert cid not in intel._resumes_en_cours


def test_la_question_precede_sa_reponse_meme_a_la_meme_microseconde():
    """Question et réponse sont flushées ensemble : à `created_at` égal, le tri
    doit mettre la question d'abord, quel que soit l'ordre des uuid."""
    import datetime as dt
    import uuid as uuidlib

    from sqlalchemy.orm import Session

    from app.modules.intelligence.models import Message

    engine = _base()
    with Session(engine) as db:
        uid = str(uuidlib.uuid4())
        proj = intel.create_project(db, uid, "P", None)
        conv = intel.create_conversation(db, uid, str(proj.id), None, None)
        instant = dt.datetime(2026, 9, 11, 10, 0, 0, tzinfo=dt.timezone.utc)
        # uuid de la réponse volontairement PLUS PETIT que celui de la question.
        reponse = Message(id=uuidlib.UUID(int=1), conversation_id=conv.id, role="assistant",
                          content="réponse", created_at=instant)
        question = Message(id=uuidlib.UUID(int=2), conversation_id=conv.id, role="user",
                           content="question", created_at=instant)
        db.add_all([reponse, question])
        db.commit()
        roles = [m.role for m in intel._messages_ordonnes(db, conv)]
        assert roles == ["user", "assistant"]
        page = intel.list_messages(db, uid, str(conv.id), limit=50, before=None)
        items = page["items"] if isinstance(page, dict) else page[0]
        assert [m.role for m in items] == ["user", "assistant"]
