"""Intelligence endpoints — projects, conversations, agents."""
from __future__ import annotations

import datetime as dt
import logging

from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.intelligence import personas, service

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

logger = logging.getLogger("axial.intelligence")


# --- schemas ---------------------------------------------------------------

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: dt.datetime
    archived_at: dt.datetime | None = None


class ProjectPatch(BaseModel):
    """PATCH partiel : un champ absent (ou `null`) n'est pas modifié.
    Renommer en vide n'est donc pas exprimable ici — c'est voulu, et le
    service rend un 400 `nom_vide` si le nom n'est que des espaces."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None


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
    # Rangement du panneau. `pinned`/`archived` restent des booléens à
    # l'entrée (PATCH) et des dates en sortie : le front veut une bascule,
    # l'historique veut savoir quand.
    pinned_at: dt.datetime | None = None
    archived_at: dt.datetime | None = None


class ConversationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    pinned: bool | None = None
    archived: bool | None = None
    project_id: str | None = None


class EditionIn(BaseModel):
    content: str = Field(min_length=1)


class RechercheOut(BaseModel):
    conversation_id: str
    title: str
    project_id: str
    extrait: str
    # `None` quand la conversation a été trouvée par son TITRE : il n'y a pas
    # de message à surligner, le front ouvre simplement le fil.
    message_id: str | None = None
    created_at: dt.datetime | None = None


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

def _project_out(p) -> ProjectOut:
    return ProjectOut(id=str(p.id), name=p.name, description=p.description,
                      created_at=p.created_at, archived_at=p.archived_at)


@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectIn, user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ProjectOut:
    return _project_out(service.create_project(db, user.id, payload.name,
                                               payload.description))


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(inclure_archives: bool = False,
                  user: AuthUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> list[ProjectOut]:
    return [_project_out(p) for p in
            service.list_projects(db, user.id, inclure_archives=inclure_archives)]


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectPatch,
                   user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ProjectOut:
    """Renomme et/ou (dés)archive un dossier."""
    return _project_out(service.update_project(db, user.id, project_id,
                                               name=payload.name,
                                               archived=payload.archived))


@router.delete("/projects/{project_id}", status_code=204, response_class=Response)
def delete_project(project_id: str, user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> Response:
    """Supprime un dossier. Refusé (409) s'il reste des conversations actives."""
    service.delete_project(db, user.id, project_id)
    return Response(status_code=204)


# --- conversations ---------------------------------------------------------

def _conv_out(c) -> ConversationOut:
    return ConversationOut(id=str(c.id), project_id=str(c.project_id), title=c.title,
                           default_agent=c.default_agent, message_count=c.message_count,
                           last_message_at=c.last_message_at,
                           pinned_at=c.pinned_at, archived_at=c.archived_at)


@router.post("/projects/{project_id}/conversations", response_model=ConversationOut)
def create_conversation(project_id: str, payload: ConversationIn,
                        user: AuthUser = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> ConversationOut:
    return _conv_out(service.create_conversation(db, user.id, project_id,
                                                 payload.title, payload.default_agent))


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationOut])
def list_conversations(project_id: str, user: AuthUser = Depends(get_current_user),
                       db: Session = Depends(get_db),
                       inclure_archivees: bool = Query(default=False),
                       limit: int = Query(default=100, ge=1, le=200)
                       ) -> list[ConversationOut]:
    """Épinglées d'abord, puis par dernier message décroissant."""
    return [_conv_out(c) for c in service.list_conversations(
        db, user.id, project_id, inclure_archivees=inclure_archivees, limit=limit)]


