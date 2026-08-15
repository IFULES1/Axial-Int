"""P4 tests: agent routing (non-overlap), AXIAL Recommande, route wiring."""
from fastapi.testclient import TestClient

from app.main import app
from app.modules.intelligence import personas

client = TestClient(app)


def test_macro_query_routes_to_market_scanner():
    agent, note = personas.route("quelles sont les tendances de régulation du marché ?")
    assert agent == "market_scanner"
    assert note is None


def test_competitive_query_routes_to_competitor_radar():
    agent, note = personas.route("qui sont mes concurrents et leur positionnement pricing ?")
    assert agent == "competitor_radar"


def test_non_overlap_redirect_note():
    # User explicitly targets Market Scanner but asks a clearly competitive question.
    agent, note = personas.route(
        "analyse la rivalité concurrentielle et les barrières à l'entrée de mes concurrents",
        requested="market_scanner",
    )
    assert agent == "market_scanner"          # non-destructive: keep requested
    assert note is not None                   # but suggest the redirect
    assert "Competitor Radar" in note


def test_axial_recommande_in_system_prompt():
    for p in personas.list_personas():
        assert "AXIAL Recommande" in p.full_system_prompt()


def test_default_when_no_signal():
    agent, _ = personas.route("bonjour")
    assert agent == personas.DEFAULT_AGENT


def test_intelligence_routes_mounted():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/intelligence/agents", "/intelligence/agents/route",
              "/intelligence/projects",
              "/intelligence/conversations/{conversation_id}/messages"]:
        assert p in paths
    assert client.get("/intelligence/agents").status_code == 200          # public
    assert client.get("/intelligence/projects").status_code in (401, 403)  # protected
