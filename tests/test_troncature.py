"""Reprise automatique après troncature de la sortie du modèle.

Le 24/08, une étude de marché livrée à un client s'est arrêtée en plein mot
après 1 740 mots. Le client l'a signalé ; rien côté serveur ne l'avait détecté,
et les 40 crédits avaient été débités. Ces tests verrouillent les deux
comportements qui manquaient : reprendre là où le modèle s'est arrêté, et
refuser de facturer un document qui reste tronqué.
"""
from __future__ import annotations

import types

import pytest

from app.modules.analysis.service import AnalysisResult, finalize
from app.shared.llm_client import claude
from app.shared.llm_client.base import LLMResult


class _Bloc:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Message:
    def __init__(self, text, stop_reason):
        self.content = [_Bloc(text)]
        self.stop_reason = stop_reason
        self.usage = types.SimpleNamespace(input_tokens=10, output_tokens=20)


def _client_factice(reponses):
    """Un client Anthropic qui rend les messages fournis, dans l'ordre."""
    suite = iter(reponses)
    appels = []

    class _Messages:
        def create(self, **kwargs):
            appels.append(kwargs["messages"])
            return next(suite)

    class _Client:
        messages = _Messages()

    return _Client(), appels


def test_reprise_apres_troncature(monkeypatch):
    """Deux morceaux tronqués puis une fin propre → un seul texte recollé."""
    client, appels = _client_factice([
        _Message("Début du rapport, coupé au milieu du m", "max_tokens"),
        _Message("ot puis la suite.", "end_turn"),
    ])
    monkeypatch.setattr(claude, "get_settings",
                        lambda: types.SimpleNamespace(anthropic_api_key="k",
                                                      llm_report_model="claude-sonnet-5"))
    monkeypatch.setitem(__import__("sys").modules, "anthropic",
                        types.SimpleNamespace(Anthropic=lambda **_: client))

    res = claude.generate(system="s", prompt="p", max_tokens=4000)

    assert res.text == "Début du rapport, coupé au milieu du mot puis la suite."
    assert res.stop_reason == "end_turn"
    # La reprise renvoie l'historique : consigne initiale + ce qui a été écrit.
    assert len(appels) == 2
    assert appels[1][-1]["role"] == "user"


def test_abandon_apres_trois_reprises(monkeypatch):
    """Un modèle qui tronque sans fin s'arrête au plafond, sans boucler."""
    client, appels = _client_factice([_Message("morceau ", "max_tokens")] * 8)
    monkeypatch.setattr(claude, "get_settings",
                        lambda: types.SimpleNamespace(anthropic_api_key="k",
                                                      llm_report_model="claude-sonnet-5"))
    monkeypatch.setitem(__import__("sys").modules, "anthropic",
                        types.SimpleNamespace(Anthropic=lambda **_: client))

    res = claude.generate(system="s", prompt="p", max_tokens=4000)

    assert len(appels) == 1 + claude.MAX_REPRISES
    assert res.stop_reason == "max_tokens"


def test_rapport_tronque_non_facture():
    """Un résultat dégradé ne consomme aucun crédit et n'est pas archivé."""
    tronque = AnalysisResult(
        analysis_type="etude_marche", title="Etude", content="coupé en plein",
        degraded=True, status_note="truncated_generation",
    )
    info = finalize(db=None, user_id="u", analysis_type="etude_marche",
                    result=tronque, is_admin=False)
    assert info == {"report_id": None, "charged": 0}


def test_gemini_signale_la_troncature():
    """La normalisation de finishReason permet un seul cas côté appelant."""
    assert LLMResult(text="x", model="m", provider="gemini",
                     stop_reason="max_tokens").stop_reason == "max_tokens"


