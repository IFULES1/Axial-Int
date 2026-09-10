"""Visualisations : rendus par empreinte, colonnes viz sur reports et messages.

Revision ID: 0021_viz
Revises: 0020_contacts
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021_viz"
down_revision = "0020_contacts"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # Un rendu par empreinte SHA-256 du spec Vega-Lite compilé : sert de cache,
    # d'identifiant public d'image (app, email) et de journal de ce qui a été
    # réellement tracé.
    op.create_table(
        "viz_rendus",
        sa.Column("empreinte", sa.String(64), primary_key=True),
        sa.Column("vl", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("reports", sa.Column("viz", _JSON))
    op.add_column("messages", sa.Column("viz", _JSON))


def downgrade() -> None:
    op.drop_column("messages", "viz")
    op.drop_column("reports", "viz")
    op.drop_table("viz_rendus")
