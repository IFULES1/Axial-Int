"""Report service: persist, list, get, delete, export to PDF."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.reports.models import Report
from app.modules.reports.pdf import render_pdf


def create_report(db: Session, user_id: str, *, title: str, content: str,
                  analysis_type: str = "synthese_executive",
                  sources: list | None = None, cout: dict | None = None) -> Report:
    """`cout` porte la mesure de production : tokens, modèle, prix, durée."""
    c = cout or {}
    report = Report(id=uuid.uuid4(), user_id=uuid.UUID(user_id), title=title,
                    content=content, analysis_type=analysis_type, sources=sources,
                    tokens_entree=c.get("tokens_entree"),
                    tokens_sortie=c.get("tokens_sortie"),
                    cout_micro_eur=c.get("cout_micro_eur"),
                    modele=c.get("modele"),
                    duree_secondes=c.get("duree_secondes"),
                    cout_recherche_micro_eur=c.get("cout_recherche_micro_eur"),
                    appels_recherche=c.get("appels_recherche"))
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def detail_dict(report: Report) -> dict:
    """Forme unique du `ReportDetail` — l'API et le flux SSE en rendent la même.

    Un seul constructeur : la route `GET /reports/{id}` et l'événement `done`
    du flux décrivaient le même rapport avec deux jeux de clés, et le front
    devait connaître les deux.
    """
    return {
        "id": str(report.id),
        "title": report.title,
        "analysis_type": report.analysis_type,
        "created_at": report.created_at,
        "content": report.content or "",
        "sources": report.sources if isinstance(report.sources, list) else None,
        "viz": report.viz if isinstance(report.viz, list) else None,
        "statut": report.statut,
        "etape": report.etape,
        "progression": report.progression,
        "detail": report.detail or {},
        "question": report.question,
        "termine_at": report.termine_at,
        "annulation_demandee": bool(report.annulation_demandee),
        # Le coût est ce que l'utilisateur a payé — les crédits, pas les euros.
        # Le prix de revient (`cout_micro_eur`, coût de recherche) reste réservé
        # à l'administration (spec §4) et n'apparaît pas ici.
        "credits": (report.detail or {}).get("credits"),
        "tokens_entree": report.tokens_entree,
        "tokens_sortie": report.tokens_sortie,
    }


def demander_annulation(db: Session, user_id: str, report_id: str) -> Report:
    """Pose le drapeau de Stop. La tâche le relit et range le rapport.

    La route ne tue rien elle-même : la tâche tourne dans un autre thread (et
    potentiellement un autre processus), le seul canal fiable est la base.
    Idempotent — cliquer deux fois ne change rien.
    """
    from app.modules.reports import models as rm

    report = get_report(db, user_id, report_id)
    if report.statut != rm.EN_COURS:
        raise AppError("Ce rapport n'est plus en cours.", 409,
                       code="rapport_non_en_cours")
    report.annulation_demandee = True
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: Session, user_id: str) -> list[Report]:
    # Les rapports en cours remontent en tête : c'est ce que l'utilisateur
    # attend, et il doit pouvoir rouvrir une génération lancée ailleurs.
    from app.modules.reports.models import EN_COURS

    stmt = (
        select(Report)
        .where(Report.user_id == uuid.UUID(user_id))
        .order_by((Report.statut != EN_COURS), Report.created_at.desc())
    )
    return list(db.scalars(stmt))


def get_report(db: Session, user_id: str, report_id: str) -> Report:
    report = db.get(Report, uuid.UUID(report_id))
    if not report or str(report.user_id) != user_id:
        raise AppError("Rapport introuvable.", 404, code="not_found")
    return report


def delete_report(db: Session, user_id: str, report_id: str) -> None:
    report = get_report(db, user_id, report_id)
    db.delete(report)
    db.commit()


def export_pdf(db: Session, user_id: str, report_id: str) -> bytes:
    report = get_report(db, user_id, report_id)
    # `sources` est un JSON : liste de citations, ou parfois un scalaire sur
    # d'anciens rapports restaurés — dans ce cas, pas de section Sources.
    sources = report.sources if isinstance(report.sources, list) else None
    vizs = report.viz if isinstance(report.viz, list) else None
    return render_pdf(report.title, report.content, sources=sources, vizs=vizs)
