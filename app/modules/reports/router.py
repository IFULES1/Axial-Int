"""Report endpoints — archive of past analyses + PDF export."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
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


class ReportDetail(ReportOut):
    content: str
    sources: list | None


@router.post("", response_model=ReportDetail)
def create(payload: ReportIn, user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> ReportDetail:
    r = service.create_report(db, user.id, title=payload.title, content=payload.content,
                              analysis_type=payload.analysis_type, sources=payload.sources)
    return ReportDetail(id=str(r.id), title=r.title, analysis_type=r.analysis_type,
                        created_at=r.created_at, content=r.content, sources=r.sources)


@router.get("", response_model=list[ReportOut])
def list_all(user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> list[ReportOut]:
    return [
        ReportOut(id=str(r.id), title=r.title, analysis_type=r.analysis_type,
                  created_at=r.created_at)
        for r in service.list_reports(db, user.id)
    ]


@router.get("/{report_id}", response_model=ReportDetail)
def get_one(report_id: str, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> ReportDetail:
    r = service.get_report(db, user.id, report_id)
    return ReportDetail(id=str(r.id), title=r.title, analysis_type=r.analysis_type,
                        created_at=r.created_at, content=r.content, sources=r.sources)


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
