"""JWT verification and the current-user dependency.

Supabase can sign access tokens two ways:
  * **ES256 / RS256** (asymmetric) — the default for projects using JWT signing
    keys. We verify against the project's public JWKS (fetched + cached once).
  * **HS256** (legacy shared secret) — also used by local dev mode, which mints
    its own tokens signed with SUPABASE_JWT_SECRET.

We branch on the token's `alg` header so both work. Verification stays local
after the one-time JWKS fetch; identity is the Supabase UUID.
"""
from __future__ import annotations

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import get_settings
from app.errors import AppError
from app.modules.auth.schemas import AuthUser

_bearer = HTTPBearer(auto_error=True)

# Cached JWKS client (one per JWKS URL) — refreshes signing keys on rotation.
_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client_for(supabase_url: str) -> PyJWKClient:
    url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url)
        _jwks_clients[url] = client
    return client


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
    # aud varies across Supabase versions; we don't gate on it.
    opts = {"verify_aud": False}
    try:
        alg = jwt.get_unverified_header(token).get("alg", "HS256")

        if alg == "HS256":
            # Legacy shared secret (also local dev mode).
            if not settings.supabase_jwt_secret:
                raise AppError("Auth non configurée (SUPABASE_JWT_SECRET manquant).",
                               500, code="auth_misconfigured")
            return jwt.decode(token, settings.supabase_jwt_secret,
                              algorithms=["HS256"], options=opts)

        # Asymmetric (ES256/RS256) — verify against the project's public JWKS.
        if not settings.supabase_url:
            raise AppError("Auth non configurée (SUPABASE_URL manquant).", 500,
                           code="auth_misconfigured")
        signing_key = _jwks_client_for(settings.supabase_url).get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=[alg], options=opts)
    except jwt.ExpiredSignatureError as e:
        raise AppError("Session expirée.", 401, code="token_expired") from e
    except jwt.InvalidTokenError as e:
        raise AppError("Jeton invalide.", 401, code="token_invalid") from e
    except jwt.PyJWKClientError as e:
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
