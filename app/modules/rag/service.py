"""RAG retrieval: embed the query, search user docs + knowledge base, format."""
from __future__ import annotations

import logging

from app.modules.rag import embeddings, vector_store
from app.modules.rag.vector_store import Passage

logger = logging.getLogger("axial.rag")


def retrieve(query: str, user_id: str, top_k: int = 8,
             include_kb: bool = True) -> list[Passage]:
    """Retrieve from the user's private docs AND the shared knowledge base,
    merged and ranked by similarity. One embedding, two collections."""
    vector = embeddings.embed_query(query)
    results = vector_store.search(vector, user_id=user_id, top_k=top_k,
                                  collection=vector_store.USER_COLLECTION)
    if include_kb:
        try:
            results += vector_store.search(vector, user_id=None, top_k=top_k,
                                           collection=vector_store.KB_COLLECTION)
        except Exception as e:
            logger.warning("Knowledge-base retrieval skipped: %s", e)
    results.sort(key=lambda p: p.score, reverse=True)
    return results[:top_k]


def format_context(passages: list[Passage]) -> str:
    """Numbered context block, tagging knowledge-base sources for the MODEL.

    « (base Axial : <titre>) » n'est vu QUE par le modèle, dans ce bloc de
    contexte — jamais par l'utilisateur : les citations qu'il voit passent
    par `grounding.assemble`, qui garde `source="interne"` (spec §5, décision
    du contrôleur du tour 1 : la base de connaissance n'est jamais nommée
    côté utilisateur ; le front, Task 6, choisit son propre libellé neutre).
    """
    if not passages:
        return ""
    lines = []
    for i, p in enumerate(passages, 1):
        tag = ""
        if p.source == "kb" and p.meta:
            titre = p.meta.get("title")
            if titre:
                tag = f" (base Axial : {titre})"
        lines.append(f"[{i}]{tag} {p.text}")
    return "\n\n".join(lines)
