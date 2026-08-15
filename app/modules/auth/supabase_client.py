"""Thin Supabase client accessors.

Two clients: a public (anon) client for password sign-in, and an admin
(service-role) client for user creation. Kept lazy so the app boots even when
Supabase is not configured (e.g. unit tests that never call these).
"""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings
from app.errors import AppError


@lru_cache
def public_client() -> Client:
    s = get_settings()
    if not (s.supabase_url and s.supabase_anon_key):
        raise AppError("Supabase non configuré (URL/anon key).", 500,
                       code="auth_misconfigured")
    return create_client(s.supabase_url, s.supabase_anon_key)


@lru_cache
def admin_client() -> Client:
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_key):
        raise AppError("Supabase non configuré (URL/service key).", 500,
                       code="auth_misconfigured")
    return create_client(s.supabase_url, s.supabase_service_key)
