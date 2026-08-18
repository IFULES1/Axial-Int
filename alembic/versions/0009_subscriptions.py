"""Suivi d'abonnement Stripe + journal de crédits

Revision ID: 0009_subscriptions
Revises: 0008_website
Create Date: 2026-08-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_subscriptions"
down_revision: str | None = "0008_website"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_subscriptions",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(length=64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=64), nullable=True),
        sa.Column("plan_key", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "credit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_credit_events_user_id", "credit_events", ["user_id"])
    op.create_index("ix_credit_events_created_at", "credit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_credit_events_created_at", table_name="credit_events")
    op.drop_index("ix_credit_events_user_id", table_name="credit_events")
    op.drop_table("credit_events")
    op.drop_table("user_subscriptions")
