"""Veille endpoints — agents (watches), run history, skills, and RSS feeds."""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.watches import service, skills
from app.modules.watches.models import RssFeed

router = APIRouter(prefix="/watches", tags=["watches"])

_CADENCES = {"daily", "weekly", "manual"}
_SKILLS = {s.key for s in skills.list_skills()}


class WatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1)
    skill: str = "concurrentielle"
    analysis_type: str = "synthese_executive"
    cadence: str = "weekly"
    email_recipients: list[str] | None = None


class WatchOut(BaseModel):
    id: str
    name: str
    query: str
    skill: str
    analysis_type: str
    cadence: str
    status: str
    email_recipients: list | None
    last_run_at: dt.datetime | None
    next_run_at: dt.datetime | None


class WatchRunOut(BaseModel):
    id: str
    created_at: dt.datetime
    had_changes: bool
    delta_content: str
    full_content: str
    sources: list | None


class SkillOut(BaseModel):
    key: str
    name: str
    focus: str


class ActivityOut(BaseModel):
    id: str
    created_at: dt.datetime
    watch_name: str
    skill: str
    had_changes: bool
    delta_preview: str


class FeedIn(BaseModel):
    url: str = Field(min_length=4)
    title: str | None = None
    category: str = "general"


class FeedOut(BaseModel):
    id: str
    url: str
    title: str | None
    category: str
    active: bool


def _out(w) -> WatchOut:
    return WatchOut(id=str(w.id), name=w.name, query=w.query, skill=w.skill,
                    analysis_type=w.analysis_type, cadence=w.cadence, status=w.status,
                    email_recipients=w.email_recipients,
                    last_run_at=w.last_run_at, next_run_at=w.next_run_at)


# --- Skills (static) -------------------------------------------------------

@router.get("/skills", response_model=list[SkillOut])
def list_skills() -> list[SkillOut]:
    return [SkillOut(key=s.key, name=s.name, focus=s.focus) for s in skills.list_skills()]


@router.get("/activity", response_model=list[ActivityOut])
def activity(user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> list[ActivityOut]:
    return [
        ActivityOut(id=str(run.id), created_at=run.created_at, watch_name=name, skill=skill,
                    had_changes=run.had_changes, delta_preview=(run.delta_content or "")[:160])
        for run, name, skill in service.list_activity(db, user.id)
    ]


# --- RSS feeds (static) ----------------------------------------------------

@router.post("/feeds", response_model=FeedOut)
def add_feed(payload: FeedIn, user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> FeedOut:
    # Un même flux ajouté deux fois ferait remonter chaque article en double
    # dans les veilles. On rend l'existant plutôt que d'en créer un second.
    existant = db.scalar(select(RssFeed).where(
        RssFeed.user_id == uuid.UUID(user.id), RssFeed.url == payload.url))
    if existant is not None:
        return FeedOut(id=str(existant.id), url=existant.url, title=existant.title,
                       category=existant.category, active=existant.active)
    feed = RssFeed(id=uuid.uuid4(), user_id=uuid.UUID(user.id), url=payload.url,
                   title=payload.title, category=payload.category)
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return FeedOut(id=str(feed.id), url=feed.url, title=feed.title,
                   category=feed.category, active=feed.active)


@router.get("/feeds/catalogue")
def feeds_catalogue(user: AuthUser = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> list[dict]:
    """Flux proposés, avec l'indication de ceux déjà suivis par l'utilisateur.

    Renvoyer l'état d'abonnement évite au client de croiser deux listes, et
    surtout d'afficher « Ajouter » sur un flux déjà présent.
    """
    from app.modules.watches.catalogue import catalogue

    deja = {f.url for f in db.scalars(
        select(RssFeed).where(RssFeed.user_id == uuid.UUID(user.id)))}
    return [dict(f, suivi=f["url"] in deja) for f in catalogue()]


@router.get("/feeds", response_model=list[FeedOut])
def list_feeds(user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> list[FeedOut]:
    stmt = select(RssFeed).where(RssFeed.user_id == uuid.UUID(user.id)).order_by(RssFeed.created_at.desc())
    return [FeedOut(id=str(f.id), url=f.url, title=f.title, category=f.category, active=f.active)
            for f in db.scalars(stmt)]


@router.delete("/feeds/{feed_id}", status_code=204, response_class=Response)
def delete_feed(feed_id: str, user: AuthUser = Depends(get_current_user),
                db: Session = Depends(get_db)) -> Response:
    feed = db.get(RssFeed, uuid.UUID(feed_id))
    if feed and str(feed.user_id) == user.id:
        db.delete(feed)
        db.commit()
    return Response(status_code=204)


# --- Watches (agents) ------------------------------------------------------

@router.post("", response_model=WatchOut)
def create(payload: WatchIn, user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> WatchOut:
    cadence = payload.cadence if payload.cadence in _CADENCES else "weekly"
    skill = payload.skill if payload.skill in _SKILLS else skills.DEFAULT_SKILL
    w = service.create_watch(db, user.id, name=payload.name, query=payload.query,
                             analysis_type=payload.analysis_type, cadence=cadence,
                             skill=skill, email_recipients=payload.email_recipients)
    return _out(w)


@router.get("", response_model=list[WatchOut])
def list_all(user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> list[WatchOut]:
    return [_out(w) for w in service.list_watches(db, user.id)]


@router.get("/{watch_id}/runs", response_model=list[WatchRunOut])
def runs(watch_id: str, user: AuthUser = Depends(get_current_user),
         db: Session = Depends(get_db)) -> list[WatchRunOut]:
    return [
        WatchRunOut(id=str(r.id), created_at=r.created_at, had_changes=r.had_changes,
                    delta_content=r.delta_content, full_content=r.full_content, sources=r.sources)
        for r in service.list_runs(db, user.id, watch_id)
    ]


@router.post("/{watch_id}/pause", response_model=WatchOut)
def pause(watch_id: str, user: AuthUser = Depends(get_current_user),
          db: Session = Depends(get_db)) -> WatchOut:
    return _out(service.set_status(db, user.id, watch_id, "paused"))


@router.post("/{watch_id}/resume", response_model=WatchOut)
def resume(watch_id: str, user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> WatchOut:
    return _out(service.set_status(db, user.id, watch_id, "active"))


@router.post("/{watch_id}/run", response_model=WatchOut)
def run_now(watch_id: str, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> WatchOut:
    watch = service._own_watch(db, user.id, watch_id)
    service.run_watch(db, watch)
    db.refresh(watch)
    return _out(watch)


@router.delete("/{watch_id}", status_code=204, response_class=Response)
def delete(watch_id: str, user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> Response:
    service.delete_watch(db, user.id, watch_id)
    return Response(status_code=204)
