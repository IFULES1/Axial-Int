"""JWT verification and the current-user dependency.

Supabase issues HS256 JWTs signed with SUPABASE_JWT_SECRET. We verify them
locally (no network round-trip) and extract a UUID-only identity. The admin
flag is resolved from user/app metadata, matching the legacy behaviour.
"""
from __future__ import annotations

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errors import AppError
from app.modules.auth.schemas import AuthUser

_bearer = HTTPBearer(auto_error=True)


def _resolve_is_admin(claims: dict) -> bool:
    user_md = claims.get("user_metadata") or {}
    app_md = claims.get("app_metadata") or {}
    return bool(
        user_md.get("is_admin")
        or app_md.get("is_admin")
        or user_md.get("role") == "admin"
        or app_md.get("role") == "admin"
    )


def decode_token(token: str) -> dict:
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise AppError("Auth non configurée (SUPABASE_JWT_SECRET manquant).", 500,
                       code="auth_misconfigured")
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": False},  # Supabase aud varies; we don't gate on it
        )
    except jwt.ExpiredSignatureError as e:
        raise AppError("Session expirée.", 401, code="token_expired") from e
    except jwt.InvalidTokenError as e:
        raise AppError("Jeton invalide.", 401, code="token_invalid") from e


def user_from_claims(claims: dict) -> AuthUser:
    user_md = claims.get("user_metadata") or {}
    return AuthUser(
        id=claims["sub"],
        email=claims.get("email") or user_md.get("email"),
        full_name=user_md.get("full_name"),
        is_admin=_resolve_is_admin(claims),
        onboarding_complete=bool(user_md.get("onboarding_complete", False)),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AuthUser:
    """FastAPI dependency: the authenticated user (UUID identity)."""
    return user_from_claims(decode_token(credentials.credentials))


def get_current_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not user.is_admin:
        raise AppError("Accès réservé aux administrateurs.", 403, code="forbidden")
    return user
