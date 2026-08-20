"""Auth endpoints.

  POST /auth/register  {email, password}  → create account + tokens
  POST /auth/login     {email, password}  → tokens
  GET  /auth/me                            → current user (from JWT)

Identity is the Supabase UUID. Freemail blocking and forced onboarding are
preserved (see service.py / security.py).
"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth import service
from app.modules.auth.schemas import AuthUser, LoginRequest, RegisterRequest, TokenResponse
from app.modules.auth.security import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token = service.register(payload, db)
    _restore_legacy(db, token)
    return token


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token = service.login(payload, db)
    _restore_legacy(db, token)
    return token


def _restore_legacy(db: Session, token: TokenResponse) -> None:
    """Bring back the reports this address produced on the previous platform.

    Runs on both register and login so a returning user gets them whichever way
    they come back. Best-effort by construction — never blocks authentication.
    """
    from app.modules.reports import legacy

    legacy.restore_for(db, token.user.id, token.user.email)
    legacy.grant_return_bonus(db, token.user.id, token.user.email)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return service.refresh(payload.refresh_token, db)


@router.get("/me", response_model=AuthUser)
def me(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthUser:
    # onboarding_complete is authoritative from the DB (the JWT claim is only a
    # snapshot from issue time), so the value stays correct after the profile
    # is created without needing to reissue the token.
    from app.modules.memory import service as memory

    user.onboarding_complete = memory.onboarding_complete(db, user.id)
    return user
