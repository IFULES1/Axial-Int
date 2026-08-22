"""Réinitialisation de mot de passe — jetons maison, email envoyé par Resend.

Choix : ne pas déléguer au service d'emails de Supabase. On maîtrise ainsi le
texte, l'expéditeur et la délivrabilité (le domaine est vérifié chez Resend),
et le mécanisme fonctionne à l'identique en mode local.

Règles de sécurité appliquées :
  * le jeton n'est JAMAIS stocké en clair — seule son empreinte l'est ;
  * usage unique, expiration à 1 heure ;
  * la demande répond toujours la même chose, que l'adresse existe ou non
    (sinon le formulaire devient un révélateur de comptes) ;
  * toute demande antérieure encore valide est invalidée.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import secrets
import uuid

from sqlalchemy import DateTime, String, select
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import get_settings
from app.db import Base
from app.errors import AppError

logger = logging.getLogger("axial.auth.reset")

DUREE_VALIDITE = dt.timedelta(hours=1)


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )


def _empreinte(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _compte_existe(db: Session, email: str) -> bool:
    settings = get_settings()
    if settings.auth_mode == "local":
        from app.modules.auth.local import DevUser

        return db.scalar(select(DevUser.id).where(DevUser.email == email)) is not None
    from app.modules.auth.supabase_client import admin_client

    try:
        page = admin_client().auth.admin.list_users()
        users = page if isinstance(page, list) else getattr(page, "users", [])
        return any((getattr(u, "email", "") or "").lower() == email for u in users)
    except Exception as e:  # noqa: BLE001
        logger.warning("Vérification d'existence impossible : %s", e)
        return False


def demander(db: Session, email: str) -> None:
    """Créer un jeton et envoyer l'email. Silencieux si l'adresse est inconnue."""
    address = (email or "").strip().lower()
    if not address:
        return

    # Invalider les demandes précédentes encore actives.
    for ancien in db.scalars(select(PasswordReset).where(
            PasswordReset.email == address, PasswordReset.used_at.is_(None))):
        ancien.used_at = _now()

    if not _compte_existe(db, address):
        db.commit()
        logger.info("Demande de réinitialisation pour une adresse inconnue (ignorée)")
        return

    token = secrets.token_urlsafe(32)
    db.add(PasswordReset(email=address, token_hash=_empreinte(token),
                         expires_at=_now() + DUREE_VALIDITE))
    db.commit()
    _envoyer_email(address, token)


def _envoyer_email(email: str, token: str) -> None:
    import httpx

    settings = get_settings()
    lien = f"https://app.axial-ia.fr/?reinit={token}"
    texte = (
        "Bonjour,\n\n"
        "Tu as demandé à réinitialiser ton mot de passe Axial. Ce lien est valable "
        "une heure et ne fonctionne qu'une fois :\n\n"
        f"{lien}\n\n"
        "Si tu n'es pas à l'origine de cette demande, ignore simplement ce message : "
        "ton mot de passe actuel reste valable.\n\n"
        "Axial Intelligence"
    )
    if not settings.resend_api_key:
        logger.warning("Resend non configuré : lien de réinitialisation non envoyé")
        return
    try:
        httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}",
                     "Content-Type": "application/json"},
            json={"from": settings.mail_from or "Axial <no-reply@axial-ia.fr>",
                  "to": [email], "subject": "Réinitialiser ton mot de passe Axial",
                  "text": texte},
            timeout=20.0,
        ).raise_for_status()
    except Exception as e:  # noqa: BLE001 — ne jamais révéler l'échec au visiteur
        logger.warning("Envoi du lien de réinitialisation échoué : %s", e)


def reinitialiser(db: Session, token: str, nouveau_mot_de_passe: str) -> str:
    """Consommer le jeton et appliquer le nouveau mot de passe. Renvoie l'email."""
    if len(nouveau_mot_de_passe or "") < 8:
        raise AppError("Le mot de passe doit faire au moins 8 caractères.", 400,
                       code="password_too_short")

    ligne = db.scalar(select(PasswordReset).where(
        PasswordReset.token_hash == _empreinte(token or "")))
    if ligne is None or ligne.used_at is not None:
        raise AppError("Ce lien n'est plus valable. Redemande-en un.", 400,
                       code="reset_invalid")
    expire = ligne.expires_at
    if expire.tzinfo is None:
        expire = expire.replace(tzinfo=dt.timezone.utc)
    if expire < _now():
        raise AppError("Ce lien a expiré. Redemande-en un.", 400, code="reset_expired")

    _appliquer(db, ligne.email, nouveau_mot_de_passe)
    ligne.used_at = _now()
    db.commit()
    logger.info("Mot de passe réinitialisé pour %s", ligne.email)
    return ligne.email


def _appliquer(db: Session, email: str, mot_de_passe: str) -> None:
    settings = get_settings()
    if settings.auth_mode == "local":
        from app.modules.auth.local import DevUser
        from app.modules.auth.security import hash_password

        user = db.scalar(select(DevUser).where(DevUser.email == email))
        if user is None:
            raise AppError("Compte introuvable.", 404, code="not_found")
        user.password_hash = hash_password(mot_de_passe)
        return

    from app.modules.auth.supabase_client import admin_client

    client = admin_client()
    page = client.auth.admin.list_users()
    users = page if isinstance(page, list) else getattr(page, "users", [])
    cible = next((u for u in users
                  if (getattr(u, "email", "") or "").lower() == email), None)
    if cible is None:
        raise AppError("Compte introuvable.", 404, code="not_found")
    client.auth.admin.update_user_by_id(str(cible.id), {"password": mot_de_passe})
