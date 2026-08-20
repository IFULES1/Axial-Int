"""Rapports hérités de l'ancienne plateforme, restaurés à la connexion

Revision ID: 0011_legacy
Revises: 0010_notifs
Create Date: 2026-08-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_legacy"
down_revision: str | None = "0010_notifs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legacy_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("legacy_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("analysis_type", sa.String(length=64), nullable=True),
        sa.Column("legacy_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_for", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_legacy_reports_email", "legacy_reports", ["email"])


def downgrade() -> None:
    op.drop_index("ix_legacy_reports_email", table_name="legacy_reports")
    op.drop_table("legacy_reports")
