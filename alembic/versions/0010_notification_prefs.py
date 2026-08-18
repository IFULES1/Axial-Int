"""Préférences de notification email

Revision ID: 0010_notifs
Revises: 0009_subscriptions
Create Date: 2026-08-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_notifs"
down_revision: str | None = "0009_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_prefs",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("findings", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("weekly", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("marketing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notification_prefs")
