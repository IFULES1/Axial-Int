"""Intelligence service: projects, conversations, and the agent message loop.

`post_message` is where an agent actually runs: route to the right persona
(non-overlap), retrieve RAG context, generate a sourced answer via the web-search
provider, and persist the turn. Resilient by design — a provider outage yields a
clear degraded message, never a crash.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

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
    # `auto` n'est pas une persona du registre mais reste un choix valide :
    # c'est celui qui laisse le routeur décider à chaque tour.
    demande = default_agent or ""
    agent = demande if (demande == personas.AUTO or personas.get_persona(demande)) \
        else personas.DEFAULT_AGENT
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
    # Un identifiant qui n'est pas un UUID (id provisoire côté client) vaut
    # « introuvable », pas une erreur serveur.
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise AppError("Conversation introuvable.", 404, code="not_found") from None
    conv = db.get(Conversation, conv_uuid)
    if not conv or str(conv.user_id) != user_id:
        raise AppError("Conversation introuvable.", 404, code="not_found")
    return conv


def list_messages(db: Session, user_id: str, conversation_id: str, *,
                  limit: int = 50,
                  before: str | None = None) -> tuple[list[Message], bool]:
    """Fenêtre de `limit` messages, rendue dans l'ordre chronologique.

    Sans `before` : les `limit` DERNIERS messages — c'est ce qu'un fil ouvre.
    Avec `before` (identifiant d'un message) : les `limit` messages qui le
    précèdent, pour « Charger les messages précédents ». `has_more` dit s'il
    reste quelque chose au-dessus de la fenêtre, donc s'il faut proposer le
    bouton. Un fil de 400 messages renvoyait 400 messages à chaque ouverture.
    """
    conv = _own_conversation(db, user_id, conversation_id)
    limit = max(1, min(int(limit or 50), 200))

    stmt = select(Message).where(Message.conversation_id == conv.id)
    if before:
        borne = db.get(Message, _uuid_ou_404(before, "Message introuvable."))
        if not borne or borne.conversation_id != conv.id:
            raise AppError("Message introuvable.", 404, code="not_found")
        stmt = stmt.where(Message.created_at < borne.created_at)
    # On lit un message de plus que demandé : sa présence EST la réponse à
    # « reste-t-il des messages plus anciens ? », sans second COUNT(*).
    fenetre = list(db.scalars(stmt.order_by(Message.created_at.desc())
                              .limit(limit + 1)))
    has_more = len(fenetre) > limit
    return list(reversed(fenetre[:limit])), has_more


def _uuid_ou_404(valeur: str, message: str) -> uuid.UUID:
    try:
        return uuid.UUID(valeur)
    except ValueError:
        raise AppError(message, 404, code="not_found") from None


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
    # Mémoire de fil : tours précédents envoyés au modèle avec la question.
    history: list[dict] = field(default_factory=list)
    # Coût de recherche du tour, mesuré pendant la préparation : c'est là que
    # les fournisseurs sont interrogés, pas à l'archivage.
    appels_recherche: int | None = None
    cout_recherche_micro_eur: int | None = None


# Titres qu'un utilisateur n'a jamais choisis : le frontend les pose à la
# création. Seule source du projet — `export.py` importe cette constante au
# lieu d'en tenir une copie qui divergeait.
TITRES_GENERIQUES = {"", "workspace", "nouvelle conversation", "conversation",
                     "new conversation", "nouvelle analyse", "new analysis"}


def titre_depuis(question: str, longueur: int = 80) -> str:
    """Première ligne utile de la question, coupée proprement — le titre qu'un
    humain donnerait en relisant l'historique."""
    texte = " ".join((question or "").split())
    if len(texte) <= longueur:
        return texte or "Conversation"
    coupe = texte[:longueur].rsplit(" ", 1)[0].rstrip(" ,;:")
    return coupe + "…"


def _appels(compteur: dict[str, int]) -> int | None:
    """Nombre total d'appels de recherche, ou None si aucun (une conversation
    triviale n'a rien cherché : un 0 la ferait passer pour mesurée à zéro)."""
    return sum(compteur.values()) or None


def _cout_recherche(compteur: dict[str, int]) -> int | None:
    from app.modules.billing.couts import cout_recherche_micro_eur

    return cout_recherche_micro_eur(compteur) or None


def _recompter(db: Session, conv: Conversation) -> int:
    """Recale `message_count` sur un COUNT(*) réel.

    Le compteur était incrémenté de 2 par tour et jamais corrigé : une
    suppression ou une édition de message le laissait faux, et c'est lui qui
    décide du titre de la conversation et du déclenchement du résumé.
    """
    from sqlalchemy import func

    n = db.scalar(select(func.count()).select_from(Message)
                  .where(Message.conversation_id == conv.id)) or 0
    conv.message_count = int(n)
    return conv.message_count


# --- Mémoire de fil --------------------------------------------------------

# 8 messages = 4 tours. Assez pour qu'une question de suite (« et pour
# l'Allemagne ? ») ait un sens, assez peu pour que le prompt reste court ; le
# reste du fil est porté par le résumé roulant.
HISTORIQUE_MESSAGES = 8
HISTORIQUE_CARACTERES = 1500
RESUME_MOTS_MAX = 600
# Longueur maximale d'un message envoyé. Au-delà, le front a laissé passer
# quelque chose : 413 plutôt qu'un prompt de 200 000 caractères facturé.
LONGUEUR_MAX_MESSAGE = 6000

# Blocs ```viz : c'est une consigne de rendu pour le frontend, pas du discours.
# Les renvoyer au modèle l'incite à les recopier et gonfle l'historique.
_BLOC_VIZ = re.compile(r"```viz\b.*?```", re.DOTALL)
# Note de redirection ajoutée par `_finalize_turn` : métadonnée d'interface.
_NOTE_REDIRECTION = re.compile(r"^>\s*ℹ️.*$", re.MULTILINE)


def verifier_longueur(content: str) -> None:
    """413 au-delà de `LONGUEUR_MAX_MESSAGE` caractères."""
    if len(content or "") > LONGUEUR_MAX_MESSAGE:
        raise AppError(
            f"Votre message dépasse {LONGUEUR_MAX_MESSAGE} caractères. "
            "Raccourcissez-le ou joignez un document.",
            413, code="message_trop_long")


def _nettoyer_pour_historique(texte: str) -> str:
    texte = _BLOC_VIZ.sub("", texte or "")
    texte = _NOTE_REDIRECTION.sub("", texte)
    return texte.strip()


def _alterner(tours: list[dict]) -> list[dict]:
    """Rend l'historique acceptable par Claude : commence par un tour
    utilisateur, alterne strictement, et se termine sur l'assistant (le tour
    utilisateur courant est le prompt). Un fil réel n'alterne pas toujours —
    une génération échouée, un message supprimé, et l'API refuse tout le tour.
    """
    out: list[dict] = []
    for m in tours:
        if not out and m["role"] != "user":
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1]["content"] += "\n\n" + m["content"]
            continue
        out.append(dict(m))
    if out and out[-1]["role"] == "user":
        # Question restée sans réponse : elle est déjà dans le prompt courant
        # ou n'a jamais abouti, la garder créerait deux tours utilisateur.
        out.pop()
    return out


