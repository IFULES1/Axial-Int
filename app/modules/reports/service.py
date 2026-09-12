"""Report service: persist, list, get, delete, manage, share, export.

Gestion (spec §4) : renommer, archiver, épingler, classer dans un dossier,
rechercher, paginer. Partage public (spec §0/§4) : un jeton non devinable ouvre
une page en lecture seule, sans coût ni source interne. Export (spec §4) :
PDF, Markdown, DOCX depuis le même markdown archivé.
"""
from __future__ import annotations

import datetime as dt
import logging
import secrets
import unicodedata
import uuid

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.reports.models import Report
from app.modules.reports.pdf import render_pdf

logger = logging.getLogger("axial.reports")

# --- Listing ---------------------------------------------------------------
LISTE_LIMITE_DEFAUT = 20
LISTE_LIMITE_MAX = 100

# --- Recherche -------------------------------------------------------------
RECHERCHE_MINIMUM = 3
RECHERCHE_RESULTATS = 20
RECHERCHE_MARGE = 80

# --- Partage ---------------------------------------------------------------
# `secrets.token_urlsafe(16)` = 22 caractères URL-safe, soit 128 bits : l'URL
# n'est pas devinable, et c'est elle qui tient lieu d'autorisation.
JETON_OCTETS = 16
JETON_ESSAIS = 3
SLUG_MAX = 60
PSEUDO_MAX = 40
# Sources à ne JAMAIS publier : ce sont les documents privés de l'utilisateur
# et son espace Notion. Le partage est public — un lien transmis par erreur ne
# doit pas exposer le contenu de son coffre.
# Valeurs réellement produites par `app/shared/grounding.py` : « interne » (base
# de connaissance), « document » (fichier déposé par l'utilisateur), « notion ».
# Tout ce qui n'est pas « web » reste privé : la liste est fermée sur le web.
SOURCES_INTERNES = ("interne", "document", "documents", "notion", "rag", "kb")

# --- Export ----------------------------------------------------------------
FORMATS_EXPORT = ("pdf", "md", "docx")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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


def _iso(valeur):
    """Date en ISO 8601 **avec** le « T » séparateur, ou `None`.

    Les dates de ce dict sortent par deux chemins : Pydantic (routes HTTP, qui
    sérialise correctement) et `json.dumps(default=str)` (événement `done` du
    flux SSE), lequel rendait « 2026-09-12 17:12:36+02:00 » — un format que
    `new Date(...)` refuse dans Safari, donc un chronomètre à « NaN » côté
    front. Un `isoformat()` explicite ici supprime la divergence à la source ;
    Pydantic reparse la chaîne sans broncher.
    """
    return valeur.isoformat() if valeur is not None else None


def resume_dict(report: Report) -> dict:
    """Forme unique du `ReportOut` — ce que la LISTE affiche, sans le contenu.

    Un rapport de 60 000 caractères par ligne de liste, c'était 20 rapports =
    1,2 Mo de JSON pour afficher des titres.
    """
    return {
        "id": str(report.id),
        "title": report.title,
        "analysis_type": report.analysis_type,
        "created_at": _iso(report.created_at),
        "statut": report.statut,
        "etape": report.etape,
        "progression": report.progression,
        "credits": (report.detail or {}).get("credits"),
        "tokens_entree": report.tokens_entree,
        "tokens_sortie": report.tokens_sortie,
        "project_id": str(report.project_id) if report.project_id else None,
        "pinned_at": _iso(report.pinned_at),
        "archived_at": _iso(report.archived_at),
    }


