"""Signalements sur un rapport (spec §3).

« Votre avis » renvoyait vers un Google Form : le retour partait chez Google,
sans l'identifiant du rapport concerné, et personne ne pouvait relire le
document incriminé. La table garde le lien rapport ↔ signalement, ce qui rend
le retour actionnable — « relire le rapport X » plutôt que « un utilisateur
trouve que c'est faux ».

Modèle seulement : les routes et la notification arrivent en Task 3.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Motifs proposés par le formulaire. Liste fermée côté API (Task 3) : un champ
# libre seul rend le tri impossible, un champ fermé seul perd le cas non prévu
# — d'où `autre` + `commentaire`.
MOTIFS = ("contenu_faux", "hors_sujet", "incomplet", "autre")


class ReportFeedback(Base):
    __tablename__ = "report_feedback"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    # CASCADE : un rapport supprimé emporte ses signalements. Le retour n'a
    # aucun sens sans le document qu'il commente.
    report_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("reports.id", ondelete="CASCADE"),
        index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, index=True, nullable=False)
    # Note 1-5 facultative : le formulaire s'ouvre aussi depuis « Votre avis »,
    # où il n'y a pas de problème à signaler.
    note: Mapped[int | None] = mapped_column(Integer)
    motif: Mapped[str] = mapped_column(String(32), nullable=False)
    commentaire: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), index=True,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )
