"""Coût des conversations et des exécutions de veille.

Seuls les rapports étaient instrumentés : le coût total mensuel restait
incalculable, et donc la rentabilité aussi.

Revision ID: 0019_couts
Revises: 0018_cout
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_couts"
down_revision = "0018_cout"
branch_labels = None
depends_on = None

_COLONNES = [
    ("tokens_entree", sa.Integer()),
    ("tokens_sortie", sa.Integer()),
    ("cout_micro_eur", sa.Integer()),
    ("modele", sa.String(length=64)),
]


def upgrade() -> None:
    for table in ("messages", "watch_runs"):
        for nom, typ in _COLONNES:
            op.add_column(table, sa.Column(nom, typ, nullable=True))
    # Coût de recherche : il vit à côté du coût modèle parce qu'il a une autre
    # cause (nombre d'angles × fournisseurs) et une autre courbe de croissance.
    op.add_column("reports", sa.Column("cout_recherche_micro_eur", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("appels_recherche", sa.Integer(), nullable=True))
    op.add_column("watch_runs", sa.Column("cout_recherche_micro_eur", sa.Integer(), nullable=True))
    op.add_column("watch_runs", sa.Column("appels_recherche", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("watch_runs", "appels_recherche")
    op.drop_column("watch_runs", "cout_recherche_micro_eur")
    op.drop_column("reports", "appels_recherche")
    op.drop_column("reports", "cout_recherche_micro_eur")
    for table in ("messages", "watch_runs"):
        for nom, _ in reversed(_COLONNES):
            op.drop_column(table, nom)