def detail_dict(report: Report, *, is_admin: bool = False) -> dict:
    """Forme unique du `ReportDetail` — l'API et le flux SSE en rendent la même.

    Un seul constructeur : la route `GET /reports/{id}` et l'événement `done`
    du flux décrivaient le même rapport avec deux jeux de clés, et le front
    devait connaître les deux.

    `is_admin` ouvre les deux coûts de revient (spec §4). Défaut `False` : un
    appelant qui oublie le drapeau ne fuite rien.
    """
    d = resume_dict(report)
    d.update({
        "content": report.content or "",
        "sources": report.sources if isinstance(report.sources, list) else None,
        "viz": report.viz if isinstance(report.viz, list) else None,
        "detail": report.detail or {},
        "question": report.question,
        "termine_at": _iso(report.termine_at),
        "annulation_demandee": bool(report.annulation_demandee),
        "jeton_partage": report.jeton_partage,
        "partage_at": _iso(report.partage_at),
    })
    # Le coût exposé à l'utilisateur est ce qu'il a payé — les crédits, pas les
    # euros. Le prix de revient reste réservé à l'administration (spec §4) : un
    # client qui lit « 0,07 € » sur un rapport facturé 25 crédits n'a pas besoin
    # de cette information pour travailler, et elle nous met en négociation.
    if is_admin:
        d["cout_micro_eur"] = report.cout_micro_eur
        d["cout_recherche_micro_eur"] = report.cout_recherche_micro_eur
    return d


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


# --- Liste paginée ---------------------------------------------------------

def _rang():
    """Rang de tri d'un rapport : en cours, puis épinglé, puis le reste.

    Expression SQL et non tri Python : c'est elle qui rend la pagination par
    curseur exacte (`before` doit comparer des rangs, pas seulement des dates).
    """
    from app.modules.reports.models import EN_COURS

    return case((Report.statut == EN_COURS, 0),
                (Report.pinned_at.is_not(None), 1),
                else_=2)


def _rang_de(report: Report) -> int:
    from app.modules.reports.models import EN_COURS

    if report.statut == EN_COURS:
        return 0
    return 1 if report.pinned_at is not None else 2


def list_reports(db: Session, user_id: str, *,
                 limit: int = LISTE_LIMITE_DEFAUT,
                 before: str | None = None,
                 inclure_archives: bool = False) -> tuple[list[Report], bool]:
    """Fenêtre de `limit` rapports + « reste-t-il quelque chose ? ».

    Ordre : les générations en cours d'abord (l'utilisateur doit pouvoir
    rouvrir un rapport lancé ailleurs), puis les épinglés, puis par date
    décroissante. Départage sur `(created_at, id)` : deux rapports créés dans
    la même microseconde — un « Régénérer » enchaîné — rendaient la fenêtre
    instable et pouvaient faire DISPARAÎTRE le jumeau du rapport borne.

    `before` est l'identifiant du dernier rapport déjà affiché : le curseur
    compare le rang ET la date, sinon « Charger plus » sauterait toute la
    section des épinglés.
    """
    limit = max(1, min(int(limit or LISTE_LIMITE_DEFAUT), LISTE_LIMITE_MAX))
    stmt = select(Report).where(Report.user_id == uuid.UUID(user_id))
    if not inclure_archives:
        stmt = stmt.where(Report.archived_at.is_(None))
    if before:
        # Rapport borne introuvable (supprimé entre deux pages) : on repart du
        # début plutôt que de faire échouer tout le « Charger plus » — le
        # curseur d'une page n'a plus de sens une fois sa cible disparue, mais
        # ce n'est pas une erreur pour l'appelant.
        try:
            borne = db.get(Report, uuid.UUID(before))
        except (ValueError, AttributeError, TypeError):
            borne = None
        if borne is not None and str(borne.user_id) != user_id:
            borne = None
        if borne is not None:
            rang_borne = _rang_de(borne)
            stmt = stmt.where(or_(
                _rang() > rang_borne,
                and_(_rang() == rang_borne,
                     or_(Report.created_at < borne.created_at,
                         and_(Report.created_at == borne.created_at,
                              Report.id < borne.id))),
            ))
    # On lit un rapport de plus que demandé : sa présence EST la réponse à
    # « reste-t-il des rapports ? », sans second COUNT(*).
    fenetre = list(db.scalars(
        stmt.order_by(_rang(), Report.created_at.desc(), Report.id.desc())
        .limit(limit + 1)))
    return fenetre[:limit], len(fenetre) > limit


