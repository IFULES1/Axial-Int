"""Suivi des clics dans les emails.

Ajoute à `email_sends` la date du premier clic et le nombre de clics, écrits
par le webhook Resend (`POST /track/resend`, événement `email.clicked`). Un
email jamais cliqué garde `clicked_at` à NULL et `click_count` à 0 ; les
envois antérieurs à l'activation du suivi des clics restent à 0 — ils ne
sont pas « non cliqués », ils ne sont pas mesurés.

Revision ID: 0026_clics_emails
Revises: 0025_flux_rss
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_clics_emails"
down_revision = "0025_flux_rss"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_sends", sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_sends", sa.Column(
        "click_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_email_sends_provider_id", "email_sends", ["provider_id"])


def downgrade() -> None:
    op.drop_index("ix_email_sends_provider_id", table_name="email_sends")
    op.drop_column("email_sends", "click_count")
    op.drop_column("email_sends", "clicked_at")
