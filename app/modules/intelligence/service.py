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
import threading
import uuid
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
    # Un identifiant qui n'est pas un UUID vaut « introuvable », pas une
    # erreur serveur : il arrive maintenant de l'URL (PATCH/DELETE) et un
    # client peut y mettre n'importe quoi.
    proj = db.get(Project, _uuid_ou_404(project_id, "Projet introuvable."))
    if not proj or str(proj.user_id) != user_id:
        raise AppError("Projet introuvable.", 404, code="not_found")
    return proj


def update_project(db: Session, user_id: str, project_id: str, *,
                   name: str | None = None,
                   archived: bool | None = None) -> Project:
    """Renomme et/ou (dés)archive un dossier. Les champs absents ne bougent pas.

    `archived` est un booléen côté API et une date côté base (`archived_at`) :
    le front veut une bascule, l'historique veut savoir quand.
    """
    proj = _own_project(db, user_id, project_id)
    if name is not None:
        propre = " ".join(name.split())
        if not propre:
            raise AppError("Le nom du dossier ne peut pas être vide.", 400,
                           code="nom_vide")
        proj.name = propre[:200]
    if archived is not None:
        proj.archived_at = _now() if archived else None
    db.commit()
    db.refresh(proj)
    return proj


def delete_project(db: Session, user_id: str, project_id: str) -> None:
    """Supprime un dossier VIDE (au sens : plus aucune conversation active).

    Refusé tant qu'il reste des conversations non archivées : la cascade ORM
    emporterait les conversations ET leurs messages, et « supprimer le
    dossier » n'est pas une manière d'effacer trente fils par erreur.
    Les conversations archivées, elles, partent avec le dossier.
    """
    from sqlalchemy import func

    proj = _own_project(db, user_id, project_id)
    actives = db.scalar(
        select(func.count()).select_from(Conversation)
        .where(Conversation.project_id == proj.id,
               Conversation.archived_at.is_(None))) or 0
    if actives:
        raise AppError(
            f"Ce dossier contient encore {actives} conversation(s) non "
            "archivée(s). Déplacez-les ou archivez-les avant de supprimer "
            "le dossier.",
            409, code="projet_non_vide")
    db.delete(proj)
    db.commit()


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


def list_conversations(db: Session, user_id: str, project_id: str, *,
                       inclure_archivees: bool = False,
                       limit: int = 100) -> list[Conversation]:
    """Conversations d'un dossier, dans l'ordre du panneau.

    Épinglées d'abord (la plus récemment épinglée en tête), puis les autres
    par dernier message décroissant. Les `NULL` sont rejetés en fin de liste
    par un tri sur `is_(None)` plutôt que par `NULLS LAST` : PostgreSQL et
    SQLite ne placent pas les `NULL` du même côté d'un `ORDER BY … DESC`, et
    une conversation créée sans message aurait remonté en tête d'un côté
    seulement.
    """
    proj = _own_project(db, user_id, project_id)
    stmt = select(Conversation).where(Conversation.project_id == proj.id)
    if not inclure_archivees:
        stmt = stmt.where(Conversation.archived_at.is_(None))
    stmt = (stmt.order_by(Conversation.pinned_at.is_(None).asc(),
                          Conversation.pinned_at.desc(),
                          Conversation.last_message_at.is_(None).asc(),
                          Conversation.last_message_at.desc(),
                          Conversation.created_at.desc())
            .limit(max(1, min(int(limit or 100), 200))))
    return list(db.scalars(stmt))


def update_conversation(db: Session, user_id: str, conversation_id: str, *,
                        title: str | None = None,
                        pinned: bool | None = None,
                        archived: bool | None = None,
                        project_id: str | None = None) -> Conversation:
    """Renomme, épingle, archive, ou déplace une conversation de dossier.

    Un seul endpoint pour les quatre : ce sont quatre attributs de la même
    ligne, et le menu ⋯ du panneau les enchaîne. Les champs absents du corps
    ne sont pas touchés (sémantique PATCH), donc `archived: false` désarchive
    et `archived` absent ne dit rien.
    """
    conv = _own_conversation(db, user_id, conversation_id)
    if title is not None:
        propre = " ".join(title.split())
        if not propre:
            raise AppError("Le titre ne peut pas être vide.", 400, code="titre_vide")
        conv.title = propre[:300]
    if pinned is not None:
        conv.pinned_at = _now() if pinned else None
    if archived is not None:
        conv.archived_at = _now() if archived else None
        # Une conversation archivée n'a plus à occuper la section « Épinglées ».
        if archived:
            conv.pinned_at = None
    if project_id is not None:
        # Le dossier de destination doit appartenir au MÊME utilisateur :
        # sinon un identifiant deviné déplacerait un fil chez quelqu'un
        # d'autre. `_own_project` rend 404, pas 403 — on ne confirme pas
        # l'existence d'un dossier qui n'est pas le sien.
        cible = _own_project(db, user_id, project_id)
        conv.project_id = cible.id
    db.commit()
    db.refresh(conv)
    return conv


def delete_conversation(db: Session, user_id: str, conversation_id: str) -> None:
    """Supprime la conversation et ses messages.

    La cascade ORM (`Conversation.messages`, `delete-orphan`) emporte les
    messages. Les rendus de visualisation (`viz_rendus`) ne sont PAS touchés :
    ils sont mis en cache par empreinte du spec compilé et partagés entre
    messages et rapports — en supprimer un casserait les images d'un autre fil.
    """
    conv = _own_conversation(db, user_id, conversation_id)
    db.delete(conv)
    db.commit()


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


# --- Recherche dans les conversations --------------------------------------

RECHERCHE_MINIMUM = 3
RECHERCHE_RESULTATS = 20
RECHERCHE_MARGE = 80


def _motif_like(terme: str) -> str:
    """Terme échappé pour un `LIKE`.

    Sans échappement, chercher « 100 % » ou « chiffre_affaires » rendait
    n'importe quoi : `%` et `_` sont les jokers du `LIKE`.
    """
    echappe = terme.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{echappe.lower()}%"


def _extrait(texte: str, terme: str, marge: int = RECHERCHE_MARGE) -> str:
    """Fenêtre de ±`marge` caractères autour de la PREMIÈRE occurrence.

    Calculé en Python et non en SQL : `position()` n'existe pas en SQLite,
    `strpos` n'est pas insensible à la casse, et le rendu (les « … » de
    troncature) est de toute façon un choix d'affichage.
    """
    texte = texte or ""
    i = texte.lower().find(terme.lower())
    if i < 0:
        # Le message ne contient pas le terme (résultat trouvé par le titre) :
        # on rend le début, qui est le meilleur aperçu disponible.
        debut, fin = 0, min(len(texte), 2 * marge)
    else:
        debut = max(0, i - marge)
        fin = min(len(texte), i + len(terme) + marge)
    fragment = " ".join(texte[debut:fin].split())
    return ("…" if debut > 0 else "") + fragment + ("…" if fin < len(texte) else "")