def get_report(db: Session, user_id: str, report_id: str) -> Report:
    report = db.get(Report, _uuid_ou_404(report_id))
    if not report or str(report.user_id) != user_id:
        raise AppError("Rapport introuvable.", 404, code="not_found")
    return report


def _uuid_ou_404(valeur: str) -> uuid.UUID:
    # Un identifiant qui n'est pas un UUID vaut « introuvable », pas une erreur
    # serveur : il arrive de l'URL et un client peut y mettre n'importe quoi.
    try:
        return uuid.UUID(str(valeur))
    except (ValueError, AttributeError, TypeError):
        raise AppError("Rapport introuvable.", 404, code="not_found") from None


def delete_report(db: Session, user_id: str, report_id: str) -> None:
    report = get_report(db, user_id, report_id)
    db.delete(report)
    db.commit()


# --- Renommer / archiver / épingler / classer (spec §4) --------------------

def update_report(db: Session, user_id: str, report_id: str, *,
                  title: str | None = None,
                  archived: bool | None = None,
                  pinned: bool | None = None,
                  project_id: str | None = None,
                  project_fourni: bool = False) -> Report:
    """Renomme, (dés)archive, (dés)épingle et/ou déplace un rapport.

    Un seul point d'entrée pour les quatre : ce sont quatre attributs de la
    même ligne et le menu ⋯ les enchaîne. Sémantique PATCH — un champ absent du
    corps ne bouge pas, donc `archived: false` désarchive et `archived` absent
    ne dit rien.

    `project_fourni` distingue « clé absente » de « clé à null » : sans lui,
    « Retirer du dossier » serait impossible à exprimer.
    """
    report = get_report(db, user_id, report_id)
    if title is not None:
        propre = " ".join(title.split())
        if not propre:
            raise AppError("Le titre ne peut pas être vide.", 400, code="titre_vide")
        report.title = propre[:300]
    if pinned is not None:
        report.pinned_at = _now() if pinned else None
    if archived is not None:
        report.archived_at = _now() if archived else None
        # Un rapport archivé n'a plus à occuper la tête de liste.
        if archived:
            report.pinned_at = None
    if project_fourni:
        if project_id is None:
            report.project_id = None
        else:
            # Le dossier de destination doit appartenir au MÊME utilisateur :
            # sinon un identifiant deviné déplacerait un rapport chez
            # quelqu'un d'autre. `_own_project` rend 404 et non 403 — on ne
            # confirme pas l'existence d'un dossier qui n'est pas le sien.
            from app.modules.intelligence.service import _own_project

            report.project_id = _own_project(db, user_id, project_id).id
    db.commit()
    db.refresh(report)
    return report


# --- Recherche (spec §4) ---------------------------------------------------

def _motif_like(terme: str) -> str:
    """Terme échappé pour un `LIKE` : sans échappement, chercher « 100 % » ou
    « chiffre_affaires » rendrait n'importe quoi (`%` et `_` sont les jokers)."""
    echappe = terme.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{echappe.lower()}%"


def _extrait(texte: str, terme: str, marge: int = RECHERCHE_MARGE) -> str:
    """Fenêtre de ±`marge` caractères autour de la PREMIÈRE occurrence.

    Calculé en Python et non en SQL : `position()` n'existe pas en SQLite,
    `strpos` n'est pas insensible à la casse, et les « … » de troncature sont
    de toute façon un choix d'affichage.
    """
    texte = texte or ""
    i = texte.lower().find(terme.lower())
    if i < 0:
        # Trouvé par le titre : on rend le début du contenu, meilleur aperçu
        # disponible.
        debut, fin = 0, min(len(texte), 2 * marge)
    else:
        debut = max(0, i - marge)
        fin = min(len(texte), i + len(terme) + marge)
    fragment = " ".join(texte[debut:fin].split())
    return ("…" if debut > 0 else "") + fragment + ("…" if fin < len(texte) else "")


