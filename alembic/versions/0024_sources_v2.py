"""Sources v2 (5) : base de connaissance Axial — table `kb_documents`.

La base de connaissance vit déjà dans Qdrant (collection `knowledge_base`,
remplie par `scripts/ingest_knowledge_base.py`) : cette migration ajoute
seulement le REGISTRE applicatif qui permet à Pilotage (Task 6) de lister,
attribuer et supprimer des documents sans parler directement à Qdrant.

`doc_id` est l'identifiant Qdrant (uuid5 du chemin ou de la clé `kb:<nom>`) :
la table ne le régénère jamais, elle le recopie tel quel (`unique=True`
depuis le départ, pour qu'un doublon d'ingestion échoue tout de suite au lieu
de désynchroniser Qdrant et la table). Elle est **remplie au premier
listage** (spec §5) à partir des points déjà présents dans Qdrant — cette
migration ne fait qu'ouvrir la table vide.

Revision ID: 0024_sources_v2
Revises: 0023_rapports_v2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_sources_v2"
down_revision = "0023_rapports_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("doc_id", sa.String(length=64), nullable=False),
        sa.Column("titre", sa.String(length=500), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("categorie", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("nb_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("taille_octets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cree_par", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("statut", sa.String(length=16), nullable=False,
                  server_default="indexe"),
        sa.Column("erreur", sa.Text(), nullable=True),
    )
    op.create_index("ux_kb_documents_doc_id", "kb_documents", ["doc_id"], unique=True)
    op.create_index("ix_kb_documents_categorie", "kb_documents", ["categorie"])
    op.create_index("ix_kb_documents_created_at", "kb_documents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_kb_documents_created_at", table_name="kb_documents")
    op.drop_index("ix_kb_documents_categorie", table_name="kb_documents")
    op.drop_index("ux_kb_documents_doc_id", table_name="kb_documents")
    op.drop_table("kb_documents")
