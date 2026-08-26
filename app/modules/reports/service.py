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


def list_reports(db: Session, user_id: str) -> list[Report]:
    stmt = (
        select(Report)
        .where(Report.user_id == uuid.UUID(user_id))
        .order_by(Report.created_at.desc())
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
    return render_pdf(report.title, report.content)
