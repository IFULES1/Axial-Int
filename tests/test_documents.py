"""P2 tests: chunking logic and route wiring (no OpenAI/Qdrant needed)."""
from fastapi.testclient import TestClient

from app.main import app
from app.modules.documents.extract import chunk_text

client = TestClient(app)


def test_chunk_short_text_single_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_chunk_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_overlap_and_coverage():
    words = " ".join(f"word{i}" for i in range(600))  # well over CHUNK_SIZE chars
    chunks = chunk_text(words, size=1000, overlap=200)
    assert len(chunks) > 1
    # Every chunk is within bounds and non-empty.
    assert all(0 < len(c) <= 1000 for c in chunks)
    # Overlap: consecutive chunks share some trailing/leading content.
    joined = " ".join(chunks)
    assert "word0" in joined and "word599" in joined


def test_documents_routes_mounted():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/documents/upload" in paths
    assert "/documents" in paths
    assert "/documents/{doc_id}" in paths
    assert "/rag/search" in paths
    # Protected: no token → 401/403.
    assert client.get("/documents").status_code in (401, 403)
    assert client.post("/rag/search", json={"query": "x"}).status_code in (401, 403)
