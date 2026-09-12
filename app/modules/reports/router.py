"""Report endpoints — archive of past analyses, management, sharing, export."""
from __future__ import annotations

import datetime as dt
import io

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_admin, get_current_user
from app.modules.reports import service

router = APIRouter(prefix="/reports", tags=["reports"])

# Le partage est PUBLIC : pas de `get_current_user`, donc pas de dépendance
# d'authentification à retirer par erreur d'une route de ce routeur-ci. Deux
# routeurs séparés rendent la frontière visible dans le code et dans l'OpenAPI.
router_public = APIRouter(prefix="/partage", tags=["partage"])


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
    # progression, le coût payé et le dossier, sans charger le contenu de
    # chaque rapport.
    statut: str = "termine"
    etape: str | None = None
    progression: int = 100
    credits: int | None = None
    tokens_entree: int | None = None
    tokens_sortie: int | None = None
    project_id: str | None = None
    pinned_at: dt.datetime | None = None
    archived_at: dt.datetime | None = None


class ReportPage(BaseModel):
    """Fenêtre de liste. `has_more` dit s'il faut proposer « Charger plus » —
    un utilisateur à 400 rapports en recevait 400 à chaque ouverture."""

    items: list[ReportOut]
    has_more: bool = False


class ReportDetail(ReportOut):
    content: str
    sources: list | None
    viz: list | None = None
    detail: dict = Field(default_factory=dict)
    question: str | None = None
    termine_at: dt.datetime | None = None
    annulation_demandee: bool = False
    jeton_partage: str | None = None
    partage_at: dt.datetime | None = None
    # Prix de revient — ADMIN seulement (spec §4). Absent du dict pour un
    # utilisateur normal, donc `None` ici, jamais la vraie valeur.
    cout_micro_eur: int | None = None
    cout_recherche_micro_eur: int | None = None


class ReportPatch(BaseModel):
    """Renommer / archiver / épingler / classer : quatre attributs de la même
    ligne, un seul endpoint (sémantique PATCH, champ absent = inchangé)."""

    title: str | None = Field(default=None, max_length=300)
    archived: bool | None = None
    pinned: bool | None = None
    project_id: str | None = None


class RechercheOut(BaseModel):
    id: str
    title: str
    analysis_type: str
    created_at: dt.datetime
    statut: str
    extrait: str


class PartageOut(BaseModel):
    jeton: str
    # Chemin relatif : l'URL publique du front n'est pas une donnée du backend.
    url: str


class RapportPublic(BaseModel):
    """Vue publique — liste blanche stricte (spec §0) : ni coût, ni question,
    ni `detail`, ni sources internes."""

    title: str
    content: str
    sources: list | None = None
    viz: list | None = None
    analysis_type: str
    created_at: dt.datetime
    pseudo: str


class FeedbackIn(BaseModel):
    note: int | None = Field(default=None, ge=1, le=5)
    motif: str = Field(min_length=1, max_length=32)
    commentaire: str | None = Field(default=None, max_length=4000)


class FeedbackOut(BaseModel):
    id: str
    motif: str
    note: int | None = None
    created_at: dt.datetime


class RelanceIn(BaseModel):
    """« Modifier et relancer » / « Recherche élargie » / « Générer quand même »."""

    question: str | None = Field(default=None, max_length=4000)
    elargir: bool = False
    forcer: bool = False


# `POST /reports` est réservé aux ADMINISTRATEURS (spec §5.2). Depuis Task 2,
# chaque rapport naît d'une ligne créée par le moteur et porte donc déjà un
# identifiant : la seule raison d'être de cette route était le repli
# « sauvegarder avant de livrer » de l'éditeur front, devenu inutile. Elle est
# conservée — et non supprimée — parce que l'import d'un rapport rédigé hors
# moteur (reprise manuelle, rattrapage d'un compte) n'a pas d'autre chemin.
@router.post("", response_model=ReportDetail)
def create(payload: ReportIn, user: AuthUser = Depends(get_current_admin),
           db: Session = Depends(get_db)) -> ReportDetail:
    r = service.create_report(db, user.id, title=payload.title, content=payload.content,
                              analysis_type=payload.analysis_type, sources=payload.sources)
    return ReportDetail(**service.detail_dict(r, is_admin=user.is_admin))


