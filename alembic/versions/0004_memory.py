"""P-memory — company_profiles table

Revision ID: 0004_memory
Revises: 0003_billing_reports
Create Date: 2026-08-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_memory"
down_revision: str | None = "0003_billing_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("sector", sa.String(length=200), nullable=True),
        sa.Column("founding_year", sa.Integer(), nullable=True),
        sa.Column("funding_stage", sa.String(length=100), nullable=True),
        sa.Column("team_size", sa.String(length=50), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("target_market", sa.Text(), nullable=True),
        sa.Column("client_segment", sa.Text(), nullable=True),
        sa.Column("known_competitors", sa.Text(), nullable=True),
        sa.Column("main_challenge", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("company_profiles")
