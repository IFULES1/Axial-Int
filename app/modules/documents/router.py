"""Document endpoints. All scoped to the authenticated user (UUID)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.documents import service

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentOut(BaseModel):
    id: str
    filename: str
    mime_type: str | None
    size_bytes: int
    chunk_count: int
    created_at: dt.datetime


def _to_out(doc) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id), filename=doc.filename, mime_type=doc.mime_type,
        size_bytes=doc.size_bytes, chunk_count=doc.chunk_count, created_at=doc.created_at,
    )


@router.post("/upload", response_model=DocumentOut)
async def upload(
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    data = await file.read()
    doc = service.ingest(db, user_id=user.id, filename=file.filename or "upload",
                         data=data, mime_type=file.content_type)
    return _to_out(doc)


@router.get("", response_model=list[DocumentOut])
def list_docs(
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    return [_to_out(d) for d in service.list_documents(db, user.id)]


@router.delete("/{doc_id}", status_code=204, response_class=Response)
def delete_doc(
    doc_id: str,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_document(db, user.id, doc_id)
    return Response(status_code=204)
