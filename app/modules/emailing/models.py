"""Journal des emails sortants + suivi des ouvertures.

Le suivi passe par un pixel servi par notre propre API plutôt que par le
prestataire d'envoi : la donnée reste chez Axial, et le mécanisme survit à un
changement de fournisseur.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Integer, String
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EmailSend(Base):
    __tablename__ = "email_sends"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    campaign: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str | None] = mapped_column(String(64))
    sent_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    opened_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    open_count: Mapped[int] = mapped_column(Integer, default=0)


class EmailSuppression(Base):
    """Adresses à ne plus jamais contacter, toutes campagnes confondues.

    Une désinscription doit survivre aux campagnes : la vérifier au moment de
    l'envoi est le seul endroit qui garantit qu'aucune liste future ne la perde.
    """
    __tablename__ = "email_suppressions"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )
