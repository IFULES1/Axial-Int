"""Memory endpoints — company profile + onboarding status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.memory import service

router = APIRouter(prefix="/memory", tags=["memory"])


class ProfileIn(BaseModel):
    company_name: str | None = None
    website: str | None = None
    positioning: str | None = None
    sector: str | None = None
    founding_year: int | None = None
    funding_stage: str | None = None
    team_size: str | None = None
    country: str | None = None
    target_market: str | None = None
    client_segment: str | None = None
    known_competitors: str | None = None
    main_challenge: str | None = None
    language: str | None = None


class ProfileOut(ProfileIn):
    onboarding_complete: bool


def _to_out(profile, complete: bool) -> ProfileOut:
    data = {f: getattr(profile, f, None) for f in ProfileIn.model_fields}
    return ProfileOut(**data, onboarding_complete=complete)


@router.get("/profile", response_model=ProfileOut | None)
def get_profile(user: AuthUser = Depends(get_current_user),
                db: Session = Depends(get_db)) -> ProfileOut | None:
    profile = service.get_profile(db, user.id)
    if profile is None:
        return None
    return _to_out(profile, service.onboarding_complete(db, user.id))


@router.put("/profile", response_model=ProfileOut)
def upsert_profile(payload: ProfileIn, user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ProfileOut:
    profile = service.upsert_profile(db, user.id, payload.model_dump(exclude_unset=True))
    return _to_out(profile, service.onboarding_complete(db, user.id))


@router.get("/onboarding-status")
def onboarding_status(user: AuthUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> dict:
    return {"complete": service.onboarding_complete(db, user.id)}


class PrefillIn(BaseModel):
    url: str


@router.post("/prefill")
def prefill(payload: PrefillIn, _: AuthUser = Depends(get_current_user)) -> dict:
    """Onboarding helper: extract company_name/positioning/sector from a website."""
    return service.prefill_from_website(payload.url.strip())


@router.delete("/profile", status_code=204, response_class=Response)
def delete_profile(user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> Response:
    service.delete_profile(db, user.id)
    return Response(status_code=204)


class NotifPrefsIn(BaseModel):
    findings: bool | None = None
    weekly: bool | None = None
    marketing: bool | None = None


@router.get("/notifications")
def get_notifications(user: AuthUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> dict:
    return service.get_notification_prefs(db, user.id)


@router.put("/notifications")
def put_notifications(payload: NotifPrefsIn, user: AuthUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> dict:
    return service.set_notification_prefs(db, user.id, payload.model_dump())


class LangueIn(BaseModel):
    language: str


@router.put("/language")
def put_language(payload: LangueIn, user: AuthUser = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Enregistrer la langue de production choisie par l'utilisateur.

    Le sélecteur de l'interface ne peut pas se contenter du navigateur : le
    worker qui envoie les veilles n'y a pas accès, et un rapport doit sortir
    dans la bonne langue quel que soit l'appareil.
    """
    from app.shared import langue as lg

    service.upsert_profile(db, user.id, {"language": lg.normaliser(payload.language)})
    return {"language": lg.normaliser(payload.language)}
