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


# ==========================================================================
# Task 2 — pipeline de message : mémoire de fil, flux par étapes, statuts,
# idempotence, coût exposé.
# ==========================================================================

import datetime as dt  # noqa: E402
import json  # noqa: E402

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
    engine = _base_complete(partagee=True)
    with Session(engine) as db:
        uid, conv = _fil(db)
        generateur = intel.stream_message(
            db, uid, str(conv.id), "Analyse détaillée du marché du logiciel RH",
            is_admin=False, cle_idempotence="cle-coupee")
        flux = intel_router._flux_sse(generateur)

        async def _lire_deux_puis_partir():
            deltas = 0
            async for bloc in flux:
                if '"delta"' in bloc:
                    deltas += 1
                    if deltas == 2:
                        break
            await flux.aclose()

        asyncio.run(_lire_deux_puis_partir())

        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == conv.id,
            intel.Message.role == "assistant")).one()
        assert reponse.statut == "partiel"
        assert reponse.content.startswith("mot0")
        assert reponse.content.endswith(intel.NOTE_INTERROMPUE)
        assert "mot39" not in reponse.content
        assert debits == [], "un flux coupé a été facturé"
        # Le fil reste cohérent : la question ET la réponse partielle sont là.
        db.refresh(conv)
        assert conv.message_count == 2
        assert db.scalar(select(func.count()).select_from(intel.Message)
                         .where(intel.Message.conversation_id == conv.id)) == 2
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

    with Session(_base_complete()) as db:
        uid, conv = _fil(db)
        flux = intel.stream_message(db, uid, str(conv.id),
                                    "Analyse détaillée du marché du logiciel RH",
                                    is_admin=False)
        # On avance jusqu'en pleine rédaction, puis on coupe comme FastAPI.
        deltas = 0
        for bloc in flux:
            if '"delta"' in bloc:
                deltas += 1
                if deltas == 3:
                    break
        flux.close()

        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == conv.id,
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
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse du marché du logiciel RH en France",
            is_admin=False))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == conv.id,
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
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), "Analyse du marché du logiciel RH en France",
            is_admin=False))
        reponse = db.scalars(select(intel.Message).where(
            intel.Message.conversation_id == conv.id,
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
        question = "Analyse du marché du logiciel RH en France"
        list(intel.stream_message(db, uid, str(conv.id), question,
                                  is_admin=False, cle_idempotence="cle-1"))
        partiel = db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant")).one()
        assert partiel.statut == "partiel"
        assert partiel.cle_idempotence is None

        # Le tour dégradé non plus ne fixe pas la clé.
        monkeypatch.setattr(intel.llm_client, "stream_text",
                            lambda **k: (_ for _ in ()).throw(RuntimeError("503")))
        list(intel.stream_message(db, uid, str(conv.id), question,
                                  is_admin=False, cle_idempotence="cle-2"))
        degrade = db.scalars(select(intel.Message).where(
            intel.Message.role == "assistant",
            intel.Message.statut == "degrade")).one()
        assert degrade.cle_idempotence is None

        # La même clé peut donc encore obtenir une réponse COMPLÈTE.
        _stub_flux(monkeypatch, [(["Réponse entière."], "end_turn")])
        evts = _evenements(intel.stream_message(
            db, uid, str(conv.id), question, is_admin=False,
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
