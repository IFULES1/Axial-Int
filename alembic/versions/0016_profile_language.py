"""Langue de production des contenus sur le profil

Revision ID: 0016_langue
Revises: 0015_connections
Create Date: 2026-08-22
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_langue"
down_revision: str | None = "0015_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("company_profiles",
                  sa.Column("language", sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column("company_profiles", "language")
