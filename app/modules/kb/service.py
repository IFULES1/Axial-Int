"""Service de la base de connaissance Axial (spec §5).

Réutilise EXACTEMENT le pipeline de `scripts/ingest_knowledge_base.py` et de
`app.modules.documents` : extraction (`extract_text`), découpage
(`chunk_text`), embeddings (`embeddings.embed_texts`), vecteurs
(`vector_store.upsert_chunks(..., collection=KB_COLLECTION)`). Rien n'est
dupliqué — seul le payload est enrichi d'un marqueur `kb=True` pour
distinguer, si besoin un jour, les points ajoutés depuis Pilotage de ceux du
lot d'ingestion initial (les deux restent lisibles de façon uniforme par
`rag.service.retrieve`, qui ne filtre pas dessus).

Backfill (spec §5) : `lister()` compare les `doc_id` distincts déjà présents
dans Qdrant aux lignes de `kb_documents` et crée les lignes manquantes — pour
que le lot ingéré en masse par le script (ou par une ancienne session) entre
dans le registre sans script de rattrapage séparé. Le scroll Qdrant est mis
en cache 10 minutes en mémoire de processus : c'est un inventaire du lot
existant, pas une source de vérité qui change à chaque appel.
"""
from __future__ import annotations

import logging
import time
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.documents.extract import SUPPORTED_EXTENSIONS, chunk_text, extract_text
from app.modules.kb.models import KbDocument
from app.modules.rag import embeddings, vector_store

logger = logging.getLogger("axial.kb")

DEFAULT_CATEGORIE = "07_ajouts-admin"

# Catégories existantes (dossiers de `data/knowledge_base/`) + la catégorie
# des ajouts faits depuis Pilotage. Une catégorie hors de cette liste est
# refusée : la lecture (rag.service, grounding) reste uniforme.
CATEGORIES = (
    "00_a-classer",
    "01_macro-institutionnel",
    "02_sectoriel",
    "03_reglementaire",
    "04_marche-benchmarks",
    "05_methodologie",
    "06_litterature-strategie",
    DEFAULT_CATEGORIE,
)

CONTENU_MIN_URL = 1500  # caractères — en-deçà, une page web n'apporte rien d'exploitable.
HTTP_TIMEOUT = 20.0
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_SCROLL_TTL_SECONDES = 600.0
_scroll_cache: dict = {"at": 0.0, "docs": None}


# --- backfill : inventaire Qdrant, mis en cache 10 minutes -----------------

def _scroll_qdrant() -> dict[str, dict]:
    """Points distincts de `knowledge_base`, groupés par `doc_id`.

    Payload seulement (`doc_id, title, filename, category, source`), pas de
    vecteurs : un scroll de 43 000+ points n'a pas besoin de rapatrier les
    embeddings pour compter des chunks.
    """
    vector_store.ensure_collection(vector_store.KB_COLLECTION)
    client = vector_store._client()
    docs: dict[str, dict] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=vector_store.KB_COLLECTION,
            limit=5000,
            with_payload=["doc_id", "title", "filename", "category", "source"],
            with_vectors=False,
            offset=offset,
        )
        for pt in points:
            payload = pt.payload or {}
            doc_id = payload.get("doc_id")
            if not doc_id:
                continue
            entry = docs.setdefault(doc_id, {
                "title": payload.get("title"),
                "filename": payload.get("filename"),
                "category": payload.get("category"),
                "source": payload.get("source"),
                "nb_chunks": 0,
            })
            entry["nb_chunks"] += 1
        if offset is None:
            break
    return docs


def _scroll_qdrant_cache() -> dict[str, dict]:
    now = time.monotonic()
    if _scroll_cache["docs"] is not None and now - _scroll_cache["at"] < _SCROLL_TTL_SECONDES:
        return _scroll_cache["docs"]
    docs = _scroll_qdrant()
    _scroll_cache["at"] = now
    _scroll_cache["docs"] = docs
    return docs


