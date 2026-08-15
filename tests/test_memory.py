"""P-memory tests: profile upsert, onboarding gate, context injection."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.main import app
from app.modules.memory import service as memory

client = TestClient(app)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", future=True)
    import app.modules.memory.models  # noqa: F401
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["company_profiles"]])
    with Session(engine) as s:
        yield s


def test_onboarding_incomplete_without_profile(db):
    uid = str(uuid.uuid4())
    assert memory.onboarding_complete(db, uid) is False
    assert memory.build_context(db, uid) == ""


def test_onboarding_complete_after_named_profile(db):
    uid = str(uuid.uuid4())
    memory.upsert_profile(db, uid, {"company_name": "Axial", "sector": "SaaS B2B"})
    assert memory.onboarding_complete(db, uid) is True


def test_context_injection_formats_fields(db):
    uid = str(uuid.uuid4())
    memory.upsert_profile(db, uid, {
        "company_name": "Axial", "sector": "SaaS B2B", "funding_stage": "Seed",
        "main_challenge": "acquisition",
    })
    ctx = memory.build_context(db, uid)
    assert "Contexte entreprise" in ctx
    assert "Entreprise : Axial" in ctx
    assert "Secteur : SaaS B2B" in ctx
    assert "Défi principal : acquisition" in ctx


def test_unknown_fields_ignored(db):
    uid = str(uuid.uuid4())
    p = memory.upsert_profile(db, uid, {"company_name": "X", "hacker_field": "nope"})
    assert not hasattr(p, "hacker_field") or getattr(p, "hacker_field", None) is None


def test_memory_routes_mounted():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/memory/profile", "/memory/onboarding-status"]:
        assert p in paths
    assert client.get("/memory/onboarding-status").status_code in (401, 403)
