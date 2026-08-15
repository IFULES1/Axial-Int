"""Auth request/response schemas. Identity is UUID-only (no legacy integer IDs)."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    invitation_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthUser(BaseModel):
    id: str  # Supabase UUID — the single identity across the whole app
    email: EmailStr
    full_name: str | None = None
    is_admin: bool = False
    onboarding_complete: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int = 3600
    user: AuthUser
