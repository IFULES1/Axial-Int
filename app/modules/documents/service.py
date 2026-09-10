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
        raise AppError("Fichier illisible ou corrompu — vérifiez qu'il s'ouvre "
                       "correctement puis réessayez.", 422, code="extraction_failed") from e
    if not text:
        msg = ("Aucun texte détecté dans ce PDF (document scanné ?). "
               "L'OCR n'a rien pu en tirer — réessayez avec une version texte."
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
            raise AppError("Indexation momentanément indisponible — réessayez dans "
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
    # Un identifiant qui n'est pas un UUID vaut « introuvable » : il vient de
    # l'URL, et un `ValueError` non capté y répondait par un 500.
    try:
        cle = uuid.UUID(doc_id)
    except ValueError:
        raise AppError("Document introuvable.", 404, code="not_found") from None
    doc = db.get(Document, cle)
    if not doc or str(doc.user_id) != user_id:
        raise AppError("Document introuvable.", 404, code="not_found")
    return doc


def reindex(db: Session, user_id: str, doc_id: str) -> Document:
    """Relance l'indexation d'un document déjà importé, sur le texte stocké.

    Seul cas utile de « rafraîchir le RAG » : un import dont l'indexation a
    échoué (`chunk_count = 0`) est en base mais invisible pour les réponses —
    c'est le « mes documents ne servent à rien ». Le texte, lui, a bien été
    extrait à l'import : rien à réuploader, on repart de `documents.content`.

    Les vecteurs existants sont supprimés AVANT le nouvel envoi : les
    identifiants de points sont dérivés de `(doc_id, index de chunk)`, donc une
    réindexation d'un texte devenu plus court laisserait la queue de l'ancienne
    version en place et la ferait ressortir dans les réponses.
    """
    doc = get_document(db, user_id, doc_id)
    text = doc.content or ""
    if not text.strip():
        raise AppError("Ce document ne contient aucun texte exploitable — "
                       "réimportez-le dans une version texte.",
                       422, code="extraction_failed")

    chunks = chunk_text(text)
    vector_store.delete_document(str(doc.id))
    try:
        vectors = embeddings.embed_texts(chunks)
        doc.chunk_count = vector_store.upsert_chunks(
            str(doc.id), user_id, chunks, vectors
        )
    except Exception as e:
        # Les anciens vecteurs sont déjà partis : `chunk_count = 0` dit la
        # vérité (document non indexé) et garde le bouton « Réindexer » visible.
        # Un rollback aurait laissé un compteur qui promet des vecteurs
        # disparus.
        doc.chunk_count = 0
        db.commit()
        logger.warning("Réindexation failed for %s: %s", doc.filename, e)
        raise AppError("Indexation momentanément indisponible — réessayez dans "
                       "un instant.", 503, code="indexing_failed") from e
    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, user_id: str, doc_id: str) -> None:
    doc = get_document(db, user_id, doc_id)
    # Cascade: remove vectors first, then the row.
    vector_store.delete_document(str(doc.id))
    db.delete(doc)
    db.commit()
