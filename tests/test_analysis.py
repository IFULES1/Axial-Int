"""P3 tests: prompt templates, graceful degradation, routing.

No network: we monkeypatch provider availability to exercise the resilient
paths without calling Perplexity/Claude.
"""
import pytest
from fastapi.testclient import TestClient

from app.errors import AppError
from app.main import app
from app.modules.analysis import service
from app.modules.analysis.prompts import ANALYSIS_PROMPTS, get_prompt_template, is_valid_type

client = TestClient(app)


def test_all_types_have_context_slot():
    for key, tmpl in ANALYSIS_PROMPTS.items():
        assert "{context}" in tmpl, key
        assert is_valid_type(key)
    assert not is_valid_type("nope")


def test_unknown_type_raises():
    with pytest.raises(AppError) as exc:
        service.run_analysis(query="x", analysis_type="bogus", user_id="u")
    assert exc.value.status_code == 400


def test_degrades_when_llm_unavailable(monkeypatch):
    # New engine: degradation happens when NO generation LLM (Gemini/Claude) is
    # usable — not when web search is down (web is optional, RAG still feeds it).
    monkeypatch.setattr(service.llm_client, "generation_available", lambda: False)
    result = service.run_analysis(
        query="analyse marché X", analysis_type="etude_marche",
        user_id="11111111-2222-3333-4444-555555555555", top_k=0,
    )
    assert result.degraded is True
    assert result.status_note == "llm_unavailable"
    assert "disponible" in result.content.lower()


def test_default_template_fallback():
    assert get_prompt_template("unknown") == ANALYSIS_PROMPTS["synthese_executive"]


def test_analysis_routes_mounted():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/analysis/types" in paths
    assert "/analysis/run" in paths
    assert "/analysis/stream" in paths
    # /analysis/types is public; run/stream require auth.
    assert client.get("/analysis/types").status_code == 200
    assert client.post("/analysis/run", json={"query": "x"}).status_code in (401, 403)


def test_le_style_exige_une_synthese_executive_en_tete():
    from app.modules.analysis import prompts

    assert "## Synthèse exécutive" in prompts.OUTPUT_STYLE
    assert "## Executive summary" in prompts.OUTPUT_STYLE


def test_le_style_demande_un_bloc_viz_et_plus_la_marque_graphique():
    from app.modules.analysis import prompts

    assert "```viz" in prompts.OUTPUT_STYLE and '"intent"' in prompts.OUTPUT_STYLE
    assert "Graphique : <titre court>" not in prompts.OUTPUT_STYLE


def test_les_personas_de_chat_connaissent_le_bloc_viz():
    from app.modules.intelligence import personas

    assert "```viz" in personas.AXIAL_RECOMMENDE_INSTRUCTION
