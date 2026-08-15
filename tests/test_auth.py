"""P1 auth tests that don't need a live Supabase: the freemail gate and JWT."""
import datetime as dt

import jwt
import pytest

from app.config import get_settings
from app.errors import AppError
from app.modules.auth.freemail import is_professional_email
from app.modules.auth.security import decode_token, user_from_claims


def test_freemail_blocks_personal_domains():
    assert is_professional_email("ceo@startup.io") is True
    assert is_professional_email("me@gmail.com") is False
    assert is_professional_email("me@yahoo.fr") is False
    assert is_professional_email("me@proton.me") is False
    assert is_professional_email("bad-input") is False


def _make_token(secret: str, **claims) -> str:
    payload = {
        "sub": "11111111-2222-3333-4444-555555555555",
        "email": "ceo@startup.io",
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_and_extract_identity(monkeypatch):
    secret = "test-secret"
    get_settings.cache_clear()
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    get_settings.cache_clear()

    token = _make_token(secret, user_metadata={"full_name": "Jane", "is_admin": True})
    claims = decode_token(token)
    user = user_from_claims(claims)

    assert user.id == "11111111-2222-3333-4444-555555555555"
    assert user.email == "ceo@startup.io"
    assert user.full_name == "Jane"
    assert user.is_admin is True

    get_settings.cache_clear()


def test_expired_token_rejected(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    get_settings.cache_clear()

    expired = jwt.encode(
        {"sub": "x", "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)},
        secret, algorithm="HS256",
    )
    with pytest.raises(AppError) as exc:
        decode_token(expired)
    assert exc.value.status_code == 401

    get_settings.cache_clear()
