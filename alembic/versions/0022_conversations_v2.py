"""Conversations v2 : socle backend.

Trois familles de colonnes, trois causes distinctes :

* `messages.statut` — un tour arrêté par l'utilisateur ou coupé après le
  premier token n'est pas une réponse complète et ne doit pas se lire comme
  telle dans l'historique ni être facturé.
* `messages.cle_idempotence` — un rejeu (réseau perdu, double clic) renvoyait
  une deuxième réponse et un deuxième débit. Unique en base : c'est la seule
  garantie qui survit à deux workers.
* `messages.cout_recherche_micro_eur` / `appels_recherche` — le coût de
  recherche des conversations était compté `0` dans `metrics`, alors que
  chaque tour interroge tous les fournisseurs actifs.
* `conversations.resume`, `pinned_at`, `archived_at` — mémoire de fil et
  rangement du panneau.
* `conversations.default_agent` passe par défaut à `auto` : le routeur réel
  choisit l'agent, plutôt que Market Scanner imposé à toute conversation.

Revision ID: 0022_conversations_v2
Revises: 0021_viz
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_conversations_v2"
down_revision = "0021_viz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column(
        "statut", sa.String(length=16), nullable=False,
        server_default="complet"))
    op.add_column("messages", sa.Column(
        "cle_idempotence", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column(
        "cout_recherche_micro_eur", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column(
        "appels_recherche", sa.Integer(), nullable=True))
    # Index unique partiel impossible en Alembic portable : un index unique
    # ordinaire suffit, les NULL n'entrent pas en collision en PostgreSQL.
    op.create_index("ix_messages_cle_idempotence", "messages",
                    ["cle_idempotence"], unique=True)

    op.add_column("conversations", sa.Column("resume", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column(
        "pinned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column(
        "archived_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("conversations", "default_agent",
                    existing_type=sa.String(length=64),
                    existing_nullable=False,
                    server_default="auto")


def downgrade() -> None:
    op.alter_column("conversations", "default_agent",
                    existing_type=sa.String(length=64),
                    existing_nullable=False,
                    server_default="market_scanner")
    op.drop_column("conversations", "archived_at")
    op.drop_column("conversations", "pinned_at")
    op.drop_column("conversations", "resume")

    op.drop_index("ix_messages_cle_idempotence", table_name="messages")
    op.drop_column("messages", "appels_recherche")
    op.drop_column("messages", "cout_recherche_micro_eur")
    op.drop_column("messages", "cle_idempotence")
    op.drop_column("messages", "statut")
