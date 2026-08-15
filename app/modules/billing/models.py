"""Billing model: per-user credit balance with three buckets.

Consumption order: trial (expiring) → free → purchased (never expires).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Integer
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CreditBalance(Base):
    __tablename__ = "credit_balances"

    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True)
    trial_credits: Mapped[int] = mapped_column(Integer, default=0)
    free_credits: Mapped[int] = mapped_column(Integer, default=0)
    purchased_credits: Mapped[int] = mapped_column(Integer, default=0)
    trial_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
    )

    def total(self) -> int:
        return self.trial_credits + self.free_credits + self.purchased_credits
