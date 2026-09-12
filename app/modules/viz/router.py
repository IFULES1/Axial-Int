"""Images des visualisations et rendu à la volée pour le chat.

Les images ne sont PLUS publiques (spec §5.3). L'empreinte était le seul
secret, mais elle n'en est pas un : c'est le sha256 du spec Vega-Lite compilé,
donc la même série de chiffres produit la même empreinte chez tout le monde —
deviner l'image d'un graphique standard (« CA 2023-2026 » d'un secteur) était
à portée d'un dictionnaire. Deux clés désormais :

* un utilisateur authentifié (en-tête `Authorization`) ;
* ou `?p=<jeton de partage>`, et l'empreinte doit appartenir au rapport que ce
  jeton ouvre — un jeton n'autorise pas « toutes les images », seulement les
  siennes.

`Cache-Control: private, max-age=3600` : une heure dans le navigateur de celui
qui a le droit, jamais dans un cache partagé.

Le PDF et l'email ne passent PAS par ces routes (`render.vers_png` en direct,
corps d'email en texte) : ils ne sont donc pas concernés par la restriction.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user, get_current_user_optionnel
from app.modules.viz import pipeline, render, service
from app.modules.viz.schema import VizSpec

router = APIRouter(prefix="/viz", tags=["viz"])
# Privé et court : l'image reste dans le cache du navigateur autorisé (une page
# de rapport en affiche plusieurs, on ne les recompile pas à chaque défilement)
# mais aucun proxy partagé ne la conserve.
_PRIVE = {"Cache-Control": "private, max-age=3600"}


def _autoriser(db: Session, empreinte: str, jeton: str | None,
               user: AuthUser | None) -> None:
    """Lève sauf si l'appelant a le droit de voir CETTE image.

    L'authentification est optionnelle mais pas facultative : un jeton présent
    et invalide a déjà levé un 401 dans la dépendance.

    Un compte authentifié ne voit que SES graphiques (ses rapports, ses
    messages) — un admin voit tout. Sans cette restriction, l'authentification
    seule suffisait à lire l'image de n'importe quel compte : l'empreinte est
    le sha256 du spec compilé, donc devinable pour des données standard.
    """
    if user is not None:
        if user.is_admin or empreinte in service.empreintes_du_compte(db, user.id):
            return
        if jeton:
            from app.modules.reports import service as reports

            if empreinte in reports.empreintes_partagees(db, jeton):
                return
        # 404 et non 403 : on ne confirme pas l'existence d'une image qui
        # n'appartient pas à ce compte.
        raise AppError("Graphique introuvable.", 404, code="not_found")
    if jeton:
        from app.modules.reports import service as reports

        if empreinte in reports.empreintes_partagees(db, jeton):
            return
        # 404 et non 403 : on ne confirme pas l'existence d'une image qu'un
        # jeton périmé ne couvre pas.
        raise AppError("Graphique introuvable.", 404, code="not_found")
    raise AppError("Authentification requise.", 401, code="not_authenticated")


def _vl(db: Session, empreinte: str, jeton: str | None,
        user: AuthUser | None) -> dict:
    if len(empreinte) != 64 or any(c not in "0123456789abcdef" for c in empreinte):
        raise AppError("Graphique introuvable.", 404, code="not_found")
    # L'autorisation AVANT la lecture : sinon l'existence d'une empreinte se
    # lirait dans la différence entre un 404 et un 401.
    _autoriser(db, empreinte, jeton, user)
    vl = service.rendu_par_empreinte(db, empreinte)
    if not vl:
        raise AppError("Graphique introuvable.", 404, code="not_found")
    return vl


@router.get("/{empreinte}.svg")
def svg(empreinte: str, p: str | None = Query(default=None),
        db: Session = Depends(get_db),
        user: AuthUser | None = Depends(get_current_user_optionnel)) -> Response:
    return Response(render.vers_svg(_vl(db, empreinte, p, user)),
                    media_type="image/svg+xml", headers=_PRIVE)


@router.get("/{empreinte}.png")
def png(empreinte: str, p: str | None = Query(default=None),
        db: Session = Depends(get_db),
        user: AuthUser | None = Depends(get_current_user_optionnel)) -> Response:
    return Response(render.vers_png(_vl(db, empreinte, p, user)),
                    media_type="image/png", headers=_PRIVE)


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
