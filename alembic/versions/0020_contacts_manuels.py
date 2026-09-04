"""Journal des contacts manuels avec les utilisateurs.

Les échanges WhatsApp, les emails personnels et les appels n'étaient tracés
nulle part : l'audit ne voyait que les campagnes automatiques, c'est-à-dire la
moitié du travail de relance.

Revision ID: 0020_contacts
Revises: 0019_couts
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_contacts"
down_revision = "0019_couts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts_manuels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        # L'email plutôt qu'un user_id : on recontacte aussi des gens qui n'ont
        # jamais créé de compte, et ce sont même les plus nombreux.
        sa.Column("email", sa.String(length=320), nullable=False, index=True),
        sa.Column("canal", sa.String(length=32), nullable=False),
        sa.Column("sens", sa.String(length=16), nullable=False),
        sa.Column("resume", sa.Text(), nullable=False),
        sa.Column("suite_prevue", sa.Text()),
        sa.Column("relance_le", sa.Date()),
        sa.Column("auteur", sa.String(length=120)),
        sa.Column("survenu_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_contacts_manuels_survenu", "contacts_manuels", ["survenu_le"])


def downgrade() -> None:
    op.drop_index("ix_contacts_manuels_survenu", table_name="contacts_manuels")
    op.drop_table("contacts_manuels")
