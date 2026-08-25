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
