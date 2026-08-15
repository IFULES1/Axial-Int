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
