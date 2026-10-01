"""Pixel de suivi d'ouverture, désinscription, webhook Resend (clics).

Sert toujours une image valide, quoi qu'il arrive : un pixel qui renvoie une
erreur laisse une case cassée dans le message du destinataire.
"""
from __future__ import annotations

import base64
import datetime as dt
import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
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


def _signature_valide(secret: str, msg_id: str, horodatage: str, corps: bytes,
                      signatures: str) -> bool:
    """Vérification Svix (schéma utilisé par Resend pour signer ses webhooks).

    Contenu signé : « id.horodatage.corps », HMAC-SHA256 avec le secret
    décodé (partie après « whsec_ »). L'en-tête peut porter plusieurs
    signatures « v1,<base64> » séparées par des espaces, une par secret actif
    pendant une rotation. Un horodatage à plus de 5 minutes est refusé, pour
    qu'un événement intercepté ne puisse pas être rejoué plus tard.
    """
    import hashlib
    import hmac
    import time

    if not (secret and msg_id and horodatage and signatures):
        return False
    try:
        if abs(time.time() - int(horodatage)) > 300:
            return False
        # Le secret se copie souvent sans le préfixe « whsec_ » ni le « = »
        # final du base64 : on accepte les deux formes plutôt que de refuser
        # en silence tous les événements (cas réel du 01/10).
        brut = secret.strip().removeprefix("whsec_")
        cle = base64.b64decode(brut + "=" * (-len(brut) % 4))
    except (ValueError, IndexError):
        return False
    attendu = base64.b64encode(hmac.new(
        cle, f"{msg_id}.{horodatage}.".encode() + corps, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(attendu, s.split(",", 1)[1])
               for s in signatures.split() if s.startswith("v1,"))


@router.post("/resend")
async def webhook_resend(request: Request, db: Session = Depends(get_db)) -> dict:
    """Événements Resend : clics, plaintes pour spam, rebonds définitifs.

    * `email.clicked` → `clicked_at` (premier clic) et `click_count` ;
    * `email.complained` → l'adresse passe en liste de suppression ;
    * `email.bounced` définitif → idem : insister sur une adresse morte
      dégrade la réputation du domaine pour tous les autres envois.

    L'envoi est retrouvé par l'identifiant Resend (`provider_id`), déjà
    enregistré à chaque envoi. Un événement inconnu ou sans envoi associé est
    acquitté sans erreur : Resend réessaierait sinon pendant des heures.
    """
    from app.config import get_settings

    corps = await request.body()
    if not _signature_valide(get_settings().resend_webhook_secret,
                             request.headers.get("svix-id", ""),
                             request.headers.get("svix-timestamp", ""),
                             corps, request.headers.get("svix-signature", "")):
        raise AppError("Signature de webhook invalide.", 401, code="signature_invalide")

    import json

    try:
        evt = json.loads(corps)
    except ValueError:
        return {"ok": True, "ignore": "corps illisible"}
    type_evt = evt.get("type", "")
    data = evt.get("data") or {}
    row = db.scalar(select(EmailSend).where(EmailSend.provider_id == data.get("email_id")))

    if type_evt == "email.clicked" and row is not None:
        row.click_count = (row.click_count or 0) + 1
        if row.clicked_at is None:
            row.clicked_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    elif type_evt in ("email.complained", "email.bounced"):
        definitif = type_evt == "email.complained" or \
            ((data.get("bounce") or {}).get("type", "").lower() == "permanent")
        destinataires = [row.email] if row is not None else [
            str(a).lower().strip() for a in (data.get("to") or [])]
        if definitif:
            motif = "plainte pour spam" if type_evt == "email.complained" else "rebond définitif"
            for adresse in destinataires:
                if adresse and db.get(EmailSuppression, adresse) is None:
                    db.add(EmailSuppression(email=adresse, reason=motif))
            db.commit()
    return {"ok": True}


@router.get("/desinscription")
def desinscription(t: str, db: Session = Depends(get_db)) -> Response:
    """Désinscription en un clic, sans compte ni confirmation.

    Le jeton d'envoi sert d'identifiant : il désigne une adresse et une seule,
    et il est déjà dans l'email. Exiger une connexion pour se désinscrire,
    c'est garantir des plaintes pour spam à la place.
    """
    message = "Adresse retirée. Vous ne recevrez plus d'email d'Axial."
    try:
        row = db.scalar(select(EmailSend).where(EmailSend.token == t))
        if row is None:
            message = "Ce lien n'est plus valide. Répondez à l'email et nous vous retirerons à la main."
        elif db.get(EmailSuppression, row.email) is None:
            db.add(EmailSuppression(email=row.email, reason="désinscription en un clic"))
            db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("Désinscription échouée (%s) : %s", t, e)
        message = "Une erreur est survenue. Répondez à l'email et nous vous retirerons à la main."
    return Response(
        content=("<!doctype html><meta charset=utf-8>"
                 "<title>Désinscription Axial</title>"
                 "<div style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
                 "max-width:520px;margin:80px auto;color:#1b1d1e;line-height:1.6\">"
                 f"<p>{message}</p></div>"),
        media_type="text/html; charset=utf-8",
    )