def rechercher(db: Session, user_id: str, q: str, *,
               limit: int = RECHERCHE_RESULTATS) -> list[dict]:
    """Cherche `q` dans le contenu des messages ET le titre des conversations.

    Périmètre : les conversations NON archivées de cet utilisateur — chercher
    dans ce qu'on a rangé hors de vue ferait remonter des fils qu'on a
    justement écartés.

    `func.lower(...).like(...)` plutôt qu'`ILIKE` : `ILIKE` est propre à
    PostgreSQL et la suite de tests tourne sur SQLite. Sur PostgreSQL les deux
    produisent le même plan (aucun index de texte ici : les volumes sont d'un
    utilisateur, pas d'un corpus).
    """
    from sqlalchemy import func

    terme = (q or "").strip()
    if len(terme) < RECHERCHE_MINIMUM:
        raise AppError(f"Saisissez au moins {RECHERCHE_MINIMUM} caractères.",
                       400, code="requete_trop_courte")
    limit = max(1, min(int(limit or RECHERCHE_RESULTATS), RECHERCHE_RESULTATS))
    motif = _motif_like(terme)
    proprietaire = (Conversation.user_id == uuid.UUID(user_id),
                    Conversation.archived_at.is_(None))

    # 1. Messages dont le contenu correspond : chaque message est un point
    #    d'arrivée distinct dans le fil, donc une ligne de résultat distincte.
    lignes = db.execute(
        select(Message.id, Message.content, Message.created_at,
               Conversation.id, Conversation.title, Conversation.project_id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(*proprietaire,
               func.lower(Message.content).like(motif, escape="\\"))
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).all()

    resultats = [{
        "conversation_id": str(conv_id),
        "title": titre,
        "project_id": str(project_id),
        "extrait": _extrait(contenu, terme),
        "message_id": str(msg_id),
        "created_at": cree_le,
    } for msg_id, contenu, cree_le, conv_id, titre, project_id in lignes]

    # 2. Conversations dont le TITRE correspond, sans message déjà remonté :
    #    un fil renommé « Levée de fonds » se trouve par son nom même si le
    #    mot n'apparaît dans aucun message. `message_id` vaut alors `None` —
    #    le front ouvre le fil sans cible à surligner.
    deja = {r["conversation_id"] for r in resultats}
    if len(resultats) < limit:
        for conv in db.scalars(
            select(Conversation)
            .where(*proprietaire,
                   func.lower(Conversation.title).like(motif, escape="\\"))
            .order_by(Conversation.last_message_at.is_(None).asc(),
                      Conversation.last_message_at.desc())
            .limit(limit)
        ):
            if str(conv.id) in deja:
                continue
            resultats.append({
                "conversation_id": str(conv.id),
                "title": conv.title,
                "project_id": str(conv.project_id),
                "extrait": _extrait(conv.title, terme),
                "message_id": None,
                "created_at": conv.last_message_at or conv.created_at,
            })
            if len(resultats) >= limit:
                break

    # Un seul ordre pour les deux origines, sinon la liste se lit comme deux
    # listes collées.
    # Le tuple évite de comparer une date à `None` (un `created_at` manquant
    # ferait lever le tri au lieu de descendre en fin de liste).
    resultats.sort(key=lambda r: (r["created_at"] is not None, r["created_at"]),
                   reverse=True)
    return resultats[:limit]


def _messages_ordonnes(db: Session, conv: Conversation) -> list[Message]:
    """Le fil complet dans l'ordre chronologique.

    `id` en second critère de tri : deux messages écrits dans la même
    microseconde (un seed, un import) donneraient sinon un ordre instable, et
    c'est cet ordre qui décide ce qu'une édition supprime.
    """
    return list(db.scalars(select(Message)
                           .where(Message.conversation_id == conv.id)
                           .order_by(Message.created_at.asc(), Message.id.asc())))


def _supprimer_messages(db: Session, conv: Conversation,
                        messages: list[Message]) -> None:
    """Supprime ces messages, puis recale les compteurs du fil.

    Suppression par `delete()` explicite sur les identifiants, et non par la
    cascade ORM : la cascade ne concerne que la suppression de la CONVERSATION
    entière. Les rendus `viz_rendus` sont laissés en place — cache partagé par
    empreinte, une même figure peut être portée par un rapport ou un autre fil.
    """
    from sqlalchemy import delete, func

    if messages:
        # `synchronize_session="fetch"` : sans lui, les objets supprimés
        # restent vivants dans l'identity map de la session et un accès
        # ultérieur les ferait ressusciter au prochain flush.
        db.execute(delete(Message).where(Message.id.in_([m.id for m in messages])),
                   execution_options={"synchronize_session": "fetch"})
    _recompter(db, conv)
    # `last_message_at` sert au tri du panneau : le laisser dans le futur du
    # fil ferait remonter une conversation qu'on vient de vider.
    conv.last_message_at = db.scalar(
        select(func.max(Message.created_at))
        .where(Message.conversation_id == conv.id))
    # Le résumé roulant est un curseur sur le fil : au-delà du nouveau nombre
    # de messages, il ne se remettrait plus jamais à jour.
    conv.resume_messages = min(conv.resume_messages or 0, conv.message_count)
    if conv.message_count == 0:
        conv.resume, conv.resume_messages = None, 0


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
    # Retroncature APRÈS fusion : deux messages de même rôle concaténés
    # dépassaient la limite (deux fois 1 500 caractères, et plus si le fil
    # enchaîne trois tours du même côté).
    for m in out:
        m["content"] = m["content"][:HISTORIQUE_CARACTERES]
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
    """Résumé roulant INCRÉMENTAL des messages sortis de la fenêtre des 8.

    Ne résume que la tranche `[conv.resume_messages, message_count - 8)` — les
    messages qui viennent de quitter la fenêtre — en donnant le résumé
    précédent comme contexte, puis enregistre la nouvelle couverture. La
    version qui relisait tout le fil à chaque tour envoyait ~35 k tokens
    d'entrée au 100ᵉ message pour produire 900 tokens de sortie, et
    recommençait au tour suivant : le résumé coûtait plus que la réponse.

    Tourne HORS du cycle de requête (voir `_mettre_a_jour_resume_en_tache`).
    Toute erreur est absorbée — un résumé manquant dégrade la mémoire longue,
    il ne casse pas la conversation.
    """
    try:
        total = conv.message_count or 0
        if total <= HISTORIQUE_MESSAGES:
            return
        deja = conv.resume_messages or 0
        fin = total - HISTORIQUE_MESSAGES
        if fin <= deja:
            # Rien de nouveau n'est sorti de la fenêtre depuis le dernier
            # résumé : le second appel au modèle serait payé pour rien.
            return
        tous = list(db.scalars(select(Message)
                               .where(Message.conversation_id == conv.id)
                               .order_by(Message.created_at.asc())))
        anciens = tous[deja:fin]
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
                                  prompt=f"{prefixe}Nouveaux messages à intégrer :\n{corps}",
                                  tier="chat", max_tokens=900)
        texte = " ".join((res.text or "").split())
        if not texte:
            return
        mots = texte.split(" ")
        conv.resume = " ".join(mots[:RESUME_MOTS_MAX]) + ("…" if len(mots) > RESUME_MOTS_MAX else "")
        conv.resume_messages = deja + len(anciens)
        db.commit()
    except Exception as e:  # noqa: BLE001 — jamais bloquant
        logger.warning("Résumé roulant non mis à jour : %s", e)


def _mettre_a_jour_resume_en_tache(conversation_id) -> None:
    """Le résumé roulant, dans son propre thread et sa propre session.

    Le générateur de la réponse n'est pas terminé tant qu'il n'a pas rendu la
    main : Starlette n'envoie le dernier chunk (`more_body: False`) qu'après
    `StopIteration`. Faire le résumé dedans gardait la connexion SSE ouverte —
    et un worker du pool occupé — pendant plusieurs secondes APRÈS le `done`,
    exactement ce que « jamais bloquant » devait éviter. La session de la
    requête, elle, est fermée par `get_db` dès la réponse rendue : ce thread
    ouvre donc la sienne. Ne lève jamais.
    """
    from app.db import SessionLocal

    db = None
    try:
        db = SessionLocal()
        conv = db.get(Conversation, conversation_id)
        if conv is not None:
            _mettre_a_jour_resume(db, conv)
    except Exception as e:  # noqa: BLE001 — un thread qui lève ne prévient personne
        logger.warning("Résumé roulant en tâche de fond abandonné : %s", e)
    finally:
        if db is not None:
            try:
                db.close()
            except Exception as e:  # noqa: BLE001
                logger.warning("Session du résumé non refermée : %s", e)


def _programmer_resume(conv: Conversation) -> None:
    """Lance le résumé roulant en arrière-plan (thread démon)."""
    try:
        threading.Thread(target=_mettre_a_jour_resume_en_tache,
                         args=(conv.id,), daemon=True).start()
    except Exception as e:  # noqa: BLE001 — jamais bloquant
        logger.warning("Résumé roulant non programmé : %s", e)


def verifier_credits(db: Session, user_id: str, *, is_admin: bool) -> None:
    """Solde suffisant pour un tour, sinon 402 nommé.

    Extrait de `_preparer_contexte` pour être appelable AVANT une suppression :
    régénérer ou éditer efface des messages, et découvrir le 402 seulement
    après aurait laissé le fil amputé sans rien avoir régénéré.
    """
    if is_admin:
        return
    from app.modules.billing import service as billing

    chk = billing.check_credits(db, user_id, AGENT_MESSAGE_ACTION)
    if not chk["affordable"]:
        raise AppError(f"Crédits insuffisants ({chk['available']}/{chk['cost']}).",
                       402, code="insufficient_credits")


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
    verifier_credits(db, user_id, is_admin=is_admin)

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
                            # La clé N'EST POSÉE QUE sur une réponse complète :
                            # sinon le rejeu après coupure réseau renvoyait
                            # définitivement le texte tronqué archivé par cette
                            # même coupure, sans jamais rien facturer ni
                            # permettre d'obtenir la réponse entière.
                            cle_idempotence=((cle_idempotence or None)
                                             if statut == "complet" else None))
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


