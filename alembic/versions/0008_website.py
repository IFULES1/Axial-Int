"""Onboarding V2 — company website on the profile

Revision ID: 0008_website
Revises: 0007_veille
Create Date: 2026-08-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_website"
down_revision: str | None = "0007_veille"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("company_profiles", sa.Column("website", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("company_profiles", "website")
