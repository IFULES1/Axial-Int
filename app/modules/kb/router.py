"""Routes admin de la base de connaissance Axial (spec §5).

Toutes réservées à `get_current_admin` : la base de connaissance n'est
JAMAIS exposée à un utilisateur normal (aucune route `/kb/...` hors admin),
conformément à la décision de visibilité du 14/09 — seule Pilotage la gère.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_admin
from app.modules.kb import service
from app.modules.kb.models import KbDocument

router = APIRouter(prefix="/admin/kb", tags=["kb"])


class KbDocumentOut(BaseModel):
    id: str
    doc_id: str
    titre: str
    source: str
    type: str
    categorie: str
    mime_type: str | None
    nb_chunks: int
    taille_octets: int
    cree_par: str | None
    created_at: dt.datetime
    statut: str
    erreur: str | None


class KbListeOut(BaseModel):
    items: list[KbDocumentOut]
    categories: list[str]


class UrlIn(BaseModel):
    url: str = Field(min_length=1)
    categorie: str | None = None


def _to_out(ligne: KbDocument) -> KbDocumentOut:
    return KbDocumentOut(
        id=str(ligne.id), doc_id=ligne.doc_id, titre=ligne.titre, source=ligne.source,
        type=ligne.type, categorie=ligne.categorie, mime_type=ligne.mime_type,
        nb_chunks=ligne.nb_chunks, taille_octets=ligne.taille_octets,
        cree_par=str(ligne.cree_par) if ligne.cree_par else None,
        created_at=ligne.created_at, statut=ligne.statut, erreur=ligne.erreur,
    )


@router.get("", response_model=KbListeOut)
def lister(user: AuthUser = Depends(get_current_admin), db: Session = Depends(get_db)) -> KbListeOut:
    items = service.lister(db)
    return KbListeOut(items=[_to_out(i) for i in items],
                      categories=service.categories_disponibles(db))


@router.post("/fichiers", response_model=KbDocumentOut)
async def ajouter_fichier(
    fichier: UploadFile = File(...),
    categorie: str | None = Form(default=None),
    user: AuthUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> KbDocumentOut:
    data = await fichier.read()
    # Extraction + embeddings sont bloquants (CPU/réseau) : `run_in_threadpool`
    # les sort de l'event loop, comme les routes sync (`ajouter_url`,
    # `lister`, `supprimer`) le font déjà nativement (tour 1, Q1).
    ligne = await run_in_threadpool(
        service.ingerer_fichier, db, user.id, fichier.filename or "fichier", data,
        fichier.content_type, categorie or service.DEFAULT_CATEGORIE,
    )
    return _to_out(ligne)


@router.post("/urls", response_model=KbDocumentOut)
def ajouter_url(payload: UrlIn, user: AuthUser = Depends(get_current_admin),
                db: Session = Depends(get_db)) -> KbDocumentOut:
    ligne = service.ingerer_url(db, user.id, payload.url,
                                categorie=payload.categorie or service.DEFAULT_CATEGORIE)
    return _to_out(ligne)


@router.delete("/{doc_id}", status_code=204, response_class=Response)
def supprimer(doc_id: str, user: AuthUser = Depends(get_current_admin),
             db: Session = Depends(get_db)) -> Response:
    service.supprimer(db, doc_id)
    return Response(status_code=204)
