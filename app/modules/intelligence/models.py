"""Intelligence domain models: Project → Conversation → Message."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# JSONB on PostgreSQL, plain JSON elsewhere (tests on SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="Nouvelle conversation")
    # `auto` : le routeur réel choisit l'agent à chaque tour. Market Scanner
    # imposé par défaut faisait répondre PESTEL à des questions de pricing.
    default_agent: Mapped[str] = mapped_column(String(64), default="auto")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    # Résumé roulant du fil au-delà de 8 messages (mémoire de conversation).
    resume: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_message_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Rangement du panneau : épinglé remonte en tête, archivé sort de la liste.
    pinned_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    agent: Mapped[str | None] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list | None] = mapped_column(JSONType)
    # Visualisations du message (forme `viz.pipeline.Viz`), préparées à
    # l'archivage pour que l'historique se recharge sans recompiler.
    viz: Mapped[list | None] = mapped_column(JSONType)
    # Coût de production. Nullable : les lignes antérieures au 25/08 n'ont
    # jamais été mesurées, et un zéro les ferait passer pour gratuites.
    tokens_entree: Mapped[int | None] = mapped_column(Integer)
    tokens_sortie: Mapped[int | None] = mapped_column(Integer)
    cout_micro_eur: Mapped[int | None] = mapped_column(Integer)
    modele: Mapped[str | None] = mapped_column(String(64))
    # Coût de recherche web du tour, séparé du coût modèle : autre cause
    # (fournisseurs actifs × requêtes) et autre courbe de croissance.
    cout_recherche_micro_eur: Mapped[int | None] = mapped_column(Integer)
    appels_recherche: Mapped[int | None] = mapped_column(Integer)
    # complet | partiel | degrade. `partiel` (arrêt utilisateur ou coupure
    # après le premier token) et `degrade` ne sont pas facturés.
    statut: Mapped[str] = mapped_column(String(16), default="complet")
    # Clé fournie par le client (un uuid par envoi) : un rejeu renvoie le
    # message déjà produit au lieu d'en générer — et de débiter — un second.
    cle_idempotence: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
