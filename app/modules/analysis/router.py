"""Analysis endpoints.

  GET  /analysis/types            → available analysis types
  POST /analysis/run              → run one analysis (synchronous)
  POST /analysis/stream           → run one analysis (SSE, live progress)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.analysis import service
from app.modules.analysis.schemas import AnalysisRequest, AnalysisResponse, available_types
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user

logger = logging.getLogger("axial.analysis.router")

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/types")
def types() -> dict:
    return {"types": available_types()}


@router.post("/run", response_model=AnalysisResponse)
def run(payload: AnalysisRequest, user: AuthUser = Depends(get_current_user),
        db: Session = Depends(get_db)) -> AnalysisResponse:
    # Check affordability before spending the API call.
    service.precheck_credits(db, user.id, payload.analysis_type, is_admin=user.is_admin)
    # Inject the company-profile memory context automatically.
    from app.modules.memory import service as memory
    company_context = memory.build_context(db, user.id)
    result = service.run_analysis(
        query=payload.query, analysis_type=payload.analysis_type,
        user_id=user.id, title=payload.title, top_k=payload.top_k,
        company_context=company_context, profile=service._profile_dict(db, user.id),
        db_pour_notion=db,
    )
    # Charge + archive + track (no-op on degraded results).
    info = service.finalize(db, user.id, payload.analysis_type, result, is_admin=user.is_admin)
    return AnalysisResponse(
        analysis_type=result.analysis_type, title=result.title, content=result.content,
        report_id=(info or {}).get("report_id"),
        sources=result.sources, degraded=result.degraded,
        status_note=result.status_note, metadata=result.metadata,
    )


@router.post("/premier-rapport", status_code=202)
def premier_rapport(user: AuthUser = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    """Lance le rapport offert à l'inscription, en arrière-plan.

    On répond immédiatement : une étude de fond demande plusieurs minutes, et
    faire patienter quelqu'un dans son onboarding est le meilleur moyen de le
    perdre. Il entre dans l'app, le rapport arrive par email.
    """
    import threading

    from app.db import SessionLocal
    from app.modules.analysis import onboarding

    if onboarding.deja_offert(db, user.id):
        return {"lance": False, "raison": "deja_offert"}
    if not onboarding.profil_utilisable(db, user.id):
        return {"lance": False, "raison": "profil_incomplet"}

    def _travail(uid: str) -> None:
        # Session propre : celle de la requête meurt avec la réponse HTTP.
        with SessionLocal() as db_thread:
            try:
                onboarding.offrir(db_thread, uid)
            except Exception:
                logger.warning("Premier rapport échoué pour %s", uid, exc_info=True)

    threading.Thread(target=_travail, args=(user.id,), daemon=True).start()
    return {"lance": True}


@router.post("/stream")
def stream(payload: AnalysisRequest, user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> StreamingResponse:
    generator = service.stream_analysis(
        db=db, user_id=user.id, is_admin=user.is_admin, query=payload.query,
        analysis_type=payload.analysis_type, title=payload.title, top_k=payload.top_k,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