def rechercher(db: Session, user_id: str, q: str, *,
               limit: int = RECHERCHE_RESULTATS) -> list[dict]:
    """Cherche `q` dans le titre ET le contenu des rapports non archivés.

    `func.lower(...).like(...)` plutôt qu'`ILIKE` : `ILIKE` est propre à
    PostgreSQL et la suite de tests tourne sur SQLite. Aucun index de texte —
    le volume est celui d'un utilisateur, pas d'un corpus.
    """
    terme = (q or "").strip()
    if len(terme) < RECHERCHE_MINIMUM:
        raise AppError(f"Saisissez au moins {RECHERCHE_MINIMUM} caractères.",
                       400, code="requete_trop_courte")
    limit = max(1, min(int(limit or RECHERCHE_RESULTATS), RECHERCHE_RESULTATS))
    motif = _motif_like(terme)
    lignes = db.scalars(
        select(Report)
        .where(Report.user_id == uuid.UUID(user_id),
               Report.archived_at.is_(None),
               or_(func.lower(Report.title).like(motif, escape="\\"),
                   func.lower(Report.content).like(motif, escape="\\")))
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(limit)
    )
    return [{
        "id": str(r.id),
        "title": r.title,
        "analysis_type": r.analysis_type,
        "created_at": r.created_at,
        "statut": r.statut,
        # Le titre d'abord : quand le terme est dans le titre, l'extrait du
        # contenu ne dit rien de plus que le titre déjà affiché.
        "extrait": _extrait(r.content or "", terme),
    } for r in lignes]


# --- Partage public (spec §0, §4) ------------------------------------------

def _ascii(texte: str) -> str:
    """Translittération sans accent : le pseudo et le slug voyagent dans une
    URL, et « Miradie Buranturu » ne doit pas devenir « %C3%A9 »."""
    decompose = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in decompose if not unicodedata.combining(c))


def normaliser(texte: str, longueur: int) -> str:
    """`texte` → segment d'URL : ascii, minuscules, tirets, tronqué."""
    propre = _ascii(texte).lower()
    propre = "".join(c if c.isalnum() else "-" for c in propre)
    propre = "-".join(p for p in propre.split("-") if p)
    return propre[:longueur].strip("-")


def pseudo_de(full_name: str | None, email: str | None) -> str:
    """Pseudo public : le nom déclaré, à défaut la partie locale de l'email.

    Le nom vient des métadonnées Supabase portées par le jeton ; il n'est ni
    unique ni vérifié — c'est un ornement d'URL, le jeton seul autorise.
    """
    pseudo = normaliser(full_name or "", PSEUDO_MAX)
    if not pseudo:
        pseudo = normaliser((email or "").split("@")[0], PSEUDO_MAX)
    return pseudo or "axial"


def url_partage(pseudo: str, slug: str, jeton: str) -> str:
    """Chemin relatif `/p/<pseudo>/<slug>-<jeton>`.

    Relatif et non absolu : l'URL publique du front n'est pas une donnée du
    backend (localhost en développement, app.axial-ia.fr en production), et le
    front sait la préfixer.
    """
    return f"/p/{pseudo}/{slug}-{jeton}" if slug else f"/p/{pseudo}/{jeton}"


