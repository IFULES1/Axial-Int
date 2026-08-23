"""Company profile — the cross-cutting Memory layer.

One profile per user. Injected automatically into every Workspace/Agent session
so the user never re-explains their context. Its existence also gates onboarding
(forced: no workspace access until a profile with a company name exists).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(300))
    positioning: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(String(200))
    founding_year: Mapped[int | None] = mapped_column(Integer)
    funding_stage: Mapped[str | None] = mapped_column(String(100))
    team_size: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(100))
    target_market: Mapped[str | None] = mapped_column(Text)
    client_segment: Mapped[str | None] = mapped_column(Text)
    known_competitors: Mapped[str | None] = mapped_column(Text)
    main_challenge: Mapped[str | None] = mapped_column(Text)
    # Langue de production des contenus (rapports, réponses, veilles).
    language: Mapped[str | None] = mapped_column(String(5))
    # Préférences personnelles saisies dans Paramètres (nom affiché,
    # modèle par défaut, citations strictes…). Stockées ici plutôt que dans
    # le navigateur : elles doivent suivre l'utilisateur d'un appareil à
    # l'autre et être lisibles par le serveur qui produit les rapports.
    preferences: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class NotificationPrefs(Base):
    """Préférences de notification email — une ligne par utilisateur.

    Absence de ligne = valeurs par défaut (findings/weekly activés). Les types
    « mentions/commentaires » ont été retirés du produit (décision 18/08)."""
    __tablename__ = "notification_prefs"

    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True)
    findings: Mapped[bool] = mapped_column(Boolean, default=True)   # emails de veille
    weekly: Mapped[bool] = mapped_column(Boolean, default=True)     # récap hebdo
    marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
