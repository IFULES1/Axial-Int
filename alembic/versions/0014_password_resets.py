"""Jetons de réinitialisation de mot de passe

Revision ID: 0014_resets
Revises: 0013_suppress
Create Date: 2026-08-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_resets"
down_revision: str | None = "0013_suppress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_password_resets_email", "password_resets", ["email"])
    op.create_index("ix_password_resets_token", "password_resets", ["token_hash"],
                    unique=True)


def downgrade() -> None:
    op.drop_table("password_resets")