def activer_partage(db: Session, user_id: str, report_id: str, *,
                    full_name: str | None = None,
                    email: str | None = None) -> dict:
    """Ouvre (ou rouvre) le partage public. Idempotent : le même rapport rend
    le même jeton, sinon un second clic invaliderait le lien déjà transmis.

    Le pseudo et le slug sont figés dans `detail["partage"]` au moment du
    partage : la page publique n'a pas d'utilisateur connecté et ne peut donc
    pas recalculer le pseudo depuis un jeton d'authentification.
    """
    from app.modules.reports import models as rm

    report = get_report(db, user_id, report_id)
    if report.statut == rm.EN_COURS or not (report.content or "").strip():
        raise AppError("Ce rapport n'a pas encore de contenu à partager.", 409,
                       code="rapport_non_partageable")

    pseudo = pseudo_de(full_name, email)
    slug = normaliser(report.title or "", SLUG_MAX)
    if not report.jeton_partage:
        _jeton_unique(db, report)
    # Réassignation complète : `detail` est une colonne JSON, une mutation en
    # place n'est pas détectée par SQLAlchemy et ne serait jamais écrite.
    report.detail = {**(report.detail or {}),
                     "partage": {"pseudo": pseudo, "slug": slug}}
    db.commit()
    db.refresh(report)
    return {"jeton": report.jeton_partage,
            "url": url_partage(pseudo, slug, report.jeton_partage)}


def _jeton_unique(db: Session, report: Report) -> str:
    """Assigne un jeton libre à `report` et committe l'assignation.

    Un `SELECT` de pré-vérification ne tranche rien sous concurrence : entre
    la lecture et l'écriture, une autre requête peut choisir le même jeton, et
    seul le `COMMIT` sur l'index unique `ux_reports_jeton_partage` le
    détecterait — en 500, pas en erreur applicative. Motif aligné sur
    `credit_events` (spec §5.4) : `try/except IntegrityError` + `rollback` +
    nouvel essai avec un jeton neuf.
    """
    for _ in range(JETON_ESSAIS):
        report.jeton_partage = secrets.token_urlsafe(JETON_OCTETS)
        report.partage_at = _now()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        return report.jeton_partage
    raise AppError("Partage impossible pour le moment.", 503,
                   code="jeton_indisponible")


def revoquer_partage(db: Session, user_id: str, report_id: str) -> None:
    """Ferme le partage. Idempotent : révoquer un rapport non partagé est un
    succès (le lien ne marche pas, c'est ce qui était demandé)."""
    report = get_report(db, user_id, report_id)
    report.jeton_partage = None
    report.partage_at = None
    detail = dict(report.detail or {})
    detail.pop("partage", None)
    report.detail = detail
    db.commit()


_JALON_SOURCE_INTERNE = {"title": "Source interne, non partagée", "url": None,
                        "source": "interne", "domain": None, "excerpt": None}


def _sources_publiables(sources: list | None) -> list | None:
    """Remplace les sources internes par un jalon inerte, À LA MÊME PLACE.

    Un lien public transmis par erreur ne doit rien dire du coffre de
    l'utilisateur — ni le titre d'un document, ni le nom d'une page Notion.
    Mais RETIRER ces entrées décalerait l'index des sources qui suivent : le
    texte du rapport cite `[N]` par position (`grounding.assemble`), et
    `viz[].spec.sources` porte les mêmes index (`app/modules/viz/schema.py`,
    consommés par `pdf.py`). Un jalon à la même place garde les deux valides.
    """
    if not isinstance(sources, list):
        return None
    return [dict(_JALON_SOURCE_INTERNE)
            if isinstance(s, dict) and (s.get("source") or "web") != "web"
            else s
            for s in sources]


