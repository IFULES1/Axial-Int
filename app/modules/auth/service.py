"""Auth service: registration and login.

Registration is a single call — POST /auth/register {email, password} — that:
  1. enforces the professional-email policy (unless ALLOW_FREEMAIL),
  2. optionally requires an invitation code (REQUIRE_INVITATION_CODE),
  3. creates the Supabase user (admin API, email auto-confirmed),
  4. signs them in and returns tokens,
  5. records first-seen in analytics (fire-and-forget).

Identity is the Supabase UUID everywhere. Onboarding stays forced: the returned
user carries onboarding_complete=False until the company profile exists.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.errors import AppError
from app.modules.analytics import client as analytics
from app.modules.auth.freemail import is_professional_email
from app.modules.auth.schemas import AuthUser, LoginRequest, RegisterRequest, TokenResponse
from app.modules.auth.supabase_client import admin_client, public_client

logger = logging.getLogger("axial.auth")


def _token_response(session, user_obj) -> TokenResponse:
    md = getattr(user_obj, "user_metadata", None) or {}
    app_md = getattr(user_obj, "app_metadata", None) or {}
    user = AuthUser(
        id=str(user_obj.id),
        email=user_obj.email,
        full_name=md.get("full_name"),
        is_admin=bool(md.get("is_admin") or app_md.get("is_admin")),
        onboarding_complete=bool(md.get("onboarding_complete", False)),
    )
    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=getattr(session, "expires_in", 3600) or 3600,
        user=user,
    )


def register(data: RegisterRequest, db=None) -> TokenResponse:
    settings = get_settings()

    # 1. Invitation policy (both modes)
    if settings.require_invitation_code and not data.invitation_code:
        raise AppError("Code d'invitation requis.", 400, code="invitation_required")

    # 2. Professional-email policy (both modes, preserved)
    if not settings.allow_freemail and not is_professional_email(data.email):
        raise AppError(
            "Merci d'utiliser ton email professionnel. Les adresses Gmail, Yahoo, "
            "Outlook, Hotmail, iCloud et similaires ne sont pas acceptées.",
            400, code="freemail_blocked",
        )

    # 3. Dispatch on auth mode. Local = self-contained dev auth (no Supabase).
    if settings.auth_mode == "local":
        from app.modules.auth import local

        return local.register(db, data)

    admin = admin_client()
    try:
        created = admin.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": data.full_name,
                "onboarding_complete": False,
            },
            "app_metadata": {"role": "user", "is_active": True},
        })
    except Exception as e:  # supabase raises library-specific errors
        msg = str(e).lower()
        if "already" in msg and "regist" in msg:
            raise AppError("Cet email est déjà utilisé.", 400, code="email_taken") from e
        logger.exception("Supabase create_user failed")
        raise AppError("Erreur lors de la création du compte. Réessaie.", 400,
                       code="register_failed") from e

    user_obj = created.user
    if not user_obj:
        raise AppError("Erreur lors de la création du compte.", 400, code="register_failed")

    # 3. Sign in to obtain tokens
    session = _sign_in(data.email, data.password)

    # 4. Analytics: first seen (non-blocking)
    analytics.record_signup(user_id=str(user_obj.id), email=data.email)

    return _token_response(session, user_obj)


def login(data: LoginRequest, db=None) -> TokenResponse:
    settings = get_settings()
    if settings.auth_mode == "local":
        from app.modules.auth import local

        return local.login(db, data)

    session = _sign_in(data.email, data.password)
    user_obj = session.user
    analytics.record_login(user_id=str(user_obj.id), email=user_obj.email)
    return _token_response(session, user_obj)


def _sign_in(email: str, password: str):
    try:
        resp = public_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as e:
        logger.warning("Sign-in failed for %s: %s", email, e)
        raise AppError("Email ou mot de passe invalide.", 401, code="bad_credentials") from e
    if not resp or not resp.session:
        raise AppError("Email ou mot de passe invalide.", 401, code="bad_credentials")
    return resp.session


def refresh(refresh_token: str, db=None) -> TokenResponse:
    """Nouvelle paire de jetons à partir d'un refresh token (les access tokens
    expirent en ~1h ; sans ça, l'app passait silencieusement en 401)."""
    settings = get_settings()
    if settings.auth_mode == "local":
        from app.modules.auth import local

        return local.refresh(db, refresh_token)

    try:
        resp = public_client().auth.refresh_session(refresh_token)
    except Exception as e:
        raise AppError("Session expirée — reconnecte-toi.", 401,
                       code="refresh_invalid") from e
    if not resp or not resp.session or not resp.user:
        raise AppError("Session expirée — reconnecte-toi.", 401, code="refresh_invalid")
    return _token_response(resp.session, resp.user)
