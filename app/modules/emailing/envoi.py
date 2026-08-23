"""Envoi d'un email de cycle de vie : jeton, mise en page, journal, désinscription.

Centralisé ici parce que trois exigences doivent tenir ensemble à CHAQUE envoi :
la liste de suppression est consultée avant tout, le journal `email_sends` est
écrit avant l'appel réseau (un jeton déjà posé = pas de doublon si l'envoi
échoue à mi-parcours), et le pied de page porte toujours un lien de
désinscription réellement fonctionnel.
"""
from __future__ import annotations

import datetime as dt
import html as _h
import logging
import secrets

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.emailing.models import EmailSend, EmailSuppression

logger = logging.getLogger("axial.emailing.envoi")

EXPEDITEUR = '"Miradie @Axial" <miradie.buranturu@axial-ia.fr>'
REPONSE_A = "miradie.buranturu@axial-ia.fr"
BASE_PUBLIQUE = "https://app.axial-ia.fr/api"

_PIED = {
    "fr": "Tu ne veux plus recevoir ces messages ? {lien}",
    "en": "Would you rather not get these? {lien}",
}
_PIED_LIEN = {"fr": "Se désinscrire", "en": "Unsubscribe"}


def supprime(db: Session, email: str) -> bool:
    return db.get(EmailSuppression, email.lower().strip()) is not None


def deja_envoye(db: Session, email: str, campagne: str) -> bool:
    return db.scalar(
        select(EmailSend.id).where(EmailSend.email == email,
                                   EmailSend.campaign == campagne)
    ) is not None


def _jeton(db: Session, email: str, campagne: str) -> str:
    jeton = secrets.token_urlsafe(24)
    db.add(EmailSend(token=jeton, email=email, campaign=campagne))
    db.commit()
    return jeton


def en_html(texte: str, jeton: str, langue: str = "fr") -> str:
    """Texte enrichi, volontairement dépouillé.

    Une mise en page riche (images, boutons, colonnes) ferait basculer le
    message en onglet « Promotions » — exactement là où un email d'activation
    ne doit pas atterrir.
    """
    blocs = []
    for para in texte.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.isupper() and len(para) < 60:
            blocs.append('<p style="margin:26px 0 10px;font-weight:700;'
                         f'letter-spacing:.04em;font-size:13px;color:#555">{_h.escape(para)}</p>')
            continue
        corps = _h.escape(para).replace(
            "app.axial-ia.fr",
            '<a href="https://app.axial-ia.fr" style="color:#4F46D6">app.axial-ia.fr</a>', 1)
        blocs.append(f'<p style="margin:0 0 16px">{corps}</p>')

    lien = (f'<a href="{BASE_PUBLIQUE}/track/desinscription?t={jeton}" '
            f'style="color:#888">{_PIED_LIEN.get(langue, _PIED_LIEN["fr"])}</a>')
    pied = _PIED.get(langue, _PIED["fr"]).format(lien=lien)
    pixel = (f'<img src="{BASE_PUBLIQUE}/track/{jeton}.gif" width="1" height="1" '
             'alt="" style="display:block;border:0" />')
    return ('<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,'
            'Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;color:#1b1d1e;'
            'max-width:600px">' + "".join(blocs)
            + f'<p style="margin:28px 0 0;font-size:12px;color:#888">{pied}</p>'
            + pixel + "</div>")


def envoyer(db: Session, email: str, campagne: str, sujet: str, texte: str,
            langue: str = "fr", simulation: bool = True) -> tuple[bool, str]:
    """Envoie un email de séquence. Retourne (envoyé, motif/identifiant)."""
    email = email.lower().strip()
    if supprime(db, email):
        return False, "désinscrit"
    if deja_envoye(db, email, campagne):
        return False, "déjà envoyé"
    if simulation:
        return False, "simulation"

    cle = get_settings().resend_api_key
    if not cle:
        return False, "RESEND_API_KEY absente"

    # Le jeton est posé AVANT l'appel réseau : si Resend répond mal ou que le
    # process meurt, la campagne ne repartira pas une deuxième fois vers la
    # même personne. Un email manquant est un incident tolérable ; un doublon
    # chez un utilisateur qui hésite déjà ne l'est pas.
    jeton = _jeton(db, email, campagne)
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"},
            json={"from": EXPEDITEUR, "to": [email], "subject": sujet,
                  "text": texte, "html": en_html(texte, jeton, langue),
                  "reply_to": REPONSE_A},
            timeout=30.0,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Envoi %s vers %s échoué : %s", campagne, email, e)
        return False, f"erreur réseau : {e}"

    if r.status_code >= 300:
        logger.warning("Resend a refusé %s (%s) : %s", campagne, r.status_code, r.text[:200])
        return False, f"HTTP {r.status_code} : {r.text[:120]}"

    ligne = db.scalar(select(EmailSend).where(EmailSend.token == jeton))
    if ligne is not None:
        ligne.provider_id = (r.json().get("id") or "")[:64]
        ligne.sent_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    return True, ligne.provider_id if ligne else "envoyé"