def rapport_public(db: Session, jeton: str) -> dict:
    """Vue publique d'un rapport partagé — rien d'autre que ce qui se lit.

    Liste blanche et non liste noire : `detail` (raison d'un dégradé, sources
    internes en aperçu, contenu partiel d'une annulation), la question posée,
    les coûts, l'identifiant du propriétaire et celui du rapport ne sortent
    pas. Ajouter une colonne au modèle n'ouvre donc rien ici par accident.
    """
    propre = (jeton or "").strip()
    # Borne de longueur avant la requête : la colonne fait 32 caractères, un
    # jeton de 10 000 caractères n'a rien à faire dans un `WHERE`.
    if not propre or len(propre) > 32:
        raise AppError("Ce lien de partage n'est plus valide.", 404, code="not_found")
    report = db.scalars(
        select(Report).where(Report.jeton_partage == propre)).first()
    if not report:
        raise AppError("Ce lien de partage n'est plus valide.", 404, code="not_found")
    partage = (report.detail or {}).get("partage") or {}
    return {
        "title": report.title,
        "content": report.content or "",
        "sources": _sources_publiables(report.sources),
        "viz": report.viz if isinstance(report.viz, list) else None,
        "analysis_type": report.analysis_type,
        "created_at": report.created_at,
        "pseudo": partage.get("pseudo") or "axial",
    }


def empreintes_partagees(db: Session, jeton: str) -> set[str]:
    """Empreintes des graphiques du rapport désigné par ce jeton.

    C'est l'autorisation des images de la page publique : le jeton n'ouvre pas
    « toutes les images », il ouvre celles de SON rapport.
    """
    propre = (jeton or "").strip()
    if not propre or len(propre) > 32:
        return set()
    # `Report.viz` seul, pas la ligne entière : cette requête est faite par
    # image d'une page publique et `content` seul peut peser 60 000
    # caractères — inutile de le charger pour ne lire que `viz`.
    viz = db.scalar(select(Report.viz).where(Report.jeton_partage == propre))
    if not isinstance(viz, list):
        return set()
    return {v.get("empreinte") for v in viz
            if isinstance(v, dict) and v.get("empreinte")}


# --- Signalement (spec §3) -------------------------------------------------

class SignalementRapport(Exception):
    """Porteur du signalement dans l'email technique.

    `notifier_erreur` attend une exception : elle formate son traceback. Le
    message porte donc tout ce qui rend le retour actionnable — l'identifiant
    du rapport, son titre, le motif et le commentaire — plutôt qu'une pile
    d'appels qui ne dit rien d'un avis utilisateur.
    """


def enregistrer_signalement(db: Session, user_id: str, report_id: str, *,
                            motif: str, note: int | None = None,
                            commentaire: str | None = None,
                            user_email: str | None = None):
    """Archive le signalement et prévient l'équipe. L'email ne bloque rien."""
    from app.modules.reports.feedback import MOTIFS, ReportFeedback

    report = get_report(db, user_id, report_id)
    # « faux » est le libellé du formulaire, `contenu_faux` celui de la base :
    # on accepte les deux plutôt que d'imposer au front une table de
    # correspondance pour un seul motif.
    propre = {"faux": "contenu_faux"}.get(motif, motif)
    if propre not in MOTIFS:
        raise AppError("Motif de signalement inconnu.", 400, code="motif_inconnu")
    if note is not None and not (1 <= int(note) <= 5):
        raise AppError("La note doit être comprise entre 1 et 5.", 400,
                       code="note_invalide")
    signalement = ReportFeedback(
        id=uuid.uuid4(), report_id=report.id, user_id=uuid.UUID(user_id),
        note=int(note) if note is not None else None, motif=propre,
        commentaire=(commentaire or "").strip()[:4000] or None)
    db.add(signalement)
    db.commit()
    db.refresh(signalement)
    _notifier_signalement(report, signalement, user_email)
    return signalement


def _notifier_signalement(report: Report, signalement, user_email: str | None) -> None:
    """Email technique « relire le rapport ». Ne lève jamais."""
    try:
        from app.shared.notifier import notifier_erreur

        detail = (
            f"Rapport : {report.id}\n"
            f"Titre : {report.title}\n"
            f"Type : {report.analysis_type} — statut {report.statut}\n"
            f"Compte : {user_email or 'inconnu'}\n"
            f"Motif : {signalement.motif}\n"
            f"Note : {signalement.note if signalement.note is not None else '—'}\n"
            f"Commentaire : {signalement.commentaire or '—'}"
        )
        notifier_erreur(
            titre="Signalement sur un rapport",
            # La signature de dédoublonnage de `notifier_erreur` est
            # (route + type d'exception) sur une heure : sans l'identifiant du
            # signalement dans la route, deux signalements de la même heure
            # n'enverraient qu'un seul email.
            route=f"/reports/{report.id}/feedback#{signalement.id}",
            methode="POST", user_email=user_email,
            exc=SignalementRapport(detail),
            action=f"Relire le rapport {report.id} « {report.title} ».",
        )
    except Exception as e:  # noqa: BLE001 — un email raté n'annule pas un avis
        logger.warning("Notification de signalement échouée : %s", e)


# --- Balayage des orphelins au démarrage (spec §1) -------------------------

def balayer_orphelins(db: Session, *, delai_secondes: int | None = None) -> int:
    """Range en `echec` les rapports laissés `en_cours` par un redémarrage.

    La génération tourne dans un thread démon : elle meurt avec le processus,
    sans repasser par `_executer_rapport`, donc sans ranger sa ligne. L'échéance
    globale du moteur couvre la tâche VIVANTE ; personne ne couvrait la tâche
    morte. Un rapport figé à « 62 % » pour toujours est le pire des états : le
    front y poll indéfiniment et l'utilisateur ne peut ni le relancer ni
    comprendre.

    Le seuil est l'échéance du moteur : en dessous, on rangerait une génération
    encore en train d'écrire (un second worker, une autre machine).
    """
    from app.config import DELAI_MAX_RAPPORT_SECONDES
    from app.modules.reports import models as rm

    delai = DELAI_MAX_RAPPORT_SECONDES if delai_secondes is None else delai_secondes
    limite = _now() - dt.timedelta(seconds=delai)
    orphelins = list(db.scalars(
        select(Report).where(Report.statut == rm.EN_COURS,
                             Report.created_at < limite)))
    for report in orphelins:
        report.statut = rm.ECHEC
        report.progression = 100
        report.termine_at = _now()
        report.detail = {
            **(report.detail or {}),
            "raison": "interrompu_par_redemarrage",
            "message": ("La génération a été interrompue par un redémarrage du "
                        "service. Vous pouvez la relancer ; rien n'a été débité."),
        }
    if orphelins:
        db.commit()
        logger.warning("Balayage au démarrage : %d rapport(s) interrompu(s) "
                       "rangé(s) en échec.", len(orphelins))
    return len(orphelins)


# --- Export (spec §4) ------------------------------------------------------

def export_pdf(db: Session, user_id: str, report_id: str) -> bytes:
    report = get_report(db, user_id, report_id)
    # `sources` est un JSON : liste de citations, ou parfois un scalaire sur
    # d'anciens rapports restaurés — dans ce cas, pas de section Sources.
    sources = report.sources if isinstance(report.sources, list) else None
    vizs = report.viz if isinstance(report.viz, list) else None
    return render_pdf(report.title, report.content, sources=sources, vizs=vizs)


def exporter(db: Session, user_id: str, report_id: str, *,
             format: str = "pdf") -> tuple[bytes, str, str]:
    """`(octets, type MIME, nom de fichier)` pour le format demandé."""
    from app.modules.reports import export as exp

    fmt = (format or "pdf").strip().lower()
    if fmt not in FORMATS_EXPORT:
        raise AppError("Format d'export inconnu (pdf, md ou docx).", 400,
                       code="format_inconnu")
    report = get_report(db, user_id, report_id)
    base = normaliser(report.title or "rapport", SLUG_MAX) or f"rapport-{report.id}"
    if fmt == "pdf":
        return (export_pdf(db, user_id, report_id), "application/pdf",
                f"{base}.pdf")
    if fmt == "md":
        return (exp.vers_markdown(report).encode("utf-8"),
                "text/markdown; charset=utf-8", f"{base}.md")
    return (exp.vers_docx(report),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            f"{base}.docx")
