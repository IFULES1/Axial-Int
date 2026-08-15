"""Document service: ingest, list, get, delete.

Ingestion is the full pipeline: extract text → persist the document row →
chunk → embed → upsert vectors to Qdrant. Deletion cascades: vectors first,
then the row, so we never leave orphaned embeddings.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.documents.extract import chunk_text, extract_text
from app.modules.documents.models import Document
from app.modules.rag import embeddings, vector_store


def ingest(db: Session, *, user_id: str, filename: str, data: bytes,
           mime_type: str | None = None) -> Document:
    text = extract_text(filename, data)
    if not text:
        raise AppError("Impossible d'extraire du texte de ce fichier.", 422,
                       code="extraction_failed")

    doc = Document(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        filename=filename,
        mime_type=mime_type,
        size_bytes=len(data),
        content=text,
    )
    db.add(doc)
    db.flush()  # assign PK before we key vectors to it

    chunks = chunk_text(text)
    if chunks:
        vectors = embeddings.embed_texts(chunks)
        doc.chunk_count = vector_store.upsert_chunks(
            str(doc.id), user_id, chunks, vectors
        )
    db.commit()
    db.refresh(doc)
    return doc


def list_documents(db: Session, user_id: str, limit: int = 100, offset: int = 0) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.user_id == uuid.UUID(user_id))
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def get_document(db: Session, user_id: str, doc_id: str) -> Document:
    doc = db.get(Document, uuid.UUID(doc_id))
    if not doc or str(doc.user_id) != user_id:
        raise AppError("Document introuvable.", 404, code="not_found")
    return doc


def delete_document(db: Session, user_id: str, doc_id: str) -> None:
    doc = get_document(db, user_id, doc_id)
    # Cascade: remove vectors first, then the row.
    vector_store.delete_document(str(doc.id))
    db.delete(doc)
    db.commit()
