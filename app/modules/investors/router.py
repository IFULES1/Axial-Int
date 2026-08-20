"""Investor database endpoints — referentials and the raw mapping.

The narrative report lives in the analysis module (type
`cartographie_investisseurs`); these routes expose the underlying data so the
interface can show the ranked shortlist without paying for a generation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.investors import client, service

router = APIRouter(prefix="/investors", tags=["investors"])


@router.get("/status")
def status() -> dict:
    """Whether the investor database is wired up (no auth: used by the UI shell)."""
    return {"configured": client.configured()}


@router.get("/referentials")
def referentials(user: AuthUser = Depends(get_current_user)) -> dict:
    """Sector / stage / zone vocabularies of the investor database."""
    return service.referentials()


@router.get("/mapping")
def mapping(limit: int = 15, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> dict:
    """Ranked investor shortlist for the signed-in user's company profile."""
    from app.modules.analysis import service as analysis

    return service.map_for_profile(analysis._profile_dict(db, user.id), limit=limit)
