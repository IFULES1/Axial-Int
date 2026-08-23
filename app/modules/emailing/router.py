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
from app.modules.emailing.models import EmailSend, EmailSuppression

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


@router.get("/desinscription")
def desinscription(t: str, db: Session = Depends(get_db)) -> Response:
    """Désinscription en un clic, sans compte ni confirmation.

    Le jeton d'envoi sert d'identifiant : il désigne une adresse et une seule,
    et il est déjà dans l'email. Exiger une connexion pour se désinscrire,
    c'est garantir des plaintes pour spam à la place.
    """
    message = "Adresse retirée. Tu ne recevras plus d'email d'Axial."
    try:
        row = db.scalar(select(EmailSend).where(EmailSend.token == t))
        if row is None:
            message = "Ce lien n'est plus valide. Réponds à l'email et je te retire à la main."
        elif db.get(EmailSuppression, row.email) is None:
            db.add(EmailSuppression(email=row.email, reason="désinscription en un clic"))
            db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("Désinscription échouée (%s) : %s", t, e)
        message = "Une erreur est survenue. Réponds à l'email et je te retire à la main."
    return Response(
        content=("<!doctype html><meta charset=utf-8>"
                 "<title>Désinscription — Axial</title>"
                 "<div style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
                 "max-width:520px;margin:80px auto;color:#1b1d1e;line-height:1.6\">"
                 f"<p>{message}</p></div>"),
        media_type="text/html; charset=utf-8",
    )
