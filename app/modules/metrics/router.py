"""Endpoint du tableau de bord — réservé à l'administration."""
from __future__ import annotations

from fastapi import APIRouter, Depends
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
