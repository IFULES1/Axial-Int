"""Flux RSS visibles et testés (Task 2, spec §3).

Ajoute à `rss_feeds` les deux colonnes que la vérification (script
`scripts/tester_flux_rss.py` en local, route admin `POST
/watches/feeds/verifier`) écrit après chaque passage sur un flux : la date
de la dernière vérification et le message d'erreur s'il y en a eu un. Un
flux jamais vérifié garde les deux à NULL — la carte d'agent l'affiche comme
« inconnu », pas comme « erreur ».

Revision ID: 0025_flux_rss
Revises: 0024_sources_v2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_flux_rss"
down_revision = "0024_sources_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rss_feeds", sa.Column(
        "derniere_verification_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rss_feeds", sa.Column("derniere_erreur", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rss_feeds", "derniere_erreur")
    op.drop_column("rss_feeds", "derniere_verification_at")
