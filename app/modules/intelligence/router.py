"""Intelligence endpoints — projects, conversations, agents."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.intelligence import personas, service

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# --- schemas ---------------------------------------------------------------

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: dt.datetime


class ConversationIn(BaseModel):
    title: str | None = None
    default_agent: str | None = None


class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: str
    default_agent: str
    message_count: int
    last_message_at: dt.datetime | None = None


class MessageIn(BaseModel):
    content: str = Field(min_length=1)
    agent: str | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    agent: str | None
    content: str
    citations: list | None
    created_at: dt.datetime


class RouteIn(BaseModel):
    query: str = Field(min_length=1)
    agent: str | None = None


# --- agents ----------------------------------------------------------------

@router.get("/agents")
def list_agents() -> dict:
    return {"agents": [
        {"key": p.key, "name": p.name, "framework": p.framework}
        for p in personas.list_personas()
    ]}


@router.post("/agents/route")
def route_query(payload: RouteIn, _: AuthUser = Depends(get_current_user)) -> dict:
    agent_key, note = personas.route(payload.query, requested=payload.agent)
    persona = personas.get_persona(agent_key)
    return {"agent": agent_key, "name": persona.name if persona else None, "redirect_note": note}


# --- projects --------------------------------------------------------------

@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectIn, user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ProjectOut:
    p = service.create_project(db, user.id, payload.name, payload.description)
    return ProjectOut(id=str(p.id), name=p.name, description=p.description, created_at=p.created_at)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(user: AuthUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> list[ProjectOut]:
    return [
        ProjectOut(id=str(p.id), name=p.name, description=p.description, created_at=p.created_at)
        for p in service.list_projects(db, user.id)
    ]


# --- conversations ---------------------------------------------------------

@router.post("/projects/{project_id}/conversations", response_model=ConversationOut)
def create_conversation(project_id: str, payload: ConversationIn,
                        user: AuthUser = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> ConversationOut:
    c = service.create_conversation(db, user.id, project_id, payload.title, payload.default_agent)
    return ConversationOut(id=str(c.id), project_id=str(c.project_id), title=c.title,
                           default_agent=c.default_agent, message_count=c.message_count,
                           last_message_at=c.last_message_at)


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationOut])
def list_conversations(project_id: str, user: AuthUser = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> list[ConversationOut]:
    return [
        ConversationOut(id=str(c.id), project_id=str(c.project_id), title=c.title,
                        default_agent=c.default_agent, message_count=c.message_count,
                        last_message_at=c.last_message_at)
        for c in service.list_conversations(db, user.id, project_id)
    ]


# --- messages --------------------------------------------------------------

def _msg_out(m) -> MessageOut:
    return MessageOut(id=str(m.id), role=m.role, agent=m.agent, content=m.content,
                      citations=m.citations, created_at=m.created_at)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: str, user: AuthUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> list[MessageOut]:
    return [_msg_out(m) for m in service.list_messages(db, user.id, conversation_id)]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
def post_message(conversation_id: str, payload: MessageIn,
                 user: AuthUser = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> MessageOut:
    m = service.post_message(db, user.id, conversation_id, payload.content,
                             payload.agent, is_admin=user.is_admin)
    return _msg_out(m)
