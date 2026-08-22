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
from dataclasses import dataclass

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
    """Pool unifié web + interne (implémentation partagée avec les rapports)."""
    from app.shared import grounding

    return grounding.assemble(query, web_results, doc_passages, top_k)


AGENT_MESSAGE_ACTION = "agent_message"


_LONG_ANSWER_SIGNALS = (
    "analyse", "détail", "approfondi", "compare", "comparaison", "stratégie",
    "plan ", "rapport", "étude", "cartographie", "explique", "structure",
    "recommandation", "roadmap", "benchmark",
)


def _wants_long_answer(query: str) -> bool:
    """Conversation libre : Sonnet (tier report) pour les demandes de fond,
    Gemini (tier chat) pour les échanges courts."""
    q = query.lower()
    return len(q) > 220 or any(s in q for s in _LONG_ANSWER_SIGNALS)


def _attached_docs_context(db: Session, user_id: str,
                           document_ids: list[str] | None) -> str:
    """Contenu des documents joints au message — injecté tel quel dans le
    prompt (comme une pièce jointe), sans dépendre du rerank RAG."""
    if not document_ids:
        return ""
    from app.modules.documents import service as documents

    parts: list[str] = []
    for doc_id in document_ids[:3]:  # au plus 3 pièces jointes par message
        try:
            doc = documents.get_document(db, user_id, doc_id)
        except Exception:
            continue
        body = (doc.content or "")[:8000]
        parts.append(f"### Document joint : {doc.filename}\n{body}")
    if not parts:
        return ""
    return ("## Documents joints par l'utilisateur (source PRIORITAIRE pour ce "
            "message)\n" + "\n\n".join(parts))


@dataclass
class _Turn:
    """Everything a turn needs once the context is assembled — shared by the
    blocking path (post_message) and the streaming path (stream_message) so the
    two can never drift apart."""
    conv: Conversation
    agent_key: str
    redirect_note: str | None
    system: str
    prompt: str
    citations: list
    tier: str
    max_tokens: int
    blocked_answer: str | None = None  # set when no LLM is available at all


def _prepare_turn(db: Session, user_id: str, conversation_id: str, content: str,
                  agent_override: str | None, *, is_admin: bool,
                  document_ids: list[str] | None) -> _Turn:
    conv = _own_conversation(db, user_id, conversation_id)
    requested = agent_override or conv.default_agent
    # Conversation libre : AUCUN routing d'agent — discussion directe avec le LLM
    # (Gemini réponses courtes / Sonnet réponses longues). Les personas spécialisées
    # ne s'appliquent que sur choix explicite de l'utilisateur.
    free_chat = requested == personas.AUTO
    if free_chat:
        agent_key, redirect_note = personas.AXIAL_CONSEIL.key, None
    else:
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
    attached_context = _attached_docs_context(db, user_id, document_ids)

    # Vitesse : très courts messages en conversation libre (« merci », « ok »)
    # → pas de recherche du tout, réponse immédiate du LLM.
    trivial = free_chat and len(content.strip()) < 25 and not attached_context

    if trivial:
        doc_passages, web_results = [], []
    else:
        # RAG et recherche web en PARALLÈLE (elles ne partagent pas la session DB).
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_docs = ex.submit(_retrieve_context, content, user_id)
            f_web = ex.submit(web_search.search, content, 6)
            try:
                web_results = f_web.result()
            except Exception as e:
                logger.warning("Agent web search failed: %s", e)
                web_results = []
            _, doc_passages = f_docs.result()

    # Espace Notion de l'utilisateur : ses pages rejoignent le même pool que le
    # web et ses documents, donc elles sont rerankées et citées comme le reste.
    if not trivial:
        try:
            from app.modules.integrations import notion_context

            doc_passages = list(doc_passages) + notion_context.passages_pour(
                db, user_id, content)
        except Exception as e:  # noqa: BLE001 — un outil injoignable ne bloque rien
            logger.warning("Espace Notion indisponible : %s", e)

    # Rerank web + internal together → one relevance-ordered context + citations.
    combined_context, citations = _assemble_sources(content, web_results, doc_passages)

    parts = [p for p in (
        company_context,
        attached_context,
        f"Sources (classées par pertinence) :\n{combined_context}" if combined_context else "",
    ) if p]
    prompt = (("\n\n".join(parts) + f"\n\nQuestion: {content}") if parts else content)

    from app.modules.pii.client import guard_outbound

    prompt = guard_outbound(prompt)

    if not llm_client.generation_available():
        return _Turn(conv=conv, agent_key=agent_key, redirect_note=redirect_note,
                     system="", prompt=prompt, citations=citations, tier="chat",
                     max_tokens=0,
                     blocked_answer=("⚠️ Aucun moteur de génération n'est disponible "
                                     "pour le moment. Réessaie plus tard."))

    # Conversation libre = discussion naturelle (pas de bloc « AXIAL Recommande »
    # imposé) ; agents spécialisés = persona complète avec cadre d'analyse.
    system = persona.system_prompt if free_chat else persona.full_system_prompt()
    # Rendre la mémoire PERCEPTIBLE : quand un contexte entreprise existe,
    # la réponse doit s'y ancrer explicitement (jamais un acteur générique).
    if company_context:
        system += (
            "\n\nUn bloc « Contexte entreprise (mémoire) » est fourni dans le "
            "message. Ancre EXPLICITEMENT ta réponse dedans : ouvre par une "
            "phrase du type « Dans votre contexte — [nom de l'entreprise], "
            "[élément pertinent du profil]… », désigne l'entreprise par son nom, "
            "et adapte chaque recommandation à SA situation (positionnement, "
            "stade, défi) plutôt qu'à un acteur générique du secteur."
        )
    # Conversation libre : Gemini (chat) pour le court, Sonnet (report) pour le
    # long. Agents spécialisés : tier chat (comportement historique).
    tier = "report" if (free_chat and _wants_long_answer(content)) else "chat"

    # Quand des pages Notion sont dans les sources, le modèle doit les traiter
    # comme le matériau de l'utilisateur — pas comme une source publique.
    if any((getattr(p, "source", "") == "notion") for p in doc_passages):
        system += (
            "\n\nESPACE DE TRAVAIL : certaines sources numérotées proviennent de "
            "l'espace Notion de l'utilisateur (repérées « espace Notion »). Ce sont "
            "SES contenus : exploite-les en priorité, désigne-les comme « votre "
            "espace Notion » et ne dis jamais que tu n'y as pas accès."
        )

    return _Turn(conv=conv, agent_key=agent_key, redirect_note=redirect_note,
                 system=system, prompt=prompt, citations=citations, tier=tier,
                 max_tokens=8000 if tier == "report" else 2500)