def _historique(db: Session, conv: Conversation) -> list[dict]:
    """Les `HISTORIQUE_MESSAGES` derniers messages du fil, prêts pour l'API.

    À appeler AVANT d'ajouter le message utilisateur courant à la session :
    l'autoflush d'un `select` le ferait apparaître dans sa propre mémoire.
    """
    stmt = (select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(HISTORIQUE_MESSAGES))
    tours: list[dict] = []
    for m in reversed(list(db.scalars(stmt))):
        texte = _nettoyer_pour_historique(m.content)
        if not texte:
            continue
        tours.append({"role": "assistant" if m.role == "assistant" else "user",
                      "content": texte[:HISTORIQUE_CARACTERES]})
    return _alterner(tours)


RESUME_SYSTEM = (
    "Tu résumes une conversation de conseil aux entreprises pour qu'un autre "
    "assistant la reprenne sans avoir lu les échanges. Restitue les faits "
    "utiles : sujet, contexte de l'entreprise, décisions, chiffres, "
    "préférences exprimées, questions restées ouvertes. Maximum "
    f"{RESUME_MOTS_MAX} mots, en prose dense, sans formule d'introduction ni "
    "de conclusion. Écris dans la langue de la conversation."
)


def _mettre_a_jour_resume(db: Session, conv: Conversation) -> None:
    """Résumé roulant des messages sortis de la fenêtre des 8 derniers.

    Appelé APRÈS l'événement `done` : l'utilisateur a déjà sa réponse, il n'a
    pas à attendre un second appel au modèle. Toute erreur est absorbée — un
    résumé manquant dégrade la mémoire longue, il ne casse pas la conversation.
    """
    try:
        if (conv.message_count or 0) <= HISTORIQUE_MESSAGES:
            return
        tous = list(db.scalars(select(Message)
                               .where(Message.conversation_id == conv.id)
                               .order_by(Message.created_at.asc())))
        anciens = tous[:-HISTORIQUE_MESSAGES]
        if not anciens:
            return
        corps = "\n\n".join(
            f"{'Utilisateur' if m.role == 'user' else 'Assistant'} : "
            f"{_nettoyer_pour_historique(m.content)[:HISTORIQUE_CARACTERES]}"
            for m in anciens if _nettoyer_pour_historique(m.content))
        if not corps:
            return
        prefixe = (f"Résumé précédent (à compléter, pas à répéter) :\n{conv.resume}\n\n"
                   if conv.resume else "")
        res = llm_client.generate(system=RESUME_SYSTEM,
                                  prompt=f"{prefixe}Messages à résumer :\n{corps}",
                                  tier="chat", max_tokens=900)
        texte = " ".join((res.text or "").split())
        if not texte:
            return
        mots = texte.split(" ")
        conv.resume = " ".join(mots[:RESUME_MOTS_MAX]) + ("…" if len(mots) > RESUME_MOTS_MAX else "")
        db.commit()
    except Exception as e:  # noqa: BLE001 — jamais bloquant
        logger.warning("Résumé roulant non mis à jour : %s", e)