def _backfill(db: Session) -> None:
    distants = _scroll_qdrant_cache()
    if not distants:
        return
    existants = {r for (r,) in db.execute(select(KbDocument.doc_id))}
    manquants = [doc_id for doc_id in distants if doc_id not in existants]
    if not manquants:
        return
    for doc_id in manquants:
        info = distants[doc_id]
        categorie = info.get("category") or DEFAULT_CATEGORIE
        source_payload = info.get("source")
        # « source distincte » = différente de la catégorie utilisée comme
        # repli par le script de lot — sinon elle n'apporte rien à afficher.
        source = source_payload if (source_payload and source_payload != categorie) \
            else "ingestion initiale 08/2026"
        titre = info.get("title") or info.get("filename") or doc_id
        db.add(KbDocument(
            id=uuid.uuid4(), doc_id=doc_id, titre=titre, source=source,
            type="fichier", categorie=categorie, mime_type=None,
            nb_chunks=info.get("nb_chunks", 0), taille_octets=0,
            cree_par=None, statut="indexe", erreur=None,
        ))
    db.commit()


def lister(db: Session) -> list[KbDocument]:
    _backfill(db)
    stmt = select(KbDocument).order_by(KbDocument.created_at.desc())
    return list(db.scalars(stmt))


def categories_disponibles(db: Session) -> list[str]:
    presentes = {r for (r,) in db.execute(select(KbDocument.categorie).distinct())}
    return sorted(set(CATEGORIES) | presentes)


# --- ingestion : fichier / URL ----------------------------------------------

def _verifier_categorie(categorie: str) -> None:
    if categorie not in CATEGORIES:
        raise AppError(
            "Catégorie inconnue. Catégories valides : " + ", ".join(CATEGORIES) + ".",
            422, code="categorie_invalide",
        )


def _ligne_reutilisable(db: Session, doc_id: str) -> KbDocument | None:
    """Refuse une ré-ingestion d'un doc_id déjà indexé (`deja_indexe`).

    Un précédent essai en échec (`statut="echec"`) est en revanche réutilisé
    — la ligne existe déjà (ni doublon Qdrant, ni doublon de table), c'est
    juste une reprise.
    """
    existante = db.scalars(select(KbDocument).where(KbDocument.doc_id == doc_id)).first()
    if existante is not None:
        if existante.statut == "indexe":
            raise AppError("Ce document est déjà indexé dans la base de connaissance.",
                           409, code="deja_indexe")
        return existante
    if vector_store.has_document(doc_id, collection=vector_store.KB_COLLECTION):
        raise AppError("Ce document est déjà indexé dans la base de connaissance.",
                       409, code="deja_indexe")
    return None


def _indexer(db: Session, *, ligne: KbDocument | None, doc_id: str, titre: str,
            source: str, type_: str, categorie: str, mime_type: str | None,
            taille_octets: int, admin_id: str | None, text: str,
            filename: str | None) -> KbDocument:
    chunks = chunk_text(text)
    if ligne is None:
        ligne = KbDocument(id=uuid.uuid4(), doc_id=doc_id)
    ligne.titre = titre
    ligne.source = source
    ligne.type = type_
    ligne.categorie = categorie
    ligne.mime_type = mime_type
    ligne.taille_octets = taille_octets
    try:
        ligne.cree_par = uuid.UUID(admin_id) if admin_id else None
    except ValueError:
        ligne.cree_par = None

    payload = {"title": titre, "category": categorie, "source": source, "sector": ""}
    if filename:
        payload["filename"] = filename

    try:
        vectors = embeddings.embed_texts(chunks) if chunks else []
        n = vector_store.upsert_chunks(
            doc_id, "__kb__", chunks, vectors, collection=vector_store.KB_COLLECTION,
            extra_payload={**payload, "kb": True},
        )
    except Exception as e:  # noqa: BLE001 — on garde la trace, pas de demi-ingestion silencieuse
        logger.warning("Indexation KB échouée pour %s : %s", doc_id, e)
        ligne.statut = "echec"
        ligne.erreur = str(e)[:2000]
        ligne.nb_chunks = 0
        db.add(ligne)
        db.commit()
        raise AppError("Indexation momentanément indisponible — réessayez dans un instant.",
                       503, code="indexing_failed") from e

    ligne.statut = "indexe"
    ligne.erreur = None
    ligne.nb_chunks = n
    db.add(ligne)
    db.commit()
    db.refresh(ligne)
    return ligne


