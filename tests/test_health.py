"""Smoke tests for the P0 scaffold: the app boots and health endpoints work."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "axial-intelligence"


def test_health_providers_shape():
    r = client.get("/health/providers")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert "providers" in body
    names = {p["name"] for p in body["providers"]}
    # New stack: multi-provider web search, Cohere embeddings, Gemini + Claude LLMs.
    assert {"web_search", "embeddings_cohere", "llm_chat_gemini", "llm_report_claude"} <= names


def test_auth_routes_mounted():
    # Endpoints exist in the schema.
    paths = client.get("/openapi.json").json()["paths"]
    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    # /auth/me requires a bearer token.
    assert client.get("/auth/me").status_code in (401, 403)
