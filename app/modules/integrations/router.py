"""Endpoints des intégrations : autoriser, retour OAuth, état, déconnexion."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.integrations import service

logger = logging.getLogger("axial.integrations")
router = APIRouter(prefix="/integrations", tags=["integrations"])

def _signer_state(user_id: str) -> str:
    """`state` OAuth signé plutôt que stocké.

    Il lie le retour du fournisseur à l'utilisateur qui a lancé la demande. Le
    garder en mémoire le rendait fragile : un redémarrage du backend pendant
    l'autorisation, ou un second processus web, et la connexion échouait sans
    raison visible. Signé, il n'a besoin d'aucun stockage partagé.
    """
    import datetime as dt

    import jwt

    settings = get_settings()
    return jwt.encode(
        {"sub": user_id, "typ": "oauth_state",
         "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)},
        settings.supabase_jwt_secret, algorithm="HS256")


def _verifier_state(state: str) -> str | None:
    import jwt

    settings = get_settings()
    try:
        claims = jwt.decode(state, settings.supabase_jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    return claims.get("sub") if claims.get("typ") == "oauth_state" else None


@router.get("/status")
def status(user: AuthUser = Depends(get_current_user),
           db: Session = Depends(get_db)) -> dict:
    return service.etat(db, user.id)


@router.post("/{provider}/authorize")
def authorize(provider: str, user: AuthUser = Depends(get_current_user)) -> dict:
    if provider not in ("notion", "google"):
        raise AppError("Outil inconnu.", 404, code="unknown_provider")
    state = _signer_state(user.id)
    return {"authorize_url": service.url_autorisation(provider, state)}


@router.get("/{provider}/callback")
def callback(provider: str, code: str = "", state: str = "",
             db: Session = Depends(get_db)) -> RedirectResponse:
    """Retour du fournisseur : on échange le code puis on renvoie dans l'app."""
    user_id = _verifier_state(state)
    if not user_id or not code:
        return RedirectResponse(f"{service.BASE_PUBLIQUE}/?integration=echec")
    try:
        jeton = service.echanger_code(provider, code)
        service.enregistrer(db, user_id, provider, jeton)
    except Exception as e:  # noqa: BLE001
        logger.warning("Connexion %s échouée : %s", provider, e)
        return RedirectResponse(f"{service.BASE_PUBLIQUE}/?integration=echec")
    return RedirectResponse(f"{service.BASE_PUBLIQUE}/?integration={provider}")


@router.delete("/{provider}", status_code=204)
def disconnect(provider: str, user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)):
    from fastapi import Response

    service.deconnecter(db, user.id, provider)
    return Response(status_code=204)


class LivraisonIn(BaseModel):
    report_id: str


@router.post("/notion/deliver")
def deliver_notion(payload: LivraisonIn, user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    """Publier un rapport archivé sous forme de page Notion."""
    from app.modules.integrations import delivery
    from app.modules.reports import service as reports

    jeton = service.jeton_actif(db, user.id, "notion")
    if not jeton:
        raise AppError("Notion n'est pas connecté.", 400, code="not_connected")
    rapport = reports.get_report(db, user.id, payload.report_id)
    url = delivery.vers_notion(jeton, rapport.title, rapport.content)
    return {"url": url}


@router.post("/google/deliver")
def deliver_drive(payload: LivraisonIn, user: AuthUser = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict:
    """Déposer le PDF d'un rapport archivé dans Google Drive."""
    from app.modules.integrations import delivery
    from app.modules.reports import service as reports

    jeton = service.jeton_actif(db, user.id, "google")
    if not jeton:
        raise AppError("Google Drive n'est pas connecté.", 400, code="not_connected")
    rapport = reports.get_report(db, user.id, payload.report_id)
    contenu = reports.export_pdf(db, user.id, payload.report_id)
    return {"url": delivery.vers_drive(jeton, rapport.title, contenu)}