# --- Régénérer / éditer ----------------------------------------------------
#
# Ces deux fonctions ne déroulent PAS de tour : elles nettoient le fil et
# rendent le contenu à (re)jouer. Le tour lui-même repart par
# `stream_message`, c'est-à-dire par le même générateur, la même enveloppe SSE
# du routeur, la même idempotence et les mêmes statuts que l'envoi normal.
# Une seconde implémentation du flux aurait divergé au premier correctif.
#
# Elles sont SYNCHRONES et appelées avant l'ouverture du flux : une régénération
# refusée doit répondre en HTTP (404/409), pas en événement d'erreur dans une
# réponse 200 que le client lit comme un succès.

def preparer_regeneration(db: Session, user_id: str, conversation_id: str,
                          message_id: str, *, is_admin: bool = False) -> str:
    """Retire la dernière réponse ET la question qui l'a produite.

    Rend le contenu de cette question, que l'appelant repasse à
    `stream_message` : le pipeline recrée le message utilisateur puis génère
    une nouvelle réponse, donc le fil retrouve exactement le même nombre de
    messages. Ne supprimer que la réponse laisserait la question en double
    (le pipeline en insère toujours une).

    Seul le DERNIER message peut être régénéré : régénérer au milieu d'un fil
    invaliderait tout ce qui suit, ce que l'édition fait explicitement.
    """
    conv = _own_conversation(db, user_id, conversation_id)
    # Solde vérifié AVANT de supprimer : un 402 découvert dans le flux aurait
    # laissé le fil amputé de la question ET de sa réponse, sans rien produire.
    verifier_credits(db, user_id, is_admin=is_admin)
    tous = _messages_ordonnes(db, conv)
    cible = _uuid_ou_404(message_id, "Message introuvable.")
    index = next((i for i, m in enumerate(tous) if m.id == cible), None)
    if index is None:
        raise AppError("Message introuvable.", 404, code="not_found")
    if tous[index].role != "assistant":
        raise AppError("Seule une réponse d'Axial peut être régénérée.", 400,
                       code="pas_une_reponse")
    if index != len(tous) - 1:
        raise AppError("Seule la dernière réponse du fil peut être régénérée.",
                       409, code="pas_le_dernier_message")
    if index == 0 or tous[index - 1].role != "user":
        raise AppError("La question d'origine est introuvable.", 409,
                       code="question_introuvable")

    question = tous[index - 1].content
    _supprimer_messages(db, conv, [tous[index - 1], tous[index]])
    db.commit()
    return question


def preparer_edition(db: Session, user_id: str, conversation_id: str,
                     message_id: str, content: str, *,
                     is_admin: bool = False) -> None:
    """Retire le message utilisateur visé et TOUT ce qui le suit.

    Éditer une question, c'est repartir de là : les réponses suivantes ont été
    écrites pour l'ancienne formulation et les garder produirait un fil qui se
    contredit. L'appelant relance ensuite un tour normal avec le nouveau texte,
    donc le fil compte `index + 2` messages.
    """
    verifier_longueur(content)
    conv = _own_conversation(db, user_id, conversation_id)
    # Même raison que pour la régénération : rien n'est supprimé avant de
    # savoir que le tour de remplacement est payable.
    verifier_credits(db, user_id, is_admin=is_admin)
    tous = _messages_ordonnes(db, conv)
    cible = _uuid_ou_404(message_id, "Message introuvable.")
    index = next((i for i, m in enumerate(tous) if m.id == cible), None)
    if index is None:
        raise AppError("Message introuvable.", 404, code="not_found")
    if tous[index].role != "user":
        raise AppError("Seul un message que vous avez envoyé peut être modifié.",
                       400, code="pas_un_message_utilisateur")
    _supprimer_messages(db, conv, tous[index:])
    db.commit()


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
        _programmer_resume(turn.conv)
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


def _fermer_flux(flux) -> None:
    """Ferme le générateur du fournisseur, sans jamais lever.

    C'est ce `close()` qui déclenche le `finally` de mesure des adaptateurs
    (Gemini, Claude) : il DOIT être appelé avant de lire le dictionnaire de
    mesure sur un chemin d'interruption.
    """
    if flux is None:
        return
    try:
        flux.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("Flux du fournisseur non refermé : %s", e)


