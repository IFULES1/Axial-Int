"""P6 — watches (scheduled analyses)

Revision ID: 0005_watches
Revises: 0004_memory
Create Date: 2026-08-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_watches"
down_revision: str | None = "0004_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("analysis_type", sa.String(length=64), nullable=False,
                  server_default="synthese_executive"),
        sa.Column("cadence", sa.String(length=20), nullable=False, server_default="weekly"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("email_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_watches_user_id", "watches", ["user_id"])
    op.create_index("ix_watches_next_run_at", "watches", ["next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_watches_next_run_at", table_name="watches")
    op.drop_index("ix_watches_user_id", table_name="watches")
    op.drop_table("watches")
