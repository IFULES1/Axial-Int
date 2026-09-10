"""Table des rendus : un spec Vega-Lite compilé par empreinte.

L'empreinte est l'identifiant public des images (`/viz/{empreinte}.svg`) :
64 caractères hexadécimaux, impossibles à deviner, et stables — le même
graphique a toujours la même adresse, ce qui rend le cache navigateur et le
cache email triviaux.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class VizRendu(Base):
    __tablename__ = "viz_rendus"

    empreinte: Mapped[str] = mapped_column(String(64), primary_key=True)
    vl: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
