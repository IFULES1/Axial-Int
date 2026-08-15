"""Analytics client — usage & KPI tracking in the separate ANALYTICS database.

Design goals:
  * **Never block or break the app.** Every call is best-effort; on any failure
    or if analytics is not configured, it logs and returns silently.
  * **Decoupled store.** Writes go to ANALYTICS_DATABASE_URL (a distinct
    Supabase project), not the app DB. If that URL is empty, this is a no-op.
  * **Extensible KPIs.** Arbitrary events land in the `events` table (JSONB
    properties), so new KPIs need no schema change.

Hosting of the analytics project is deferred; until ANALYTICS_DATABASE_URL is
set, these functions no-op cleanly and the rest of the app is unaffected.
"""
from __future__ import annotations

import datetime as dt
import logging
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import get_settings

logger = logging.getLogger("axial.analytics")


@lru_cache
def _engine() -> Engine | None:
    s = get_settings()
    if not (s.analytics_enabled and s.analytics_database_url):
        return None
    try:
        return create_engine(s.analytics_database_url, pool_pre_ping=True, future=True)
    except Exception:
        logger.exception("Analytics engine init failed; analytics disabled")
        return None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _period(now: dt.datetime | None = None) -> str:
    now = now or _now()
    return f"{now.year:04d}-{now.month:02d}"


def record_event(user_id: str, event_type: str, properties: dict | None = None) -> None:
    """Append a generic event. Basis for any future KPI. Best-effort."""
    eng = _engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO analytics.events (user_id, event_type, properties, ts) "
                    "VALUES (:uid, :etype, CAST(:props AS jsonb), :ts)"
                ),
                {
                    "uid": user_id,
                    "etype": event_type,
                    "props": _json(properties or {}),
                    "ts": _now(),
                },
            )
    except Exception:
        logger.warning("record_event(%s) failed", event_type, exc_info=True)


def _upsert_profile(conn, user_id: str, email: str | None, *, first_seen: bool) -> None:
    now = _now()
    conn.execute(
        text(
            "INSERT INTO analytics.user_profiles (user_id, email, first_seen_at, "
            "last_seen_at, signup_at, created_at, updated_at) "
            "VALUES (:uid, :email, :now, :now, :signup, :now, :now) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "last_seen_at = :now, updated_at = :now, "
            "email = COALESCE(analytics.user_profiles.email, EXCLUDED.email)"
        ),
        {"uid": user_id, "email": email, "now": now,
         "signup": now if first_seen else None},
    )


def record_signup(user_id: str, email: str | None = None) -> None:
    eng = _engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            _upsert_profile(conn, user_id, email, first_seen=True)
        record_event(user_id, "signup", {"email": email})
    except Exception:
        logger.warning("record_signup failed", exc_info=True)


def record_login(user_id: str, email: str | None = None) -> None:
    eng = _engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            _upsert_profile(conn, user_id, email, first_seen=False)
        record_event(user_id, "login", {})
    except Exception:
        logger.warning("record_login failed", exc_info=True)


def increment_usage(user_id: str, *, analyses: int = 0, credits: int = 0,
                    reports: int = 0, agent_messages: int = 0) -> None:
    """Bump the per-period usage counters (quota tracking). Best-effort."""
    eng = _engine()
    if eng is None:
        return
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO analytics.usage_counters "
                    "(user_id, period, analyses_run, credits_consumed, "
                    " reports_generated, agent_messages, updated_at) "
                    "VALUES (:uid, :period, :a, :c, :r, :m, :now) "
                    "ON CONFLICT (user_id, period) DO UPDATE SET "
                    "analyses_run = analytics.usage_counters.analyses_run + :a, "
                    "credits_consumed = analytics.usage_counters.credits_consumed + :c, "
                    "reports_generated = analytics.usage_counters.reports_generated + :r, "
                    "agent_messages = analytics.usage_counters.agent_messages + :m, "
                    "updated_at = :now"
                ),
                {"uid": user_id, "period": _period(), "a": analyses, "c": credits,
                 "r": reports, "m": agent_messages, "now": _now()},
            )
    except Exception:
        logger.warning("increment_usage failed", exc_info=True)


def _json(obj: dict) -> str:
    import json
    return json.dumps(obj, default=str)
