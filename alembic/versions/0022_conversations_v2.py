"""Conversations v2 : socle backend.

Trois familles de colonnes, trois causes distinctes :

* `messages.statut` — un tour arrêté par l'utilisateur ou coupé après le
  premier token n'est pas une réponse complète et ne doit pas se lire comme
  telle dans l'historique ni être facturé.
* `messages.cle_idempotence` — un rejeu (réseau perdu, double clic) renvoyait
  une deuxième réponse et un deuxième débit. Unique en base : c'est la seule
  garantie qui survit à deux workers. Unicité **composite**
  `(conversation_id, cle_idempotence)` : une clé dérivée d'autre chose qu'un
  uuid (hash du message, compteur de composer) est réutilisable d'un fil à
  l'autre, et un index global y répondait par un `IntegrityError` 500.
* `conversations.resume_messages` — nombre de messages déjà couverts par
  `resume`. Sans ce curseur, le résumé roulant relisait tout le fil à chaque
  tour : au 100ᵉ message, ~35 k tokens d'entrée pour produire 900 tokens, et
  cela recommençait au tour suivant.
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


INDEX_IDEMPOTENCE = "ix_messages_conversation_cle_idempotence"


def _index_idempotence(*, creer: bool) -> None:
    """Crée (ou retire) l'unicité composite sans verrouiller `messages`.

    Index unique partiel impossible en Alembic portable : un index unique
    ordinaire suffit, les NULL n'entrent pas en collision en PostgreSQL.
    Composite : la clé n'est unique QUE dans sa conversation (voir en-tête).

    `CREATE UNIQUE INDEX` ordinaire prend un ACCESS EXCLUSIVE sur la table
    pendant toute la construction — lectures ET écritures bloquées. Instantané
    sur la volumétrie d'aujourd'hui, mais `messages` ne fera que grossir et
    c'est le seul point de cette migration qui ne soit pas instantané par
    construction. `CONCURRENTLY` ne peut pas tourner dans une transaction :
    d'où l'`autocommit_block`. SQLite (tests) ne connaît ni l'un ni l'autre.
    """
    postgres = op.get_bind().dialect.name == "postgresql"
    colonnes = ["conversation_id", "cle_idempotence"]

    def _appliquer() -> None:
        if creer:
            op.create_index(INDEX_IDEMPOTENCE, "messages", colonnes, unique=True,
                            **({"postgresql_concurrently": True} if postgres else {}))
        else:
            op.drop_index(INDEX_IDEMPOTENCE, table_name="messages",
                          **({"postgresql_concurrently": True} if postgres else {}))

    if postgres:
        with op.get_context().autocommit_block():
            _appliquer()
    else:
        _appliquer()


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
    _index_idempotence(creer=True)

    op.add_column("conversations", sa.Column("resume", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column(
        "resume_messages", sa.Integer(), nullable=False, server_default="0"))
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
    op.drop_column("conversations", "resume_messages")
    op.drop_column("conversations", "resume")

    _index_idempotence(creer=False)
    op.drop_column("messages", "appels_recherche")
    op.drop_column("messages", "cout_recherche_micro_eur")
    op.drop_column("messages", "cle_idempotence")
    op.drop_column("messages", "statut")
