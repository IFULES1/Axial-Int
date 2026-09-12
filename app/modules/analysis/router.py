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
from app.modules.analysis.schemas import AnalysisRequest, available_types
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.reports.router import ReportDetail

logger = logging.getLogger("axial.analysis.router")

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/types")
def types() -> dict:
    return {"types": available_types()}


@router.post("/run", response_model=ReportDetail)
def run(payload: AnalysisRequest, user: AuthUser = Depends(get_current_user),
        db: Session = Depends(get_db)) -> ReportDetail:
    """Chemin bloquant — repli du flux (arbitrage §0).

    Ce n'est plus une seconde implémentation : la route crée la ligne de
    rapport, appelle le MÊME moteur suivi par identifiant et attend son terme.
    Le moteur ouvre sa propre session ; la propriété de survie est la sienne,
    et un seul test la couvre.
    """
    from app.modules.reports import service as reports

    # `elargir` / `forcer` transmis comme sur `/stream` : « Recherche élargie »
    # et « Générer quand même » doivent marcher sur les deux chemins, sinon le
    # repli du flux perd les deux boutons de la spec §2.
    rapport = service.lancer_rapport(
        db, user.id, query=payload.query, analysis_type=payload.analysis_type,
        title=payload.title, top_k=payload.top_k, is_admin=user.is_admin,
        elargir=payload.elargir, forcer=payload.forcer, attendre=True,
    )
    return ReportDetail(**reports.detail_dict(rapport, is_admin=user.is_admin))


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
        elargir=payload.elargir, forcer=payload.forcer,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