def _finalize_turn(db: Session, user_id: str, turn: _Turn, answer: str, *,
                   is_admin: bool, degraded: bool) -> Message:
    """Persist the assistant turn, update the conversation, bill on success."""
    from app.modules.billing import service as billing

    if turn.redirect_note:
        answer = f"> ℹ️ {turn.redirect_note}\n\n{answer}"

    assistant_msg = Message(id=uuid.uuid4(), conversation_id=turn.conv.id,
                            role="assistant", agent=turn.agent_key, content=answer,
                            citations=turn.citations or None)
    db.add(assistant_msg)

    turn.conv.message_count += 2
    turn.conv.last_message_at = _now()
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


def post_message(db: Session, user_id: str, conversation_id: str, content: str,
                 agent_override: str | None = None, *, is_admin: bool = False,
                 document_ids: list[str] | None = None) -> Message:
    turn = _prepare_turn(db, user_id, conversation_id, content, agent_override,
                         is_admin=is_admin, document_ids=document_ids)
    if turn.blocked_answer:
        return _finalize_turn(db, user_id, turn, turn.blocked_answer,
                              is_admin=is_admin, degraded=True)
    try:
        result = llm_client.generate(system=turn.system, prompt=turn.prompt,
                                     tier=turn.tier, max_tokens=turn.max_tokens)
        answer, degraded = result.text, False
    except Exception as e:
        logger.warning("Agent generation failed: %s", e)
        answer, degraded = "⚠️ La génération a échoué. Réessaie dans un instant.", True
    return _finalize_turn(db, user_id, turn, answer, is_admin=is_admin,
                          degraded=degraded)


# --- Flux temps réel du chat ------------------------------------------------

def _sse(event: dict) -> str:
    import json

    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_message(db: Session, user_id: str, conversation_id: str, content: str,
                   agent_override: str | None = None, *, is_admin: bool = False,
                   document_ids: list[str] | None = None):
    """Same turn as post_message, but the answer arrives word by word.

    Order matters: the citations are sent BEFORE the first word, so the reader
    can already see what the answer is built on while it is being written.
    """
    try:
        turn = _prepare_turn(db, user_id, conversation_id, content, agent_override,
                             is_admin=is_admin, document_ids=document_ids)
    except AppError as e:
        yield _sse({"step": "error", "done": True, "error": e.message, "code": e.code})
        return
    except Exception as e:
        logger.warning("Stream prepare failed: %s", e)
        yield _sse({"step": "error", "done": True,
                    "error": "La préparation de la réponse a échoué."})
        return

    yield _sse({"step": "sources", "agent": turn.agent_key,
                "citations": turn.citations or []})

    if turn.blocked_answer:
        msg = _finalize_turn(db, user_id, turn, turn.blocked_answer,
                             is_admin=is_admin, degraded=True)
        yield _sse({"step": "done", "done": True, "degraded": True,
                    "data": _stream_payload(msg, turn)})
        return

    chunks: list[str] = []
    try:
        for chunk in llm_client.stream_text(system=turn.system, prompt=turn.prompt,
                                            tier=turn.tier,
                                            max_tokens=turn.max_tokens):
            chunks.append(chunk)
            yield _sse({"step": "delta", "delta": chunk})
    except Exception as e:
        logger.warning("Agent stream failed: %s", e)
        if not chunks:
            msg = _finalize_turn(db, user_id, turn,
                                 "⚠️ La génération a échoué. Réessaie dans un instant.",
                                 is_admin=is_admin, degraded=True)
            yield _sse({"step": "done", "done": True, "degraded": True,
                        "data": _stream_payload(msg, turn)})
            return
        # Coupure en cours de réponse : on garde ce qui a été écrit et on le dit.
        chunks.append("\n\n*(réponse interrompue — le service a coupé en cours "
                      "de rédaction)*")

    answer = "".join(chunks)
    msg = _finalize_turn(db, user_id, turn, answer, is_admin=is_admin, degraded=False)
    yield _sse({"step": "done", "done": True, "data": _stream_payload(msg, turn)})


def _stream_payload(msg: Message, turn: _Turn) -> dict:
    return {
        "id": str(msg.id),
        "role": msg.role,
        "agent": msg.agent,
        "content": msg.content,
        "citations": msg.citations or [],
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }
