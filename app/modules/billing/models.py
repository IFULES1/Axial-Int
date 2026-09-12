"""Billing model: per-user credit balance with three buckets.

Consumption order: trial (expiring) → free → purchased (never expires).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Action du premier rapport offert. Dupliquée depuis
# `app.modules.analysis.onboarding.ACTION` pour ne pas faire dépendre le
# billing du module d'analyse ; le test `test_rapports_v2` vérifie l'égalité.
ACTION_PREMIER_RAPPORT_OFFERT = "premier_rapport_offert"
INDEX_PREMIER_RAPPORT_OFFERT = "ux_credit_events_premier_rapport_offert"
_CLAUSE_OFFERT = text(f"action = '{ACTION_PREMIER_RAPPORT_OFFERT}'")


class CreditBalance(Base):
    __tablename__ = "credit_balances"

    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True)
    trial_credits: Mapped[int] = mapped_column(Integer, default=0)
    free_credits: Mapped[int] = mapped_column(Integer, default=0)
    purchased_credits: Mapped[int] = mapped_column(Integer, default=0)
    trial_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Date à laquelle l'import des rapports hérités a été tenté pour ce compte.
    # `restore_for` tournait à CHAQUE connexion (et à chaque réinitialisation de
    # mot de passe) : une requête sur `legacy_reports` par authentification,
    # pour un import qui ne peut se produire qu'une fois. Le marqueur vit ici
    # plutôt que dans une table `users_meta` — c'est la seule table qui existe
    # déjà pour tout compte, et elle est déjà lue à la connexion.
    legacy_verifie_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
    )

    def total(self) -> int:
        return self.trial_credits + self.free_credits + self.purchased_credits


class UserSubscription(Base):
    """One Stripe subscription per user — the app-side mirror of Stripe state.

    Updated by the webhook (checkout completed / invoice paid) and refreshed
    on-demand when the user opens the Credits tab. Source of truth for "does
    this account have an active plan?" (server-side card gate).
    """
    __tablename__ = "user_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64))
    plan_key: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="none")  # trialing|active|past_due|canceled|none
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    current_period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
    )


class CreditEvent(Base):
    """Append-only credit ledger: every grant (+) and debit (−), for the
    consumption history shown in Settings."""
    __tablename__ = "credit_events"
    # Un seul rapport offert par compte, garanti en base. La vérification
    # applicative de `onboarding.deja_offert` laissait passer deux appels
    # simultanés (deux onglets, un rejeu du front) : tous deux lisaient
    # « pas encore offert » avant que le premier n'écrive. Index PARTIEL : le
    # registre doit rester append-only pour toutes les autres actions — un
    # compte a bien plusieurs `agent_message` ou `pack`.
    __table_args__ = (
        Index(INDEX_PREMIER_RAPPORT_OFFERT, "user_id", unique=True,
              postgresql_where=_CLAUSE_OFFERT, sqlite_where=_CLAUSE_OFFERT),
    )

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, index=True)
    delta: Mapped[int] = mapped_column(Integer)          # +grant / −debit
    action: Mapped[str] = mapped_column(String(64))      # essai, pack, abonnement, agent_message…
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), index=True,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )
