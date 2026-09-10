"""Images des visualisations et rendu à la volée pour le chat.

Les images sont publiques : l'empreinte (64 hex) est le secret, comme un
lien de partage. Sans ça, ni l'email de veille ni une balise <img> ne
pourraient les charger.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.viz import pipeline, render, service
from app.modules.viz.schema import VizSpec

router = APIRouter(prefix="/viz", tags=["viz"])
_IMMUABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _vl(db: Session, empreinte: str) -> dict:
    if len(empreinte) != 64 or any(c not in "0123456789abcdef" for c in empreinte):
        raise AppError("Graphique introuvable.", 404, code="not_found")
    vl = service.rendu_par_empreinte(db, empreinte)
    if not vl:
        raise AppError("Graphique introuvable.", 404, code="not_found")
    return vl


@router.get("/{empreinte}.svg")
def svg(empreinte: str, db: Session = Depends(get_db)) -> Response:
    return Response(render.vers_svg(_vl(db, empreinte)), media_type="image/svg+xml", headers=_IMMUABLE)


@router.get("/{empreinte}.png")
def png(empreinte: str, db: Session = Depends(get_db)) -> Response:
    return Response(render.vers_png(_vl(db, empreinte)), media_type="image/png", headers=_IMMUABLE)


@router.post("/rendu")
def rendu(spec: VizSpec, user: AuthUser = Depends(get_current_user),
          db: Session = Depends(get_db)) -> dict:
    """Chat en flux : le navigateur envoie le bloc dès qu'il est fermé."""
    v = pipeline.compiler_spec(0, spec)
    if v.vl:
        service.preparer(db, "```viz\n" + spec.model_dump_json() + "\n```")
        db.commit()
    return {
        "empreinte": v.empreinte or None, "kind": v.kind, "statut": v.statut,
        "svg": render.vers_svg(v.vl) if v.vl else None,
        "tableau": None if v.vl else pipeline.tableau_de_repli(v.spec),
    }