def _fournisseurs_recherche() -> list[str]:
    """Fournisseurs qui vont être interrogés — pour l'annoncer AVANT la
    recherche (le compteur, lui, n'est rempli qu'après)."""
    try:
        from app.config import get_settings
        from app.shared.search.providers import get_provider

        return [n for n in get_settings().search_provider_list
                if (p := get_provider(n)) and p.available()]
    except Exception as e:  # noqa: BLE001
        logger.warning("Liste des fournisseurs de recherche indisponible : %s", e)
        return []


# --- Préparation d'un tour, en deux temps ----------------------------------

@dataclass
class _Contexte:
    """Ce qu'on sait AVANT la recherche web : routage, crédits, mémoire.

    Séparé de la recherche pour que le flux puisse annoncer « Recherche web… »
    au bon moment — c'est la partie lente, et l'annoncer après ne sert à rien.
    """
    conv: Conversation
    agent_key: str
    redirect_note: str | None
    persona: object
    conversation_libre: bool
    company_context: str
    attached_context: str
    history: list[dict]
    trivial: bool


@dataclass
class _Recherche:
    combined_context: str = ""
    citations: list = field(default_factory=list)
    doc_passages: list = field(default_factory=list)
    appels_recherche: int | None = None
    cout_recherche_micro_eur: int | None = None


def _preparer_contexte(db: Session, user_id: str, conversation_id: str, content: str,
                       agent_override: str | None, *, is_admin: bool,
                       document_ids: list[str] | None) -> _Contexte:
    verifier_longueur(content)
    conv = _own_conversation(db, user_id, conversation_id)
    requested = agent_override or conv.default_agent
    # Le routeur réel décide dans TOUS les cas : en `auto` il lit l'intention,
    # sur choix explicite il respecte la demande et se contente d'une note de
    # redirection. Le court-circuit précédent envoyait toute conversation libre
    # à Axial Conseil — Market Scanner et Competitor Radar n'étaient joignables
    # que par le sélecteur, alors que le routage était la fonctionnalité.
    agent_key, redirect_note = personas.route(content, requested=requested)
    persona = personas.get_persona(agent_key) or personas.AXIAL_CONSEIL
    free_chat = requested == personas.AUTO
    # `free_chat` dit seulement que l'utilisateur n'a rien imposé. Le ton de
    # conversation (pas de bloc « AXIAL Recommande », tier selon la longueur de
    # la demande) ne vaut que si le routeur a retenu le généraliste : un
    # spécialiste choisi par le routeur répond avec son cadre complet.
    conversation_libre = free_chat and agent_key == personas.AXIAL_CONSEIL.key

    # Affordability check before spending the API call (admins bypass).
    from app.modules.billing import service as billing

    if not is_admin:
        chk = billing.check_credits(db, user_id, AGENT_MESSAGE_ACTION)
        if not chk["affordable"]:
            raise AppError(
                f"Crédits insuffisants ({chk['available']}/{chk['cost']}).",
                402, code="insufficient_credits",
            )

    # Mémoire de fil AVANT d'ajouter le message courant : sinon l'autoflush du
    # `select` le glisserait dans son propre historique.
    history = _historique(db, conv)

    # Persist the user's turn first.
    user_msg = Message(id=uuid.uuid4(), conversation_id=conv.id, role="user",
                       agent=agent_key, content=content)
    db.add(user_msg)
    # Première question = titre. Le frontend crée chaque conversation sous
    # « Workspace » et rien ne le remplaçait : 14 conversations sur 19 portaient
    # ce nom, l'historique existait mais restait illisible.
    if conv.message_count == 0 and (conv.title or "").strip().lower() in TITRES_GENERIQUES:
        conv.title = titre_depuis(content)

    from app.modules.memory import service as memory

    company_context = memory.build_context(db, user_id)
    attached_context = _attached_docs_context(db, user_id, document_ids)

    # Vitesse : très courts messages en conversation libre (« merci », « ok »)
    # → pas de recherche du tout, réponse immédiate du LLM.
    trivial = conversation_libre and len(content.strip()) < 25 and not attached_context

    return _Contexte(conv=conv, agent_key=agent_key, redirect_note=redirect_note,
                     persona=persona, conversation_libre=conversation_libre,
                     company_context=company_context,
                     attached_context=attached_context, history=history,
                     trivial=trivial)


