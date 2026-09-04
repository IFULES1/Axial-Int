"""Export d'une conversation en Markdown ou en PDF.

Le Markdown est la source : le PDF en est rendu. Une seule mise en forme à
maintenir, et les deux fichiers disent exactement la même chose.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import text

_ROLES = {"user": "Question", "assistant": "Axial"}


_TITRES_PAR_DEFAUT = {"workspace", "conversation", "nouvelle conversation",
                      "new conversation", "nouvelle analyse", "new analysis", ""}


def _titre_utile(titre: str | None, messages) -> str:
    """Titre stocké s'il est parlant, sinon la première question posée."""
    t = (titre or "").strip()
    if t.lower() not in _TITRES_PAR_DEFAUT:
        return t
    for m in messages:
        if m["role"] == "user" and (m["content"] or "").strip():
            premiere = " ".join((m["content"] or "").split())
            return premiere[:80].rstrip() + ("…" if len(premiere) > 80 else "")
    return "Conversation"


def _entete(titre: str, quand: dt.datetime | None, n: int) -> str:
    date = (quand or dt.datetime.now(dt.timezone.utc)).strftime("%d/%m/%Y")
    return (f"# {titre}\n\n"
            f"*Conversation Axial — {date} — {n} message(s)*\n\n---\n\n")


def markdown(db, user_id: str, conversation_id: str) -> tuple[str, str]:
    """Retourne (titre, markdown). Lève si la conversation n'appartient pas."""
    from app.errors import AppError

    conv = db.execute(text("""
        SELECT id, title, created_at FROM conversations
        WHERE id = :c AND user_id = :u
    """), {"c": conversation_id, "u": user_id}).mappings().first()
    if not conv:
        raise AppError("Conversation introuvable.", 404, code="not_found")

    messages = db.execute(text("""
        SELECT role, content, agent, citations, created_at
        FROM messages WHERE conversation_id = :c ORDER BY created_at
    """), {"c": conversation_id}).mappings().all()

    # Les conversations gardent souvent leur titre par défaut. L'interface
    # affiche alors la première question ; l'export doit faire pareil, sinon
    # tous les fichiers s'appellent « workspace » dans le dossier de
    # téléchargements.
    titre = _titre_utile(conv["title"], messages)
    parties = [_entete(titre, conv["created_at"], len(messages))]

    for m in messages:
        contenu = (m["content"] or "").strip()
        if not contenu:
            continue
        role = _ROLES.get(m["role"], m["role"])
        parties.append(f"## {role}\n\n{contenu}\n")

        # Les sources sont attachées au message, pas à la conversation : les
        # regrouper en fin de document ferait perdre à quelle réponse elles
        # se rapportent.
        sources = m["citations"] if isinstance(m["citations"], list) else None
        if sources:
            parties.append("\n**Sources**\n")
            for i, s in enumerate(sources, 1):
                if not isinstance(s, dict):
                    continue
                titre_s = s.get("title") or s.get("domain") or "Source"
                url = s.get("url")
                parties.append(f"{i}. {titre_s}" + (f" — {url}" if url else ""))
            parties.append("")
        parties.append("\n---\n")

    return titre, "\n".join(parties).rstrip() + "\n"


def pdf(db, user_id: str, conversation_id: str) -> tuple[str, bytes]:
    """Même contenu que le Markdown, rendu en PDF."""
    from app.modules.reports.pdf import render_pdf

    titre, md = markdown(db, user_id, conversation_id)
    # Le titre est déjà en tête du Markdown : le repasser à render_pdf le
    # ferait apparaître deux fois.
    corps = md.split("\n", 1)[1] if md.startswith("# ") else md
    return titre, render_pdf(titre, corps)
