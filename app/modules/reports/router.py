"""Report endpoints — archive of past analyses + PDF export."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.reports import service

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str
    analysis_type: str = "synthese_executive"
    sources: list | None = None


class ReportOut(BaseModel):
    id: str
    title: str
    analysis_type: str
    created_at: dt.datetime
    # La liste doit pouvoir afficher une génération en cours avec sa barre de
    # progression, sans charger le contenu de chaque rapport.
    statut: str = "termine"
    etape: str | None = None
    progression: int = 100


class ReportDetail(ReportOut):
    content: str
    sources: list | None
    viz: list | None = None
    detail: dict = Field(default_factory=dict)
    question: str | None = None
    termine_at: dt.datetime | None = None
    annulation_demandee: bool = False
    credits: int | None = None
    tokens_entree: int | None = None
    tokens_sortie: int | None = None


class RelanceIn(BaseModel):
    """« Modifier et relancer » / « Recherche élargie » / « Générer quand même »."""

    question: str | None = Field(default=None, max_length=4000)
    elargir: bool = False
    forcer: bool = False


@router.post("", response_model=ReportDetail)
def create(payload: ReportIn, user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> ReportDetail:
    r = service.create_report(db, user.id, title=payload.title, content=payload.content,
                              analysis_type=payload.analysis_type, sources=payload.sources)
    return ReportDetail(**service.detail_dict(r))


@router.get("", response_model=list[ReportOut])
def list_all(user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> list[ReportOut]:
    return [
        ReportOut(id=str(r.id), title=r.title, analysis_type=r.analysis_type,
                  created_at=r.created_at, statut=r.statut, etape=r.etape,
                  progression=r.progression)
        for r in service.list_reports(db, user.id)
    ]


@router.get("/{report_id}", response_model=ReportDetail)
def get_one(report_id: str, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> ReportDetail:
    # La génération écrit depuis une AUTRE session : clore la transaction de
    # lecture puis vider le cache d'identité, sinon le polling du front relit
    # son propre instantané et voit une progression figée.
    db.rollback()
    db.expire_all()
    r = service.get_report(db, user.id, report_id)
    return ReportDetail(**service.detail_dict(r))


@router.post("/{report_id}/annuler", response_model=ReportDetail)
def annuler(report_id: str, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> ReportDetail:
    """Stop. Pose le drapeau ; la tâche range le rapport en `annule`."""
    r = service.demander_annulation(db, user.id, report_id)
    return ReportDetail(**service.detail_dict(r))


@router.post("/{report_id}/relancer", response_model=ReportDetail)
def relancer(report_id: str, payload: RelanceIn | None = None,
             user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> ReportDetail:
    """Crée un NOUVEAU rapport à partir d'un rapport existant.

    L'ancien n'est jamais écrasé (spec §1) : on veut pouvoir comparer, et un
    rapport payé ne disparaît pas parce qu'on en relance un autre.
    """
    from app.modules.analysis import service as analysis
    from app.modules.reports import models as rm

    options = payload or RelanceIn()
    ancien = service.get_report(db, user.id, report_id)
    if ancien.statut == rm.EN_COURS:
        raise AppError("Ce rapport est encore en cours.", 409,
                       code="rapport_en_cours")
    question = (options.question or ancien.question or ancien.title or "").strip()
    if not question:
        raise AppError("Ce rapport n'a pas de question à relancer.", 400,
                       code="question_absente")
    nouveau = analysis.lancer_rapport(
        db, user.id, query=question, analysis_type=ancien.analysis_type,
        title=None, is_admin=user.is_admin, elargir=options.elargir,
        forcer=options.forcer,
    )
    return ReportDetail(**service.detail_dict(nouveau))


@router.get("/{report_id}/pdf")
def export_pdf(report_id: str, user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> StreamingResponse:
    import io

    pdf = service.export_pdf(db, user.id, report_id)
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.pdf"'},
    )


@router.delete("/{report_id}", status_code=204, response_class=Response)
def delete_one(report_id: str, user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> Response:
    service.delete_report(db, user.id, report_id)
    return Response(status_code=204)
