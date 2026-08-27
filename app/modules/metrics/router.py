"""Endpoint du tableau de bord — réservé à l'administration."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.metrics import service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/tableau")
def tableau(jours: int = 30, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> dict:
    # Ces chiffres portent le chiffre d'affaires et les coûts : ils ne sortent
    # pas du périmètre de l'administration.
    if not user.is_admin:
        raise AppError("Réservé à l'administration.", 403, code="forbidden")
    return service.tableau(db, jours=max(1, min(jours, 365)))


@router.get("/export")
def export(x_axial_export_token: str = Header(default=""),
           db: Session = Depends(get_db)) -> dict:
    """Export complet pour le classeur de pilotage.

    Authentifié par un jeton dédié plutôt qu'une session : un script planifié
    ne peut pas se reconnecter, et un JWT d'administration expire au bout
    d'une heure. Le jeton passe par un en-tête, jamais par l'URL — une chaîne
    de requête finit dans les journaux du serveur et du navigateur.
    """
    from app.config import get_settings

    attendu = get_settings().metrics_export_token
    if not attendu:
        raise AppError("Export non configuré.", 503, code="export_disabled")
    # Comparaison à temps constant : une comparaison naïve laisse deviner le
    # jeton caractère par caractère en mesurant le temps de réponse.
    if not hmac.compare_digest(x_axial_export_token or "", attendu):
        raise AppError("Jeton d'export invalide.", 403, code="forbidden")
    return service.export(db)
