"""Document service: ingest, list, get, delete.

Ingestion is the full pipeline: extract text → persist the document row →
chunk → embed → upsert vectors to Qdrant. Deletion cascades: vectors first,
then the row, so we never leave orphaned embeddings.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import logging

from app.errors import AppError
from app.modules.documents.extract import SUPPORTED_EXTENSIONS, chunk_text, extract_text
from app.modules.documents.models import Document
from app.modules.rag import embeddings, vector_store

logger = logging.getLogger("axial.documents")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 Mo (nginx accepte 25m)


def ingest(db: Session, *, user_id: str, filename: str, data: bytes,
           mime_type: str | None = None) -> Document:
    lowered = (filename or "").lower()
    if not lowered.endswith(SUPPORTED_EXTENSIONS):
        raise AppError(
            "Format non pris en charge. Formats acceptés : "
            + ", ".join(e.lstrip(".").upper() for e in SUPPORTED_EXTENSIONS) + ".",
            422, code="unsupported_format",
        )
    if not data:
        raise AppError("Fichier vide.", 422, code="empty_file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError(f"Fichier trop volumineux (max {MAX_UPLOAD_BYTES // (1024*1024)} Mo).",
                       413, code="file_too_large")

    try:
        text = extract_text(filename, data)
    except AppError:
        raise
    except Exception as e:
        logger.warning("Extraction failed for %s: %s", filename, e)
        raise AppError("Fichier illisible ou corrompu — vérifie qu'il s'ouvre "
                       "correctement puis réessaie.", 422, code="extraction_failed") from e
    if not text:
        msg = ("Aucun texte détecté dans ce PDF (document scanné ?). "
               "L'OCR n'a rien pu en tirer — réessaie avec une version texte."
               if lowered.endswith(".pdf")
               else "Impossible d'extraire du texte de ce fichier.")
        raise AppError(msg, 422, code="extraction_failed")

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
        try:
            vectors = embeddings.embed_texts(chunks)
            doc.chunk_count = vector_store.upsert_chunks(
                str(doc.id), user_id, chunks, vectors
            )
        except Exception as e:
            # Never half-ingest: without vectors the doc wouldn't feed answers,
            # which is exactly the "mes documents ne servent à rien" bug.
            db.rollback()
            logger.warning("Indexation failed for %s: %s", filename, e)
            raise AppError("Indexation momentanément indisponible — réessaie dans "
                           "un instant.", 503, code="indexing_failed") from e
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
