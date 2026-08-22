"""Pixel de suivi d'ouverture.

Sert toujours une image valide, quoi qu'il arrive : un pixel qui renvoie une
erreur laisse une case cassée dans le message du destinataire.
"""
from __future__ import annotations

import base64
import datetime as dt
import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.emailing.models import EmailSend

logger = logging.getLogger("axial.emailing")

router = APIRouter(prefix="/track", tags=["emailing"])

# GIF transparent de 1x1 pixel.
_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/{token}.gif")
def pixel(token: str, db: Session = Depends(get_db)) -> Response:
    try:
        row = db.scalar(select(EmailSend).where(EmailSend.token == token))
        if row is not None:
            row.open_count = (row.open_count or 0) + 1
            if row.opened_at is None:
                row.opened_at = dt.datetime.now(dt.timezone.utc)
            db.commit()
    except Exception as e:  # noqa: BLE001 — jamais d'image cassée chez le lecteur
        logger.warning("Suivi d'ouverture échoué (%s) : %s", token, e)
    return Response(
        content=_PIXEL, media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                 "Pragma": "no-cache"},
    )
