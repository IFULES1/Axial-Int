"""Coût réel de production d'un rapport.

Les tokens consommés étaient calculés à chaque génération puis jetés : aucune
métrique de rentabilité n'était calculable, et la marge restait une estimation.

Revision ID: 0018_cout
Revises: 0017_prefs
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_cout"
down_revision = "0017_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("tokens_entree", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("tokens_sortie", sa.Integer(), nullable=True))
    # Micro-euros entiers : sommer des flottants de coûts finit par dériver.
    op.add_column("reports", sa.Column("cout_micro_eur", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("modele", sa.String(length=64), nullable=True))
    op.add_column("reports", sa.Column("duree_secondes", sa.Integer(), nullable=True))


def downgrade() -> None:
    for c in ("duree_secondes", "modele", "cout_micro_eur",
              "tokens_sortie", "tokens_entree"):
        op.drop_column("reports", c)
