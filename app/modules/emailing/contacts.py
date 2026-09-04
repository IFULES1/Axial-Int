"""Journal des contacts manuels.

L'audit d'activation ne voyait que les campagnes automatiques. Or l'essentiel
des relances passe par WhatsApp, par email personnel ou par téléphone : sans
ce journal, on ne sait pas qui a déjà été relancé, ni ce qui s'est dit, ni ce
qui avait été promis.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

CANAUX = ("whatsapp", "email", "appel", "linkedin", "rencontre", "autre")
SENS = ("sortant", "entrant")


class ContactManuel(Base):
    __tablename__ = "contacts_manuels"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True)
    canal: Mapped[str] = mapped_column(String(32))
    sens: Mapped[str] = mapped_column(String(16))
    resume: Mapped[str] = mapped_column(Text)
    suite_prevue: Mapped[str | None] = mapped_column(Text)
    relance_le: Mapped[dt.date | None] = mapped_column(Date)
    auteur: Mapped[str | None] = mapped_column(String(120))
    survenu_le: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )


def consigner(db, *, email: str, canal: str, sens: str, resume: str,
              survenu_le: dt.datetime | None = None,
              suite_prevue: str | None = None,
              relance_le: dt.date | None = None,
              auteur: str = "Miradie") -> ContactManuel:
    if canal not in CANAUX:
        raise ValueError(f"canal inconnu : {canal} (attendu : {', '.join(CANAUX)})")
    if sens not in SENS:
        raise ValueError(f"sens inconnu : {sens} (attendu : {', '.join(SENS)})")
    c = ContactManuel(
        email=email.lower().strip(), canal=canal, sens=sens, resume=resume.strip(),
        suite_prevue=(suite_prevue or "").strip() or None, relance_le=relance_le,
        auteur=auteur,
        survenu_le=survenu_le or dt.datetime.now(dt.timezone.utc),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
