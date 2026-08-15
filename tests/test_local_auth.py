"""Local-auth tests: register/login issue Supabase-shaped JWTs, freemail enforced."""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base
from app.errors import AppError
from app.modules.auth import service
from app.modules.auth.local import hash_password, verify_password
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.security import decode_token, user_from_claims


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "dev-secret-key-for-tests-only-32b")
    monkeypatch.setenv("ALLOW_FREEMAIL", "false")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", future=True)
    import app.modules.auth.models  # noqa: F401
    import app.modules.memory.models  # noqa: F401  (login checks onboarding)
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["dev_users"],
        Base.metadata.tables["company_profiles"],
    ])
    with Session(engine) as s:
        yield s
    get_settings.cache_clear()


def test_password_hash_roundtrip():
    h = hash_password("s3cret!")
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_register_issues_valid_supabase_shaped_jwt(db):
    resp = service.register(
        RegisterRequest(email="ceo@startup.io", password="password123", full_name="Jane"), db)
    assert resp.user.email == "ceo@startup.io"
    assert resp.user.onboarding_complete is False
    # The access token verifies with the same path production uses.
    claims = decode_token(resp.access_token)
    user = user_from_claims(claims)
    assert user.email == "ceo@startup.io"
    assert claims["aud"] == "authenticated"
    assert claims["user_metadata"]["full_name"] == "Jane"
    uuid.UUID(user.id)  # sub is a real UUID


def test_freemail_blocked_in_local_mode(db):
    with pytest.raises(AppError) as exc:
        service.register(RegisterRequest(email="me@gmail.com", password="password123"), db)
    assert exc.value.code == "freemail_blocked"


def test_login_after_register(db):
    service.register(RegisterRequest(email="cfo@startup.io", password="password123"), db)
    resp = service.login(LoginRequest(email="cfo@startup.io", password="password123"), db)
    assert resp.access_token
    with pytest.raises(AppError) as exc:
        service.login(LoginRequest(email="cfo@startup.io", password="WRONG"), db)
    assert exc.value.status_code == 401


def test_duplicate_email_rejected(db):
    service.register(RegisterRequest(email="dup@startup.io", password="password123"), db)
    with pytest.raises(AppError) as exc:
        service.register(RegisterRequest(email="dup@startup.io", password="password123"), db)
    assert exc.value.code == "email_taken"
