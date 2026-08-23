"""Préférences personnelles saisies dans Paramètres

Revision ID: 0017_prefs
Revises: 0016_langue
Create Date: 2026-08-23
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_prefs"
down_revision: str | None = "0016_langue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("company_profiles",
                  sa.Column("preferences", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("company_profiles", "preferences")
