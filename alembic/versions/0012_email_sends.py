"""Journal des emails envoyés et suivi des ouvertures

Revision ID: 0012_emails
Revises: 0011_legacy
Create Date: 2026-08-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_emails"
down_revision: str | None = "0011_legacy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_sends",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("campaign", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_email_sends_token", "email_sends", ["token"], unique=True)
    op.create_index("ix_email_sends_email", "email_sends", ["email"])
    op.create_index("ix_email_sends_campaign", "email_sends", ["campaign"])


def downgrade() -> None:
    op.drop_table("email_sends")