def ingerer_fichier(db: Session, admin_id: str, filename: str, data: bytes,
                    mime: str | None, categorie: str = DEFAULT_CATEGORIE) -> KbDocument:
    _verifier_categorie(categorie)
    lowered = (filename or "").lower()
    if not lowered.endswith(SUPPORTED_EXTENSIONS):
        raise AppError(
            "Format non pris en charge. Formats acceptés : "
            + ", ".join(e.lstrip(".").upper() for e in SUPPORTED_EXTENSIONS) + ".",
            422, code="unsupported_format",
        )
    if not data:
        raise AppError("Fichier vide.", 422, code="empty_file")

    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"kb:{filename}"))
    ligne = _ligne_reutilisable(db, doc_id)

    try:
        text = extract_text(filename, data)
    except Exception as e:
        raise AppError("Fichier illisible ou corrompu — vérifiez qu'il s'ouvre "
                       "correctement puis réessayez.", 422, code="extraction_failed") from e
    if not text:
        raise AppError("Aucun texte exploitable détecté dans ce fichier.",
                       422, code="extraction_failed")

    return _indexer(db, ligne=ligne, doc_id=doc_id, titre=filename, source=filename,
                    type_="fichier", categorie=categorie, mime_type=mime,
                    taille_octets=len(data), admin_id=admin_id, text=text,
                    filename=filename)


def _extraire_html(html: str) -> tuple[str, str]:
    """(titre, texte nettoyé) — retire script/style/nav, garde le reste."""
    import lxml.html as LH

    try:
        doc = LH.fromstring(html)
    except Exception:
        return "", ""
    titres = doc.xpath("//title/text()")
    titre = titres[0].strip() if titres and titres[0].strip() else ""
    for noeud in doc.xpath("//script|//style|//nav|//noscript"):
        noeud.drop_tree()
    texte = " ".join(doc.text_content().split())
    return titre, texte


def ingerer_url(db: Session, admin_id: str, url: str,
                categorie: str = DEFAULT_CATEGORIE) -> KbDocument:
    _verifier_categorie(categorie)
    url = (url or "").strip()
    if not url:
        raise AppError("URL requise.", 422, code="url_requise")

    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"kb:{url}"))
    ligne = _ligne_reutilisable(db, doc_id)

    try:
        reponse = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT,
                            follow_redirects=True)
        reponse.raise_for_status()
    except Exception as e:
        raise AppError("Impossible de récupérer cette URL.", 422, code="url_inaccessible") from e

    content_type = (reponse.headers.get("content-type") or "").lower()
    est_pdf = "pdf" in content_type or url.lower().split("?")[0].endswith(".pdf")
    if est_pdf:
        titre = url
        text = extract_text("document.pdf", reponse.content)
        mime = "application/pdf"
    else:
        titre_html, text = _extraire_html(reponse.text)
        titre = titre_html or url
        mime = content_type.split(";")[0].strip() or "text/html"

    if len(text) < CONTENU_MIN_URL:
        raise AppError(
            f"Contenu insuffisant pour l'indexation (moins de {CONTENU_MIN_URL} "
            "caractères extraits).", 422, code="contenu_insuffisant",
        )

    return _indexer(db, ligne=ligne, doc_id=doc_id, titre=titre, source=url, type_="url",
                    categorie=categorie, mime_type=mime, taille_octets=len(reponse.content),
                    admin_id=admin_id, text=text, filename=None)


def supprimer(db: Session, doc_id: str) -> None:
    ligne = db.scalars(select(KbDocument).where(KbDocument.doc_id == doc_id)).first()
    existe_qdrant = vector_store.has_document(doc_id, collection=vector_store.KB_COLLECTION)
    if ligne is None and not existe_qdrant:
        raise AppError("Document introuvable.", 404, code="not_found")
    # Vecteurs d'abord, ligne ensuite : jamais de ligne « indexée » qui pointe
    # vers des vecteurs déjà partis.
    vector_store.delete_document(doc_id, collection=vector_store.KB_COLLECTION)
    if ligne is not None:
        db.delete(ligne)
        db.commit()
