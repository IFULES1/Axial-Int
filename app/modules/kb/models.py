"""ORM model for `kb_documents` — the app-DB registry of the knowledge base.

The chunk *embeddings* live in Qdrant (collection `knowledge_base`), keyed by
`doc_id`. This row is metadata only: what Pilotage lists, attributes and
deletes without talking to Qdrant directly.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    # Identifiant Qdrant (uuid5 du chemin/de la clé "kb:<nom>") — jamais régénéré.
    doc_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    titre: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # nom de fichier ou URL
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # "fichier" | "url"
    categorie: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nb_chunks: Mapped[int] = mapped_column(Integer, default=0)
    taille_octets: Mapped[int] = mapped_column(Integer, default=0)
    cree_par: Mapped[uuid.UUID | None] = mapped_column(SAUuid, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc), index=True,
    )
    statut: Mapped[str] = mapped_column(String(16), default="indexe")  # "indexe" | "echec"
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
