"""Local auth adapter — self-contained dev authentication.

Creates users in the `dev_users` table and issues Supabase-shaped HS256 JWTs
signed with SUPABASE_JWT_SECRET, so `decode_token` and every downstream module
behave exactly as they will in production. No Supabase project required.

Password hashing uses PBKDF2-HMAC-SHA256 from the stdlib (no extra dependency);
swap for argon2 when promoting local auth to production if ever desired.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os
import uuid

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.modules.analytics import client as analytics
from app.modules.auth.models import DevUser
from app.modules.auth.schemas import AuthUser, LoginRequest, RegisterRequest, TokenResponse

_PBKDF2_ROUNDS = 200_000


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt_b64, hash_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def _issue_tokens(user: DevUser, *, onboarding_complete: bool) -> TokenResponse:
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise AppError("SUPABASE_JWT_SECRET manquant (requis même en auth local).",
                       500, code="auth_misconfigured")
    now = dt.datetime.now(dt.timezone.utc)
    base_claims = {
        "sub": str(user.id),
        "email": user.email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "user_metadata": {
            "full_name": user.full_name,
            "is_admin": user.is_admin,
            "onboarding_complete": onboarding_complete,
        },
        "app_metadata": {"provider": "local", "role": "user"},
    }
    access = jwt.encode(
        {**base_claims, "exp": now + dt.timedelta(seconds=settings.jwt_ttl_seconds)},
        settings.supabase_jwt_secret, algorithm="HS256",
    )
    refresh = jwt.encode(
        {"sub": str(user.id), "type": "refresh",
         "exp": now + dt.timedelta(seconds=settings.refresh_ttl_seconds)},
        settings.supabase_jwt_secret, algorithm="HS256",
    )
    return TokenResponse(
        access_token=access, refresh_token=refresh, expires_in=settings.jwt_ttl_seconds,
        user=AuthUser(id=str(user.id), email=user.email, full_name=user.full_name,
                      is_admin=user.is_admin, onboarding_complete=onboarding_complete),
    )


def _onboarding_complete(db: Session, user_id: str) -> bool:
    from app.modules.memory import service as memory

    return memory.onboarding_complete(db, user_id)


def register(db: Session, data: RegisterRequest) -> TokenResponse:
    existing = db.scalar(select(DevUser).where(DevUser.email == data.email.lower()))
    if existing:
        raise AppError("Cet email est déjà utilisé.", 400, code="email_taken")
    user = DevUser(id=uuid.uuid4(), email=data.email.lower(),
                   password_hash=hash_password(data.password), full_name=data.full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    analytics.record_signup(user_id=str(user.id), email=user.email)
    return _issue_tokens(user, onboarding_complete=False)


def login(db: Session, data: LoginRequest) -> TokenResponse:
    user = db.scalar(select(DevUser).where(DevUser.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise AppError("Email ou mot de passe invalide.", 401, code="bad_credentials")
    analytics.record_login(user_id=str(user.id), email=user.email)
    return _issue_tokens(user, onboarding_complete=_onboarding_complete(db, str(user.id)))


def refresh(db: Session, refresh_token: str) -> TokenResponse:
    """Échange un refresh token local valide contre une nouvelle paire de jetons."""
    settings = get_settings()
    try:
        claims = jwt.decode(refresh_token, settings.supabase_jwt_secret,
                            algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise AppError("Session expirée — reconnecte-toi.", 401,
                       code="refresh_invalid") from e
    if claims.get("type") != "refresh":
        raise AppError("Jeton invalide.", 401, code="refresh_invalid")
    user = db.get(DevUser, uuid.UUID(claims["sub"]))
    if not user:
        raise AppError("Compte introuvable.", 401, code="refresh_invalid")
    return _issue_tokens(user, onboarding_complete=_onboarding_complete(db, str(user.id)))
