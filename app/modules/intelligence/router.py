"""Intelligence endpoints — projects, conversations, agents."""
from __future__ import annotations

import datetime as dt

from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
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
    # Documents joints via le composer : injectés DIRECTEMENT dans le contexte
    # de ce message (garantis), en plus de leur indexation RAG durable.
    document_ids: list[str] | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    agent: str | None
    content: str
    citations: list | None
    viz: list | None = None
    created_at: dt.datetime
    # complet | partiel | degrade — le front pose un bandeau « Réponse
    # partielle » sur les deux derniers.
    statut: str = "complet"
    tokens_entree: int | None = None
    tokens_sortie: int | None = None
    # Crédits réellement débités : 0 sur un tour partiel ou dégradé.
    credits: int = 0
    # Coût réel de production. Donnée de marge : renseignée pour les admins
    # seulement, `None` pour tous les autres.
    cout_micro_eur: int | None = None


class MessagesPage(BaseModel):
    items: list[MessageOut]
    has_more: bool


class CoutOut(BaseModel):
    messages: int
    credits: int
    tokens_entree: int
    tokens_sortie: int
    cout_micro_eur: int | None = None


# --- agents ----------------------------------------------------------------

@router.get("/agents")
def list_agents(_: AuthUser = Depends(get_current_user)) -> dict:
    """Liste des agents disponibles. Authentifié comme le reste : il n'existe
    aucun usage anonyme de cette liste, et le frontend ne l'appelle que connecté.
    """
    return {"agents": [
        {"key": p.key, "name": p.name, "framework": p.framework}
        for p in personas.list_personas()
    ]}


# `POST /agents/route` (prévisualisation du routage, sans effet de bord) est
# supprimé : le frontend ne l'a jamais appelé et le badge d'agent porté par
# chaque réponse dit déjà qui a répondu.


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

def _detecteur_deconnexion(request: Request):
    """Rend une fonction SYNCHRONE qui dit si le client est parti.

    Le générateur du service est synchrone : Starlette l'itère dans un thread
    du pool (`iterate_in_threadpool`), donc `request.is_disconnected()` — une
    coroutine — doit être relancée sur la boucle d'événements depuis ce thread.
    C'est exactement ce que fait `anyio.from_thread.run`. Un générateur async
    aurait évité le détour mais aurait forcé à rendre asynchrone tout le
    pipeline (SQLAlchemy synchrone compris).
    """
    import anyio

    def _parti() -> bool:
        try:
            return bool(anyio.from_thread.run(request.is_disconnected))
        except Exception:  # noqa: BLE001 — un test raté ne doit jamais couper un flux sain
            return False

    return _parti


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_message(conversation_id: str, payload: MessageIn, request: Request,
                   user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db),
                   x_idempotency_key: str | None = Header(default=None)
                   ) -> StreamingResponse:
    """Word-by-word answer (SSE). Same billing and persistence as the blocking route."""
    # 413 AVANT d'ouvrir le flux : un événement SSE d'erreur dans une réponse
    # 200 est invisible pour un client qui teste le code HTTP.
    service.verifier_longueur(payload.content)
    generator = service.stream_message(
        db, user.id, conversation_id, payload.content, payload.agent,
        is_admin=user.is_admin, document_ids=payload.document_ids,
        cle_idempotence=x_idempotency_key,
        est_deconnecte=_detecteur_deconnexion(request),
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _msg_out(m, *, is_admin: bool = False) -> MessageOut:
    return MessageOut(id=str(m.id), role=m.role, agent=m.agent, content=m.content,
                      citations=m.citations, viz=m.viz, created_at=m.created_at,
                      statut=m.statut, tokens_entree=m.tokens_entree,
                      tokens_sortie=m.tokens_sortie,
                      credits=service.credits_du_message(m),
                      cout_micro_eur=m.cout_micro_eur if is_admin else None)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagesPage)
def list_messages(conversation_id: str, user: AuthUser = Depends(get_current_user),
                  db: Session = Depends(get_db),
                  limit: int = Query(default=50, ge=1, le=200),
                  before: str | None = Query(default=None)) -> MessagesPage:
    """Fenêtre paginée, ordre chronologique. `before` = identifiant du plus
    ancien message déjà affiché, pour « Charger les messages précédents »."""
    items, has_more = service.list_messages(db, user.id, conversation_id,
                                            limit=limit, before=before)
    return MessagesPage(items=[_msg_out(m, is_admin=user.is_admin) for m in items],
                        has_more=has_more)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
def post_message(conversation_id: str, payload: MessageIn,
                 user: AuthUser = Depends(get_current_user),
                 db: Session = Depends(get_db),
                 x_idempotency_key: str | None = Header(default=None)) -> MessageOut:
    service.verifier_longueur(payload.content)
    m = service.post_message(db, user.id, conversation_id, payload.content,
                             payload.agent, is_admin=user.is_admin,
                             document_ids=payload.document_ids,
                             cle_idempotence=x_idempotency_key)
    return _msg_out(m, is_admin=user.is_admin)


@router.get("/conversations/{conversation_id}/cout", response_model=CoutOut)
def cout_conversation(conversation_id: str, user: AuthUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> CoutOut:
    """Total du fil : crédits, tokens, et le coût € pour les admins seulement."""
    return CoutOut(**service.cout_conversation(db, user.id, conversation_id,
                                               is_admin=user.is_admin))


@router.get("/conversations/{conversation_id}/export")
def exporter(conversation_id: str, format: str = "md",
             user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """Exporte une conversation en Markdown ou en PDF.

    Le nom de fichier est dérivé du titre : un export nommé d'après un
    identifiant technique est inexploitable une fois dans un dossier.
    """
    import io
    import re
    import unicodedata

    from fastapi.responses import Response, StreamingResponse

    from app.modules.intelligence import export as expo

    if format not in ("md", "pdf"):
        raise AppError("Format inconnu (md ou pdf).", 400, code="bad_format")

    if format == "md":
        titre, contenu = expo.markdown(db, user.id, conversation_id)
        corps, media = contenu.encode("utf-8"), "text/markdown; charset=utf-8"
    else:
        titre, corps = expo.pdf(db, user.id, conversation_id)
        media = "application/pdf"

    # Les accents et espaces d'un titre cassent l'en-tête Content-Disposition.
    base = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:60] or "conversation"
    nom = f"{base}.{format}"

    if format == "pdf":
        return StreamingResponse(
            io.BytesIO(corps), media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{nom}"'})
    return Response(content=corps, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})