def _rechercher(db: Session, user_id: str, content: str,
                ctx: _Contexte) -> _Recherche:
    """La partie lente : web, RAG, Notion, rerank. Le flux l'annonce."""
    from app.shared import search as web_search

    # Rempli par l'orchestrateur, un compte par fournisseur interrogé : le coût
    # de recherche d'une conversation n'apparaît sur aucune facture ventilée,
    # il faut le compter à la source (même mécanique que `analysis`).
    appels_recherche: dict[str, int] = {}

    if ctx.trivial:
        doc_passages, web_results = [], []
    else:
        # RAG et recherche web en PARALLÈLE (elles ne partagent pas la session DB).
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_docs = ex.submit(_retrieve_context, content, user_id)
            f_web = ex.submit(web_search.search, content, 6,
                              compteur=appels_recherche)
            try:
                web_results = f_web.result()
            except Exception as e:
                logger.warning("Agent web search failed: %s", e)
                web_results = []
            _, doc_passages = f_docs.result()

    # Espace Notion de l'utilisateur : ses pages rejoignent le même pool que le
    # web et ses documents, donc elles sont rerankées et citées comme le reste.
    if not ctx.trivial:
        try:
            from app.modules.integrations import notion_context

            doc_passages = list(doc_passages) + notion_context.passages_pour(
                db, user_id, content)
        except Exception as e:  # noqa: BLE001 — un outil injoignable ne bloque rien
            logger.warning("Espace Notion indisponible : %s", e)

    # Rerank web + internal together → one relevance-ordered context + citations.
    combined_context, citations = _assemble_sources(content, web_results, doc_passages)
    return _Recherche(combined_context=combined_context, citations=citations,
                      doc_passages=list(doc_passages),
                      appels_recherche=_appels(appels_recherche),
                      cout_recherche_micro_eur=_cout_recherche(appels_recherche))


def _assembler_turn(content: str, ctx: _Contexte, rech: _Recherche) -> _Turn:
    """Prompt + system + tier, une fois le contexte et les sources réunis."""
    conv, agent_key, persona = ctx.conv, ctx.agent_key, ctx.persona
    company_context, conversation_libre = ctx.company_context, ctx.conversation_libre
    combined_context, citations = rech.combined_context, rech.citations

    parts = [p for p in (
        # Le résumé roulant ouvre le prompt : c'est la mémoire longue du fil,
        # tout ce qui suit se lit à sa lumière.
        (f"Résumé de la conversation jusqu'ici :\n{conv.resume}" if conv.resume else ""),
        company_context,
        ctx.attached_context,
        f"Sources (classées par pertinence) :\n{combined_context}" if combined_context else "",
    ) if p]
    prompt = (("\n\n".join(parts) + f"\n\nQuestion: {content}") if parts else content)

    from app.modules.pii.client import guard_outbound

    prompt = guard_outbound(prompt)

    if not llm_client.generation_available():
        return _Turn(conv=conv, agent_key=agent_key, redirect_note=ctx.redirect_note,
                     system="", prompt=prompt, citations=citations, tier="chat",
                     max_tokens=0, history=ctx.history,
                     blocked_answer=("⚠️ Aucun moteur de génération n'est disponible "
                                     "pour le moment. Réessayez plus tard."),
                     appels_recherche=rech.appels_recherche,
                     cout_recherche_micro_eur=rech.cout_recherche_micro_eur)

    # Conversation avec le généraliste = échange naturel : ni cadre d'analyse
    # ni bloc « AXIAL Recommande » imposé. Agent spécialisé (choisi par
    # l'utilisateur OU retenu par le routeur) = persona complète. La consigne
    # de visualisation, elle, vaut pour tous les chemins.
    system = (persona.system_prompt + personas.VIZ_INSTRUCTION
              + personas.REGISTRE_INSTRUCTION) if conversation_libre \
        else persona.full_system_prompt()
    # Rendre la mémoire PERCEPTIBLE : quand un contexte entreprise existe,
    # la réponse doit s'y ancrer explicitement (jamais un acteur générique).
    if company_context:
        system += (
            "\n\nUn bloc « Contexte entreprise (mémoire) » est fourni dans le "
            "message. Ancre EXPLICITEMENT ta réponse dedans : ouvre par une phrase "
            "qui situe la réponse dans le contexte de cette entreprise — son nom "
            "puis l'élément de profil pertinent pour la question (« Dans votre "
            "contexte — [nom], [élément]… » en français, « In your context — "
            "[name], [element]… » en anglais) — puis adapte chaque recommandation "
            "à SA situation (positionnement, stade, défi) plutôt qu'à un acteur "
            "générique du secteur. Cette phrase d'ouverture suit la langue de la "
            "réponse, jamais celle de cette instruction."
        )
    # Conversation libre : Gemini (chat) pour le court, Sonnet (report) pour le
    # long. Agents spécialisés : tier chat (comportement historique).
    tier = "report" if (conversation_libre and _wants_long_answer(content)) else "chat"

    # La langue de la QUESTION commande celle de la réponse : quelqu'un qui écrit
    # en anglais dans une interface française n'a pas à changer un réglage.
    from app.shared import langue as lg

    system += lg.consigne_miroir()

    # Quand des pages Notion sont dans les sources, le modèle doit les traiter
    # comme le matériau de l'utilisateur — pas comme une source publique.
    if any((getattr(p, "source", "") == "notion") for p in rech.doc_passages):
        system += (
            "\n\nESPACE DE TRAVAIL : certaines sources numérotées proviennent de "
            "l'espace Notion de l'utilisateur (repérées « espace Notion »). Ce sont "
            "SES contenus : exploite-les en priorité, désigne-les comme « votre "
            "espace Notion » et ne dis jamais que tu n'y as pas accès."
        )

    return _Turn(conv=conv, agent_key=agent_key, redirect_note=ctx.redirect_note,
                 system=system, prompt=prompt, citations=citations, tier=tier,
                 # 2500 pouvaient être entièrement absorbés par la réflexion
                 # adaptative du modèle, ne laissant rien pour la réponse.
                 max_tokens=16000 if tier == "report" else 8000,
                 history=ctx.history,
                 appels_recherche=rech.appels_recherche,
                 cout_recherche_micro_eur=rech.cout_recherche_micro_eur)