def stream_message(db: Session, user_id: str, conversation_id: str, content: str,
                   agent_override: str | None = None, *, is_admin: bool = False,
                   document_ids: list[str] | None = None,
                   cle_idempotence: str | None = None):
    """`_stream_message`, plus la fermeture garantie de la session.

    `get_db` ferme la session à la fin du cycle de requête, c'est-à-dire AVANT
    que le corps de ce générateur ne démarre (il tourne dans le thread de la
    réponse). Le premier accès ORM la ressuscite, et plus personne ne la
    referme : la transaction ouverte par `_finalize_turn` retenait sa connexion
    jusqu'au ramasse-miettes. `close()` est idempotent, l'appeler ici ne gêne
    pas `get_db`.
    """
    try:
        yield from _stream_message(db, user_id, conversation_id, content,
                                   agent_override, is_admin=is_admin,
                                   document_ids=document_ids,
                                   cle_idempotence=cle_idempotence)
    finally:
        try:
            db.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Session non refermée en fin de flux : %s", e)


def _stream_message(db: Session, user_id: str, conversation_id: str, content: str,
                    agent_override: str | None = None, *, is_admin: bool = False,
                    document_ids: list[str] | None = None,
                    cle_idempotence: str | None = None):
    """Same turn as post_message, but the answer arrives word by word.

    Order matters: the citations are sent BEFORE the first word, so the reader
    can already see what the answer is built on while it is being written.

    **Déconnexion du client** (bouton Stop, onglet fermé) : rien n'est sondé
    ici. Le routeur enveloppe ce générateur dans un générateur ASYNC et appelle
    `close()` dessus dans un `finally` ; Starlette ferme ce générateur async dès
    que le client part, donc `GeneratorExit` est levé au `yield` courant,
    ENCORE DANS LE SCOPE DE LA REQUÊTE (la session `get_db` est toujours
    ouverte). Le sondage précédent lisait le même `receive` que la tâche
    `listen_for_disconnect` de Starlette — une course non déterministe — et
    l'archivage se retrouvait à tourner sur une session déjà fermée.
    Le handler `except GeneratorExit` archive le texte écrit en
    `statut='partiel'`, sans facturer : l'utilisateur retrouve ce qu'il a vu
    passer.
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
    flux = None
    try:
        prompt_flux, hist_flux = turn.prompt, list(turn.history)
        for reprise in range(REPRISES_FLUX_MAX + 1):
            flux = llm_client.stream_text(system=turn.system, prompt=prompt_flux,
                                          tier=turn.tier, history=hist_flux,
                                          mesure=compte_tokens,
                                          max_tokens=turn.max_tokens)
            raison = None
            while True:
                try:
                    chunk = next(flux)
                except StopIteration as fin:
                    raison = fin.value
                    break
                chunks.append(chunk)
                yield _sse({"step": "delta", "delta": chunk})
            if raison != "max_tokens":
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
    except GeneratorExit:
        # SEUL chemin de détection du départ du client : le routeur ferme ce
        # générateur (via son enveloppe async), `GeneratorExit` est levé au
        # `yield` courant et la session de la requête est encore ouverte. On
        # archive AVANT de laisser la fermeture se poursuivre — c'est
        # exactement ce qui faisait perdre un rapport le 25/08. Aucun `yield`
        # n'est permis ici, d'où l'absence de `done`.
        #
        # Fermer le flux du fournisseur AVANT de lire `compte_tokens` : la frame
        # de ce générateur est encore vivante, donc rien n'a fermé `flux` et le
        # `finally` de mesure du fournisseur n'a pas tourné — le partiel était
        # archivé sans tokens ni coût, alors que le fournisseur les a facturés.
        _fermer_flux(flux)
        if chunks:
            chunks.append(NOTE_INTERROMPUE)
            # Jamais d'exception hors d'un `close()` : une erreur de base ici
            # (un `IntegrityError` sur la clé d'idempotence, par exemple)
            # remplacerait l'annulation par une trace bruyante côté serveur,
            # sans rien sauver de plus.
            try:
                _finalize_turn(db, user_id, turn, "".join(chunks), is_admin=is_admin,
                               statut="partiel", cle_idempotence=cle_idempotence,
                               mesure=llm_client.resultat_de_mesure(compte_tokens))
                logger.info("Flux fermé par le client — réponse partielle archivée")
            except Exception as archivage:  # noqa: BLE001
                logger.warning("Archivage du partiel impossible : %s", archivage)
        raise
    except Exception as e:
        logger.warning("Agent stream failed: %s", e)
        # Même raison que ci-dessus : l'erreur peut venir d'ailleurs que du
        # fournisseur (un `yield` refusé, par exemple) et laisser son flux
        # ouvert, donc sa mesure non cumulée.
        _fermer_flux(flux)
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
        _programmer_resume(turn.conv)


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