def test_angles_couvrent_le_reglementaire():
    """Une étude de marché doit interroger l'accès au marché, pas seulement sa taille.

    Le rapport du 24/08 a décoté un marché de 35 à 50 % parce qu'aucune source
    ne confirmait la voie d'homologation — alors que rien ne l'avait cherchée.
    """
    from app.modules.analysis.prompts import angles_de_recherche

    angles = angles_de_recherche("etude_marche", "taille du marché des cargos électriques")
    assert len(angles) > 1, "une seule requête ne couvre qu'une facette"
    assert angles[0] == "taille du marché des cargos électriques"
    assert any("églementaire" in a for a in angles), angles


def test_angles_sans_type_connu():
    """Type inconnu ou question vide : on retombe sur le comportement d'origine."""
    from app.modules.analysis.prompts import angles_de_recherche

    assert angles_de_recherche("inexistant", "ma question") == ["ma question"]
    assert angles_de_recherche("etude_marche", "") == []


def test_angles_suivent_la_langue_de_la_question():
    """Un suffixe français sur une question anglaise dégrade les moteurs lexicaux."""
    from app.modules.analysis.prompts import angles_de_recherche

    en = angles_de_recherche("etude_marche", "What is the market size for electric cargo bikes?")
    assert any("regulatory landscape" in a for a in en), en
    assert not any("réglementaire" in a for a in en), en

    fr = angles_de_recherche("etude_marche", "Quelle est la taille du marché des vélos cargo ?")
    assert any("réglementaire" in a.lower() for a in fr), fr


def test_luhn_epargne_les_chiffres_de_marche():
    """Sans clé de contrôle, un rapport de marché perdrait ses chiffres.

    Détecté le 25/08 en mode shadow : la suite d'années « 2024 2025 … 2031 »
    était comptée comme un numéro de carte.
    """
    from app.modules.pii.redaction import redact

    _, faux = redact("Croissance 2024 2025 2026 2027 2028 2029 2030 2031 constante.")
    assert faux == {}, faux

    _, vrai = redact("Paiement par 4539 1488 0343 6467 accepté.")
    assert any("4539" in v for v in vrai.values()), vrai


def test_rapport_survit_a_la_fermeture_du_navigateur(monkeypatch):
    """Un rapport doit être archivé même si le client se déconnecte.

    L'archivage vivait après le dernier `yield` du générateur SSE : fermer
    l'onglet pendant les minutes de rédaction faisait perdre le rapport, alors
    que la génération était allée au bout et avait été payée. Reproduit le
    25/08 avant correction.
    """
    import time
    from unittest import mock

    from app.modules.analysis import service

    archives: list[str] = []

    def faux_run(**kw):
        time.sleep(2)
        return service.AnalysisResult(analysis_type="analyse_risques",
                                      title="T", content="contenu", degraded=False)

    def faux_finalize(db, user_id, analysis_type, result, *, is_admin):
        archives.append(result.title)
        return {"report_id": "r1", "charged": 25}

    class _Session:
        def __enter__(self):
            return None

        def __exit__(self, *a):
            return False

    import app.db as db_mod
    import app.modules.memory.service as mem
    with mock.patch.object(service, "run_analysis", faux_run), \
         mock.patch.object(service, "finalize", faux_finalize), \
         mock.patch.object(service, "precheck_credits", lambda *a, **k: None), \
         mock.patch.object(service, "HEARTBEAT_SECONDS", 1), \
         mock.patch.object(db_mod, "SessionLocal", _Session), \
         mock.patch.object(mem, "build_context", lambda *a, **k: ""), \
         mock.patch.object(service, "_profile_dict", lambda *a, **k: {}):
        gen = service.stream_analysis(db=None, user_id="u", is_admin=False,
                                      query="q", analysis_type="analyse_risques")
        # Couper AVANT le premier battement reviendrait à tester une génération
        # jamais démarrée. On attend d'être en pleine rédaction.
        for evt in gen:
            if "heartbeat" in evt:
                break
        gen.close()  # ce que fait FastAPI quand le navigateur part

    assert archives == ["T"], "le rapport a été perdu à la déconnexion"