def _prepare_turn(db: Session, user_id: str, conversation_id: str, content: str,
                  agent_override: str | None, *, is_admin: bool,
                  document_ids: list[str] | None) -> _Turn:
    """Chemin bloquant : les trois étapes enchaînées, sans annonce d'étape."""
    ctx = _preparer_contexte(db, user_id, conversation_id, content, agent_override,
                             is_admin=is_admin, document_ids=document_ids)
    rech = _rechercher(db, user_id, content, ctx)
    return _assembler_turn(content, ctx, rech)


def credits_du_message(msg: Message) -> int:
    """Crédits réellement débités pour ce message. Un statut `partiel` ou
    `degrade` n'est pas facturé : la pastille doit dire 0, pas 2."""
    from app.modules.billing.catalog import cost_for

    if msg.role != "assistant" or msg.statut != "complet":
        return 0
    return cost_for(AGENT_MESSAGE_ACTION)


def _solde(db: Session, user_id: str) -> int | None:
    """Solde de crédits après le tour, pour la pastille du frontend.
    `None` si le calcul échoue — mieux vaut ne rien afficher qu'un faux solde."""
    try:
        from app.modules.billing import service as billing

        return billing.available_credits(billing.get_or_create_balance(db, user_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("Solde indisponible : %s", e)
        return None


def rejeu(db: Session, user_id: str, conversation_id: str,
          cle_idempotence: str | None) -> Message | None:
    """Message assistant déjà produit pour cette clé, s'il existe.

    Le frontend renvoie le même `X-Idempotency-Key` quand il réessaie après une
    coupure réseau : sans ce garde-fou, l'utilisateur payait deux fois la même
    question et voyait le tour en double dans son fil.
    """
    if not cle_idempotence:
        return None
    conv = _own_conversation(db, user_id, conversation_id)
    stmt = (select(Message)
            .where(Message.conversation_id == conv.id,
                   Message.cle_idempotence == cle_idempotence)
            .order_by(Message.created_at.desc()))
    return db.scalars(stmt).first()


def _finalize_turn(db: Session, user_id: str, turn: _Turn, answer: str, *,
                   is_admin: bool, statut: str = "complet", mesure=None,
                   cle_idempotence: str | None = None) -> Message:
    """Persist the assistant turn, update the conversation, bill on success.

    `statut` — `complet`, `partiel` (arrêt utilisateur ou coupure après le
    premier mot) ou `degrade` (échec, réponse vide, aucun moteur). Seul
    `complet` est facturé : un texte tronqué par un Stop ou une panne n'est pas
    une réponse vendue.

    `mesure` — le LLMResult de la génération. Sans lui, le coût des
    conversations reste invisible et le coût total mensuel incalculable : seuls
    les rapports étaient instrumentés.
    """
    from app.modules.billing import service as billing
    from app.modules.billing.couts import cout_micro_eur

    if turn.redirect_note:
        answer = f"> ℹ️ {turn.redirect_note}\n\n{answer}"

    entree = getattr(mesure, "input_tokens", 0) or 0
    sortie = getattr(mesure, "output_tokens", 0) or 0
    modele = getattr(mesure, "model", None)
    # Visualisations de la réponse, préparées maintenant pour que l'historique
    # se recharge sans recompiler. Tolérant : jamais bloquant. Sur un tour
    # dégradé il n'y a rien à compiler (le texte est un message d'erreur).
    from app.modules.viz import service as viz_service

    viz = viz_service.preparer_sans_faute(db, answer) if statut != "degrade" else None
    assistant_msg = Message(id=uuid.uuid4(), conversation_id=turn.conv.id,
                            role="assistant", agent=turn.agent_key, content=answer,
                            citations=turn.citations or None, viz=viz,
                            tokens_entree=entree or None,
                            tokens_sortie=sortie or None,
                            modele=modele,
                            cout_micro_eur=(cout_micro_eur(modele, entree, sortie)
                                            if modele else None) or None,
                            appels_recherche=turn.appels_recherche,
                            cout_recherche_micro_eur=turn.cout_recherche_micro_eur,
                            statut=statut,
                            cle_idempotence=cle_idempotence or None)
    db.add(assistant_msg)

    turn.conv.message_count += 2
    turn.conv.last_message_at = _now()
    db.commit()
    db.refresh(assistant_msg)

    # Charge + track only on a real answer (never on degradation or a stop).
    if statut == "complet":
        from app.modules.analytics import client as analytics

        billing_res = billing.consume_credits(db, user_id, AGENT_MESSAGE_ACTION,
                                              is_admin=is_admin)
        analytics.increment_usage(user_id, agent_messages=1,
                                  credits=billing_res.get("charged", 0))

    return assistant_msg


def post_message(db: Session, user_id: str, conversation_id: str, content: str,
                 agent_override: str | None = None, *, is_admin: bool = False,
                 document_ids: list[str] | None = None,
                 cle_idempotence: str | None = None) -> Message:
    deja = rejeu(db, user_id, conversation_id, cle_idempotence)
    if deja is not None:
        return deja
    turn = _prepare_turn(db, user_id, conversation_id, content, agent_override,
                         is_admin=is_admin, document_ids=document_ids)
    if turn.blocked_answer:
        return _finalize_turn(db, user_id, turn, turn.blocked_answer,
                              is_admin=is_admin, statut="degrade",
                              cle_idempotence=cle_idempotence)
    result = None
    try:
        result = llm_client.generate(system=turn.system, prompt=turn.prompt,
                                     tier=turn.tier, max_tokens=turn.max_tokens,
                                     history=turn.history)
        answer, statut = result.text, "complet"
    except Exception as e:
        logger.warning("Agent generation failed: %s", e)
        answer = "⚠️ La génération a échoué. Réessayez dans un instant."
        statut = "degrade"
    msg = _finalize_turn(db, user_id, turn, answer, is_admin=is_admin,
                         statut=statut, mesure=result,
                         cle_idempotence=cle_idempotence)
    if statut == "complet":
        _mettre_a_jour_resume(db, turn.conv)
    return msg


# --- Coût d'une conversation ------------------------------------------------

def cout_conversation(db: Session, user_id: str, conversation_id: str, *,
                      is_admin: bool = False) -> dict:
    """Total du fil : crédits débités, tokens, et le coût réel en micro-euros
    (modèle + recherche) réservé aux admins — c'est une donnée de marge."""
    conv = _own_conversation(db, user_id, conversation_id)
    reponses = list(db.scalars(select(Message).where(
        Message.conversation_id == conv.id, Message.role == "assistant")))
    micro = sum((m.cout_micro_eur or 0) + (m.cout_recherche_micro_eur or 0)
                for m in reponses)
    return {
        "messages": len(reponses),
        "credits": sum(credits_du_message(m) for m in reponses),
        "tokens_entree": sum(m.tokens_entree or 0 for m in reponses),
        "tokens_sortie": sum(m.tokens_sortie or 0 for m in reponses),
        "cout_micro_eur": micro if is_admin else None,
    }


# --- Flux temps réel du chat ------------------------------------------------

def _sse(event: dict) -> str:
    import json

    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# Reprises après troncature EN FLUX. Deux : au-delà, ce n'est plus un plafond
# de sortie mais une consigne de volume déraisonnable (le chemin bloquant de
# `claude.generate` en autorise trois, il n'a pas d'utilisateur qui attend).
REPRISES_FLUX_MAX = 2
SUITE_FLUX_CONSIGNE = "Continue exactement où tu t'es arrêté, sans répéter."

NOTE_INTERROMPUE = "\n\n*(réponse interrompue)*"
NOTE_COUPURE = ("\n\n*(réponse interrompue — le service a coupé en cours "
                "de rédaction)*")

# Fréquence du test de déconnexion dans la boucle de chunks. Chaque test
# traverse la frontière thread → boucle d'événements : à chaque chunk, le coût
# dépasserait ce qu'il évite.
DECONNEXION_TOUS_LES = 10


def stream_message(db: Session, user_id: str, conversation_id: str, content: str,
                   agent_override: str | None = None, *, is_admin: bool = False,
                   document_ids: list[str] | None = None,
                   cle_idempotence: str | None = None,
                   est_deconnecte: Callable[[], bool] | None = None):
    """Same turn as post_message, but the answer arrives word by word.

    Order matters: the citations are sent BEFORE the first word, so the reader
    can already see what the answer is built on while it is being written.

    `est_deconnecte` — fourni par le routeur, dit si le client a fermé la
    connexion (bouton Stop, onglet fermé). Le générateur s'arrête alors et
    ARCHIVE quand même le texte écrit, en `statut='partiel'` et sans facturer :
    l'utilisateur retrouve ce qu'il a vu passer.
    """
    # Rejeu : la même clé renvoie le message déjà produit, en un seul `done`.
    try:
        deja = rejeu(db, user_id, conversation_id, cle_idempotence)
    except AppError as e:
        yield _sse({"step": "error", "done": True, "error": e.message, "code": e.code})
        return
    if deja is not None:
        yield _sse({"step": "done", "done": True, "rejeu": True,
                    "data": _stream_payload(deja, balance=_solde(db, user_id),
                                             is_admin=is_admin)})
        return

    try:
        ctx = _preparer_contexte(db, user_id, conversation_id, content,
                                 agent_override, is_admin=is_admin,
                                 document_ids=document_ids)
    except AppError as e:
        yield _sse({"step": "error", "done": True, "error": e.message, "code": e.code})
        return
    except Exception as e:
        logger.warning("Stream prepare failed: %s", e)
        yield _sse({"step": "error", "done": True,
                    "error": "La préparation de la réponse a échoué."})
        return

    # Profil entreprise vide : la réponse sera générique et l'utilisateur doit
    # le savoir AVANT de la lire, pas en la trouvant décevante.
    if not ctx.company_context:
        yield _sse({"step": "avertissement", "code": "contexte_absent"})

    try:
        if not ctx.trivial:
            yield _sse({"step": "etape", "etape": "recherche",
                        "detail": {"fournisseurs": _fournisseurs_recherche()}})
        rech = _rechercher(db, user_id, content, ctx)
        yield _sse({"step": "etape", "etape": "sources",
                    "detail": {"nombre": len(rech.citations or [])}})
        turn = _assembler_turn(content, ctx, rech)
    except Exception as e:
        logger.warning("Stream search failed: %s", e)
        yield _sse({"step": "error", "done": True,
                    "error": "La préparation de la réponse a échoué."})
        return

    yield _sse({"step": "sources", "agent": turn.agent_key,
                "citations": turn.citations or []})

    if turn.blocked_answer:
        msg = _finalize_turn(db, user_id, turn, turn.blocked_answer,
                             is_admin=is_admin, statut="degrade",
                             cle_idempotence=cle_idempotence)
        yield _sse({"step": "done", "done": True, "degraded": True,
                    "data": _stream_payload(msg, balance=_solde(db, user_id),
                                            is_admin=is_admin)})
        return

    yield _sse({"step": "etape", "etape": "redaction", "detail": {}})

    chunks: list[str] = []
    statut = "complet"
    # Rempli par le fournisseur, cumulé sur les reprises : sans lui, une
    # réponse en flux — le chemin normal du chat — n'aurait ni tokens ni coût
    # archivés, alors que `MessageOut` et `GET …/cout` les exposent.
    compte_tokens: dict = {}
    try:
        prompt_flux, hist_flux = turn.prompt, list(turn.history)
        for reprise in range(REPRISES_FLUX_MAX + 1):
            flux = llm_client.stream_text(system=turn.system, prompt=prompt_flux,
                                          tier=turn.tier, history=hist_flux,
                                          mesure=compte_tokens,
                                          max_tokens=turn.max_tokens)
            raison, vus = None, 0
            while True:
                try:
                    chunk = next(flux)
                except StopIteration as fin:
                    raison = fin.value
                    break
                chunks.append(chunk)
                yield _sse({"step": "delta", "delta": chunk})
                vus += 1
                if (vus % DECONNEXION_TOUS_LES == 0 and est_deconnecte
                        and est_deconnecte()):
                    flux.close()
                    statut = "partiel"
                    break
            if statut == "partiel" or raison != "max_tokens":
                break
            partiel = "".join(chunks)
            if not partiel.strip():
                break
            # Reprise : on rend au modèle ce qu'il a écrit et on lui demande de
            # poursuivre, sans fermer le flux vers le navigateur.
            logger.info("Flux tronqué (%s), reprise %d/%d", turn.tier,
                        reprise + 1, REPRISES_FLUX_MAX)
            hist_flux = list(turn.history) + [
                {"role": "user", "content": turn.prompt},
                {"role": "assistant", "content": partiel},
            ]
            prompt_flux = SUITE_FLUX_CONSIGNE
        if statut == "partiel":
            chunks.append(NOTE_INTERROMPUE)
    except GeneratorExit:
        # FastAPI ferme le générateur quand le client part sans que le test de
        # déconnexion soit tombé (entre deux vérifications, ou dès le premier
        # morceau). On archive AVANT de laisser la fermeture se poursuivre :
        # c'est exactement ce qui faisait perdre un rapport le 25/08. Plus
        # rien ne peut être émis à ce stade, d'où l'absence de `done`.
        if chunks:
            chunks.append(NOTE_INTERROMPUE)
            _finalize_turn(db, user_id, turn, "".join(chunks), is_admin=is_admin,
                           statut="partiel", cle_idempotence=cle_idempotence,
                           mesure=llm_client.resultat_de_mesure(compte_tokens))
            logger.info("Flux fermé par le client — réponse partielle archivée")
        raise
    except Exception as e:
        logger.warning("Agent stream failed: %s", e)
        if not chunks:
            msg = _finalize_turn(db, user_id, turn,
                                 "⚠️ La génération a échoué. Réessayez dans un instant.",
                                 is_admin=is_admin, statut="degrade",
                                 cle_idempotence=cle_idempotence)
            yield _sse({"step": "done", "done": True, "degraded": True,
                        "data": _stream_payload(msg,
                                                balance=_solde(db, user_id),
                                                is_admin=is_admin)})
            return
        # Coupure en cours de réponse : on garde ce qui a été écrit et on le dit.
        chunks.append(NOTE_COUPURE)
        statut = "partiel"

    answer = "".join(chunks)
    # Le flux peut se terminer SANS erreur et SANS rien produire : le modèle
    # renvoie zéro token quand sa réflexion a consommé tout le budget de sortie.
    # Sans ce garde-fou, la réponse vide était archivée et facturée — arrivé le
    # 03/09 à un utilisateur qui posait sa deuxième question.
    if not answer.strip():
        logger.warning("Réponse vide (modèle %s, tier %s) — non facturée",
                       turn.agent_key, turn.tier)
        msg = _finalize_turn(
            db, user_id, turn,
            "⚠️ La réponse n'a pas abouti. Reposez votre question — aucun crédit "
            "n'a été débité.",
            is_admin=is_admin, statut="degrade", cle_idempotence=cle_idempotence)
        yield _sse({"step": "done", "done": True, "degraded": True,
                    "data": _stream_payload(msg, balance=_solde(db, user_id),
                                            is_admin=is_admin)})
        return

    # Archiver AVANT le dernier `yield` : si le client est déjà parti, l'envoi
    # du `done` échoue, mais le message partiel est en base.
    msg = _finalize_turn(db, user_id, turn, answer, is_admin=is_admin,
                         statut=statut, cle_idempotence=cle_idempotence,
                         mesure=llm_client.resultat_de_mesure(compte_tokens))
    yield _sse({"step": "done", "done": True, "degraded": statut == "degrade",
                "data": _stream_payload(msg, balance=_solde(db, user_id),
                                        is_admin=is_admin)})
    # Résumé roulant APRÈS le `done` : l'utilisateur a sa réponse, il n'attend
    # pas un second appel au modèle.
    if statut == "complet":
        _mettre_a_jour_resume(db, turn.conv)


def _stream_payload(msg: Message, *, balance: int | None = None,
                    is_admin: bool = False) -> dict:
    """Forme d'un message dans le payload final du flux.

    `cout_micro_eur` n'est renseigné que pour un admin : c'est le coût réel de
    production, donc une donnée de marge, pas une information client.
    """
    return {
        "id": str(msg.id),
        "role": msg.role,
        "agent": msg.agent,
        "content": msg.content,
        "citations": msg.citations or [],
        "viz": getattr(msg, "viz", None) or [],
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "statut": msg.statut,
        "tokens_entree": msg.tokens_entree,
        "tokens_sortie": msg.tokens_sortie,
        "credits": credits_du_message(msg),
        "cout_micro_eur": msg.cout_micro_eur if is_admin else None,
        "balance": balance,
    }
