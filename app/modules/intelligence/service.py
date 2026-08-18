"""Intelligence service: projects, conversations, and the agent message loop.

`post_message` is where an agent actually runs: route to the right persona
(non-overlap), retrieve RAG context, generate a sourced answer via the web-search
provider, and persist the turn. Resilient by design — a provider outage yields a
clear degraded message, never a crash.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.intelligence import personas
from app.modules.intelligence.models import Conversation, Message, Project
from app.shared import llm_client

logger = logging.getLogger("axial.intelligence")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --- Projects --------------------------------------------------------------

def create_project(db: Session, user_id: str, name: str, description: str | None) -> Project:
    project = Project(id=uuid.uuid4(), user_id=uuid.UUID(user_id), name=name,
                      description=description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, user_id: str) -> list[Project]:
    stmt = (
        select(Project)
        .where(Project.user_id == uuid.UUID(user_id), Project.archived_at.is_(None))
        .order_by(Project.created_at.desc())
    )
    return list(db.scalars(stmt))


def _own_project(db: Session, user_id: str, project_id: str) -> Project:
    proj = db.get(Project, uuid.UUID(project_id))
    if not proj or str(proj.user_id) != user_id:
        raise AppError("Projet introuvable.", 404, code="not_found")
    return proj


# --- Conversations ---------------------------------------------------------

def create_conversation(db: Session, user_id: str, project_id: str,
                        title: str | None, default_agent: str | None) -> Conversation:
    _own_project(db, user_id, project_id)
    agent = default_agent if personas.get_persona(default_agent or "") else personas.DEFAULT_AGENT
    conv = Conversation(
        id=uuid.uuid4(), project_id=uuid.UUID(project_id), user_id=uuid.UUID(user_id),
        title=title or "Nouvelle conversation", default_agent=agent,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(db: Session, user_id: str, project_id: str) -> list[Conversation]:
    _own_project(db, user_id, project_id)
    stmt = (
        select(Conversation)
        .where(Conversation.project_id == uuid.UUID(project_id))
        .order_by(Conversation.created_at.desc())
    )
    return list(db.scalars(stmt))


def _own_conversation(db: Session, user_id: str, conversation_id: str) -> Conversation:
    conv = db.get(Conversation, uuid.UUID(conversation_id))
    if not conv or str(conv.user_id) != user_id:
        raise AppError("Conversation introuvable.", 404, code="not_found")
    return conv


def list_messages(db: Session, user_id: str, conversation_id: str) -> list[Message]:
    _own_conversation(db, user_id, conversation_id)
    stmt = (
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.created_at.asc())
    )
    return list(db.scalars(stmt))


# --- The agent message loop ------------------------------------------------

def _retrieve_context(query: str, user_id: str, top_k: int = 6):
    """Return (formatted_context, passages) so callers can both feed the LLM
    and surface the internal passages as citations."""
    try:
        from app.modules.rag import service as rag

        passages = rag.retrieve(query, user_id=user_id, top_k=top_k)
        return rag.format_context(passages), passages
    except Exception as e:
        logger.warning("RAG retrieval skipped: %s", e)
        return "", []


def _assemble_sources(query: str, web_results, doc_passages, top_k: int = 8):
    """Merge web results + internal passages into ONE relevance-ranked pool via
    Cohere rerank, then derive both the LLM context block and the citations from
    that single ordering — so web and internal compete on equal footing instead
    of being concatenated with non-comparable scores."""
    from app.shared import search as web_search

    pool: list[dict] = []
    for r in web_results:
        pool.append({
            "text": f"{r.title}\n{r.snippet}",
            "tag": f"(web : {r.domain})" if r.domain else "(web)",
            "body": r.snippet or r.title,
            "cite": {"title": r.title, "url": r.url, "domain": r.domain, "source": "web"},
            "key": f"web::{r.domain}::{r.title.strip().lower()}",
        })
    for p in doc_passages:
        if p.source not in ("kb", "user"):
            continue
        meta = p.meta or {}
        title = meta.get("title") or meta.get("filename") or "Base de connaissance"
        ref = meta.get("source") or meta.get("category") or ""
        pool.append({
            "text": p.text,
            "tag": f"(réf. interne : {ref} — {title})" if ref else f"(réf. interne : {title})",
            "body": p.text,
            "cite": {"title": title,
                     "source": "interne" if p.source == "kb" else "document",
                     "reference": ref},
            "key": f"doc::{title}",
        })
    if not pool:
        return "", []

    order = web_search.rerank_indices(query, [it["text"] for it in pool], top_k)
    ranked = [pool[i] for i, _ in order] or pool[:top_k]

    # Dedupe FIRST, then number — so the inline [N] markers the model emits from
    # the numbered context map 1:1 to the citations list the user sees. Numbering
    # the context and the (deduped) citations separately would desync them.
    deduped: list[dict] = []
    seen: set[str] = set()
    for it in ranked:
        if it["key"] in seen:
            continue
        seen.add(it["key"])
        deduped.append(it)

    lines = [f"[{n}] {it['tag']} {it['body']}" for n, it in enumerate(deduped, 1)]
    citations = [it["cite"] for it in deduped]
    return "\n\n".join(lines), citations


AGENT_MESSAGE_ACTION = "agent_message"


def post_message(db: Session, user_id: str, conversation_id: str, content: str,
                 agent_override: str | None = None, *, is_admin: bool = False) -> Message:
    conv = _own_conversation(db, user_id, conversation_id)
    requested = agent_override or conv.default_agent
    agent_key, redirect_note = personas.route(content, requested=requested)
    persona = personas.get_persona(agent_key) or personas.get_persona(personas.DEFAULT_AGENT)

    # Affordability check before spending the API call (admins bypass).
    from app.modules.billing import service as billing

    if not is_admin:
        chk = billing.check_credits(db, user_id, AGENT_MESSAGE_ACTION)
        if not chk["affordable"]:
            raise AppError(
                f"Crédits insuffisants ({chk['available']}/{chk['cost']}).",
                402, code="insufficient_credits",
            )

    # Persist the user's turn first.
    user_msg = Message(id=uuid.uuid4(), conversation_id=conv.id, role="user",
                       agent=agent_key, content=content)
    db.add(user_msg)

    from app.modules.memory import service as memory
    from app.shared import search as web_search

    company_context = memory.build_context(db, user_id)
    _, doc_passages = _retrieve_context(content, user_id)
    try:
        web_results = web_search.search(content, top_k=6)
    except Exception as e:
        logger.warning("Agent web search failed: %s", e)
        web_results = []

    # Rerank web + internal together → one relevance-ordered context + citations.
    combined_context, citations = _assemble_sources(content, web_results, doc_passages)

    parts = [p for p in (
        company_context,
        f"Sources (classées par pertinence) :\n{combined_context}" if combined_context else "",
    ) if p]
    prompt = (("\n\n".join(parts) + f"\n\nQuestion: {content}") if parts else content)

    from app.modules.pii.client import guard_outbound

    prompt = guard_outbound(prompt)

    degraded = False
    if not llm_client.generation_available():
        degraded = True
        answer = ("⚠️ Aucun moteur de génération n'est disponible pour le moment. "
                  "Réessaie plus tard.")
    else:
        # Rendre la mémoire PERCEPTIBLE : quand un contexte entreprise existe,
        # la réponse doit s'y ancrer explicitement (jamais un acteur générique).
        system = persona.full_system_prompt()
        if company_context:
            system += (
                "\n\nUn bloc « Contexte entreprise (mémoire) » est fourni dans le "
                "message. Ancre EXPLICITEMENT ta réponse dedans : ouvre par une "
                "phrase du type « Dans votre contexte — [nom de l'entreprise], "
                "[élément pertinent du profil]… », désigne l'entreprise par son nom, "
                "et adapte chaque recommandation à SA situation (positionnement, "
                "stade, défi) plutôt qu'à un acteur générique du secteur."
            )
        try:
            # Chat tier → Gemini (cheap/fast). AXIAL Recommande via the persona prompt.
            result = llm_client.generate(system=system,
                                         prompt=prompt, tier="chat", max_tokens=2500)
            answer = result.text
        except Exception as e:
            logger.warning("Agent generation failed: %s", e)
            degraded = True
            answer = "⚠️ La génération a échoué. Réessaie dans un instant."

    if redirect_note:
        answer = f"> ℹ️ {redirect_note}\n\n{answer}"

    assistant_msg = Message(id=uuid.uuid4(), conversation_id=conv.id, role="assistant",
                            agent=agent_key, content=answer, citations=citations or None)
    db.add(assistant_msg)

    conv.message_count += 2
    conv.last_message_at = _now()
    db.commit()
    db.refresh(assistant_msg)

    # Charge + track only on a real answer (never on degradation).
    if not degraded:
        from app.modules.analytics import client as analytics

        billing_res = billing.consume_credits(db, user_id, AGENT_MESSAGE_ACTION,
                                              is_admin=is_admin)
        analytics.increment_usage(user_id, agent_messages=1,
                                  credits=billing_res.get("charged", 0))

    return assistant_msg