# `search` est déclaré AVANT les routes en `/conversations/{id}` : FastAPI
# résout dans l'ordre de déclaration, et le jour où un `GET
# /conversations/{id}` existera, `search` se ferait sinon capter comme un
# identifiant de conversation.
# `q` a une valeur par défaut : sans elle, une requête sans `q` rendait un 422
# pydantic là où le contrat annonce un 400 `requete_trop_courte`.
@router.get("/conversations/search", response_model=list[RechercheOut])
def rechercher(q: str = Query(default=""),
               user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> list[RechercheOut]:
    """Cherche dans le contenu des messages et le titre des conversations
    non archivées. 20 résultats au plus, 3 caractères au moins."""
    return [RechercheOut(**r) for r in service.rechercher(db, user.id, q)]


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation(conversation_id: str, payload: ConversationPatch,
                        user: AuthUser = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> ConversationOut:
    """Renommer, épingler, archiver, déplacer de dossier — un seul endpoint."""
    return _conv_out(service.update_conversation(
        db, user.id, conversation_id, title=payload.title, pinned=payload.pinned,
        archived=payload.archived, project_id=payload.project_id))


@router.delete("/conversations/{conversation_id}", status_code=204,
               response_class=Response)
def delete_conversation(conversation_id: str,
                        user: AuthUser = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> Response:
    """Supprime la conversation et ses messages (cascade)."""
    service.delete_conversation(db, user.id, conversation_id)
    return Response(status_code=204)


# --- messages --------------------------------------------------------------

def _flux_sse(generateur):
    """Enveloppe un générateur SYNCHRONE du service en générateur ASYNC.

    C'est ce qui rend la détection de déconnexion fiable. Starlette n'appelle
    jamais `close()` sur un itérable synchrone (`iterate_in_threadpool`) : à
    l'annulation, le générateur du service était abandonné en plein `yield` et
    son `GeneratorExit` n'arrivait qu'au passage du ramasse-miettes, après que
    l'`AsyncExitStack` de FastAPI a fermé la session `get_db` — l'archivage de
    la réponse partielle tournait alors sur une session morte.

    Un générateur ASYNC, lui, est fermé par Starlette (`aclose`) dès que le
    client part. Le `finally` appelle `gen.close()` dans un thread du pool :
    `GeneratorExit` est levé au `yield` courant du service. À ce moment la
    session `get_db` de la requête est déjà fermée (mesuré sous uvicorn) :
    l'archivage de la réponse partielle ouvre donc sa PROPRE session
    (`_archiver_partiel`) et ne touche plus à celle de la requête.
    """
    from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

    async def _flux():
        try:
            async for evenement in iterate_in_threadpool(generateur):
                yield evenement
        finally:
            # Jamais d'exception hors de ce `finally` : il tourne pendant
            # l'annulation de la requête, et une erreur venue de l'archivage du
            # partiel y remplacerait le `CancelledError` par une trace 500
            # trompeuse — le client est déjà parti, personne ne la lirait.
            try:
                await run_in_threadpool(generateur.close)
            except Exception as e:  # noqa: BLE001
                logger.warning("Fermeture du flux SSE en échec : %s", e)

    return _flux()


def _reponse_sse(generateur) -> StreamingResponse:
    return StreamingResponse(
        _flux_sse(generateur),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_message(conversation_id: str, payload: MessageIn,
                   user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db),
                   x_idempotency_key: str | None = Header(default=None)
                   ) -> StreamingResponse:
    """Word-by-word answer (SSE). Same billing and persistence as the blocking route."""
    # 413 AVANT d'ouvrir le flux : un événement SSE d'erreur dans une réponse
    # 200 est invisible pour un client qui teste le code HTTP.
    service.verifier_longueur(payload.content)
    return _reponse_sse(service.stream_message(
        db, user.id, conversation_id, payload.content, payload.agent,
        is_admin=user.is_admin, document_ids=payload.document_ids,
        cle_idempotence=x_idempotency_key,
    ))


@router.post("/conversations/{conversation_id}/messages/{message_id}/regenerer")
def regenerer(conversation_id: str, message_id: str,
              user: AuthUser = Depends(get_current_user),
              db: Session = Depends(get_db),
              x_idempotency_key: str | None = Header(default=None)
              ) -> StreamingResponse:
    """Rejoue le dernier tour : SSE identique à `messages/stream`.

    La suppression est SYNCHRONE et hors du flux — un refus (message
    introuvable, pas le dernier) doit sortir en HTTP, pas en événement d'erreur
    dans une réponse 200. Le tour lui-même repart par `service.stream_message`,
    donc rien du pipeline n'est dupliqué ici.
    """
    question = service.preparer_regeneration(db, user.id, conversation_id,
                                             message_id, is_admin=user.is_admin)
    return _reponse_sse(service.stream_message(
        db, user.id, conversation_id, question, None, is_admin=user.is_admin,
        cle_idempotence=x_idempotency_key))


@router.post("/conversations/{conversation_id}/messages/{message_id}/editer")
def editer(conversation_id: str, message_id: str, payload: EditionIn,
           user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db),
           x_idempotency_key: str | None = Header(default=None)
           ) -> StreamingResponse:
    """Remplace un message envoyé et rejoue la suite : SSE identique à
    `messages/stream`."""
    service.verifier_longueur(payload.content)
    service.preparer_edition(db, user.id, conversation_id, message_id,
                             payload.content, is_admin=user.is_admin)
    return _reponse_sse(service.stream_message(
        db, user.id, conversation_id, payload.content, None,
        is_admin=user.is_admin, cle_idempotence=x_idempotency_key))


def _msg_out(m, *, is_admin: bool = False) -> MessageOut:
    return MessageOut(id=str(m.id), role=m.role, agent=m.agent, content=m.content,
                      citations=m.citations, viz=m.viz, created_at=m.created_at,
                      statut=m.statut, tokens_entree=m.tokens_entree,
                      tokens_sortie=m.tokens_sortie,
                      credits=service.credits_du_message(m),
                      cout_micro_eur=m.cout_micro_eur if is_admin else None)


@router.get("/conversations/{conversation_id}/messages",
            response_model=MessagesPage | list[MessageOut])
def list_messages(conversation_id: str, user: AuthUser = Depends(get_current_user),
                  db: Session = Depends(get_db),
                  limit: int | None = Query(default=None, ge=1, le=200),
                  before: str | None = Query(default=None)):
    """Fenêtre paginée, ordre chronologique. `before` = identifiant du plus
    ancien message déjà affiché, pour « Charger les messages précédents ».

    Sans `limit` : l'ancienne forme (liste brute). Un onglet ouvert avant le
    déploiement de Conversations v2 appelle encore cette route sans
    paramètre et attend un tableau — constaté le 11/09 chez une utilisatrice
    qui « n'avait plus accès à ses conversations » : le fil ne s'affichait
    plus, sans erreur visible.
    """
    if limit is None:
        items, _ = service.list_messages(db, user.id, conversation_id,
                                         limit=200, before=None)
        return [_msg_out(m, is_admin=user.is_admin) for m in items]
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
