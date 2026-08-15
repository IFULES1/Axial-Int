"""Veille (monitoring) domain models.

A `Watch` is a monitoring agent: a subject + a specialised veille skill + a
cadence. Each execution is a `WatchRun` (dated finding history). The agent keeps
a compact `rolling_state` it updates every run, so it builds on what it already
reported instead of re-analysing from scratch. `RssFeed` rows are the article
sources an agent combines with web search.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(64), default="synthese_executive")
    # Specialised veille skill (concurrentielle | reglementaire | financement | produit_tech).
    skill: Mapped[str] = mapped_column(String(48), default="concurrentielle")
    cadence: Mapped[str] = mapped_column(String(20), default="weekly")  # daily|weekly|manual
    status: Mapped[str] = mapped_column(String(20), default="active")   # active|paused
    email_recipients: Mapped[list | None] = mapped_column(JSONType)
    # Compact cumulative memory the agent maintains and updates each run.
    rolling_state: Mapped[str | None] = mapped_column(Text)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WatchRun(Base):
    """One execution of a watch — the dated finding history + memory snapshot."""

    __tablename__ = "watch_runs"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    watch_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("watches.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True)
    delta_content: Mapped[str] = mapped_column(Text, default="")   # what's NEW since last run
    full_content: Mapped[str] = mapped_column(Text, default="")    # refreshed full report
    rolling_state: Mapped[str | None] = mapped_column(Text)        # memory snapshot after this run
    sources: Mapped[list | None] = mapped_column(JSONType)         # web + rss sources used
    new_article_urls: Mapped[list | None] = mapped_column(JSONType)  # RSS urls consumed (dedupe)
    had_changes: Mapped[bool] = mapped_column(Boolean, default=True)


class RssFeed(Base):
    """An RSS/Atom source an agent tracks. Seeded per user; agents pick by category."""

    __tablename__ = "rss_feeds"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, index=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(48), default="general", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