@router.get("", response_model=ReportPage)
def list_all(limit: int = Query(default=service.LISTE_LIMITE_DEFAUT, ge=1,
                                le=service.LISTE_LIMITE_MAX),
             before: str | None = Query(default=None),
             inclure_archives: bool = Query(default=False),
             user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> ReportPage:
    """En cours d'abord, puis épinglés, puis par date décroissante."""
    items, has_more = service.list_reports(
        db, user.id, limit=limit, before=before,
        inclure_archives=inclure_archives)
    return ReportPage(items=[ReportOut(**service.resume_dict(r)) for r in items],
                      has_more=has_more)


# `search` est déclaré AVANT `/{report_id}` : FastAPI résout dans l'ordre de
# déclaration, et « search » serait sinon pris pour un identifiant de rapport.
# `q` a une valeur par défaut pour que l'absence de requête rende le 400
# `requete_trop_courte` annoncé par le contrat, et non un 422 pydantic.
@router.get("/search", response_model=list[RechercheOut])
def rechercher(q: str = Query(default=""),
               user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> list[RechercheOut]:
    """Titre + contenu des rapports non archivés, 20 résultats au plus,
    3 caractères au moins, extrait de ±80 caractères."""
    return [RechercheOut(**r) for r in service.rechercher(db, user.id, q)]


@router.get("/{report_id}", response_model=ReportDetail)
def get_one(report_id: str, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> ReportDetail:
    # La génération écrit depuis une AUTRE session : clore la transaction de
    # lecture puis vider le cache d'identité, sinon le polling du front relit
    # son propre instantané et voit une progression figée.
    db.rollback()
    db.expire_all()
    r = service.get_report(db, user.id, report_id)
    return ReportDetail(**service.detail_dict(r, is_admin=user.is_admin))


@router.patch("/{report_id}", response_model=ReportDetail)
def update_one(report_id: str, payload: ReportPatch,
               user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> ReportDetail:
    """Renomme, archive, épingle et/ou déplace. `project_id: null` explicite
    retire du dossier ; `project_id` absent du corps ne touche à rien."""
    r = service.update_report(
        db, user.id, report_id, title=payload.title, archived=payload.archived,
        pinned=payload.pinned, project_id=payload.project_id,
        project_fourni="project_id" in payload.model_fields_set)
    return ReportDetail(**service.detail_dict(r, is_admin=user.is_admin))


@router.post("/{report_id}/annuler", response_model=ReportDetail)
def annuler(report_id: str, user: AuthUser = Depends(get_current_user),
            db: Session = Depends(get_db)) -> ReportDetail:
    """Stop. Pose le drapeau ; la tâche range le rapport en `annule`."""
    r = service.demander_annulation(db, user.id, report_id)
    return ReportDetail(**service.detail_dict(r, is_admin=user.is_admin))


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
    return ReportDetail(**service.detail_dict(nouveau, is_admin=user.is_admin))


# --- Partage public (spec §0, §4) ------------------------------------------

@router.post("/{report_id}/partage", response_model=PartageOut)
def partager(report_id: str, user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> PartageOut:
    """Ouvre le partage. Idempotent : le même rapport rend le même jeton,
    sinon un second clic invaliderait le lien déjà transmis."""
    return PartageOut(**service.activer_partage(
        db, user.id, report_id, full_name=user.full_name, email=str(user.email)))


@router.delete("/{report_id}/partage", status_code=204, response_class=Response)
def revoquer(report_id: str, user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> Response:
    """Révoque le partage : le lien cesse immédiatement de fonctionner."""
    service.revoquer_partage(db, user.id, report_id)
    return Response(status_code=204)


@router_public.get("/{jeton}", response_model=RapportPublic)
def lire_partage(jeton: str, db: Session = Depends(get_db)) -> RapportPublic:
    """Rapport partagé, en lecture seule, SANS authentification.

    Le jeton EST l'autorisation (22 caractères aléatoires). Rien d'autre que ce
    qui se lit ne sort : ni coûts, ni question posée, ni `detail`, ni sources
    internes (documents déposés, pages Notion).
    """
    return RapportPublic(**service.rapport_public(db, jeton))


# --- Signalement (spec §3) -------------------------------------------------

@router.post("/{report_id}/feedback", response_model=FeedbackOut, status_code=201)
def signaler(report_id: str, payload: FeedbackIn,
             user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> FeedbackOut:
    """« Signaler un problème » / « Votre avis » : archive l'avis et envoie
    l'email technique « relire le rapport » (le Google Form disparaît)."""
    s = service.enregistrer_signalement(
        db, user.id, report_id, motif=payload.motif, note=payload.note,
        commentaire=payload.commentaire, user_email=str(user.email))
    return FeedbackOut(id=str(s.id), motif=s.motif, note=s.note,
                       created_at=s.created_at)


# --- Export (spec §4) ------------------------------------------------------

def _fichier(octets: bytes, mime: str, nom: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(octets), media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


@router.get("/{report_id}/export")
def exporter(report_id: str, format: str = Query(default="pdf"),
             user: AuthUser = Depends(get_current_user),
             db: Session = Depends(get_db)) -> StreamingResponse:
    """`format` ∈ pdf | md | docx."""
    octets, mime, nom = service.exporter(db, user.id, report_id, format=format)
    return _fichier(octets, mime, nom)


# Alias conservé : le front en production télécharge le PDF par ce chemin, et
# un lien déjà collé dans un email doit continuer de marcher.
@router.get("/{report_id}/pdf")
def export_pdf(report_id: str, user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> StreamingResponse:
    octets, mime, nom = service.exporter(db, user.id, report_id, format="pdf")
    return _fichier(octets, mime, nom)


@router.delete("/{report_id}", status_code=204, response_class=Response)
def delete_one(report_id: str, user: AuthUser = Depends(get_current_user),
               db: Session = Depends(get_db)) -> Response:
    service.delete_report(db, user.id, report_id)
    return Response(status_code=204)
