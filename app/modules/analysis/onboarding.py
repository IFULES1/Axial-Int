"""Premier rapport offert à l'inscription.

Trois personnes ont rempli leur profil sans jamais poser de question. L'écran
final de l'onboarding proposait une question et attendait un clic : personne ne
cliquait. On renverse — Axial produit le premier rapport lui-même, gratuitement,
pour que la première expérience soit de LIRE un document sur sa propre
entreprise plutôt que de DÉCIDER quoi demander.

Deux protections, toutes deux côté serveur :
  * la question est construite depuis le profil enregistré, jamais fournie par
    le client — sinon l'endpoint offrirait un rapport arbitraire à qui le
    demande ;
  * l'offre est marquée dans `credit_events` (delta 0) et vérifiée avant
    exécution, donc elle ne peut être servie qu'une fois par compte. Depuis la
    migration 0023, l'unicité est garantie EN BASE par un index unique partiel
    sur `(user_id) WHERE action = 'premier_rapport_offert'` : la vérification
    applicative seule laissait passer deux appels concurrents.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("axial.analysis.onboarding")

ACTION = "premier_rapport_offert"
TYPE_RAPPORT = "etude_marche"


def question_pour(profil: dict) -> str:
    """Question construite depuis le profil, dans la langue de l'utilisateur."""
    en = (profil.get("language") or "fr").lower().startswith("en")
    societe = (profil.get("company_name") or "").strip()
    secteur = (profil.get("sector") or "").strip()
    zone = (profil.get("target_market") or "").strip()
    stade = (profil.get("funding_stage") or "").strip()

    qui = societe or (f"a {secteur} startup" if en else f"une startup {secteur}").strip()
    ou = zone or ("Europe" if en else "France")
    if en:
        q = (f"Market study for {qui}"
             + (f", a {secteur} company" if secteur and societe else "")
             + f", targeting {ou}"
             + (f" at {stade} stage" if stade else "")
             + ". Size the market, name the segments, identify the direct "
               "competitors and the growth dynamics.")
    else:
        q = (f"Étude de marché pour {qui}"
             + (f", entreprise {secteur}" if secteur and societe else "")
             + f", sur le marché {ou}"
             + (f" au stade {stade}" if stade else "")
             + ". Dimensionne le marché, nomme les segments, identifie les "
               "concurrents directs et les dynamiques de croissance.")
    return q


def deja_offert(db, user_id: str) -> bool:
    return bool(db.execute(
        text("SELECT 1 FROM credit_events WHERE user_id = :u AND action = :a LIMIT 1"),
        {"u": user_id, "a": ACTION}).first())


def profil_utilisable(db, user_id: str) -> dict | None:
    """Le profil doit porter de quoi poser une vraie question."""
    r = db.execute(text("""
        SELECT company_name, sector, funding_stage, target_market, language
        FROM company_profiles WHERE user_id = :u
    """), {"u": user_id}).mappings().first()
    if not r:
        return None
    p = dict(r)
    return p if (p.get("company_name") or p.get("sector")) else None


def offrir(db, user_id: str) -> str | None:
    """Génère, archive et notifie. Retourne l'identifiant du rapport ou None."""
    from app.modules.analysis import service
    from app.modules.billing import service as billing
    from app.modules.reports import models as rm
    from app.modules.reports import notification

    if deja_offert(db, user_id):
        return None
    profil = profil_utilisable(db, user_id)
    if not profil:
        logger.info("Premier rapport : profil trop vide pour %s", user_id)
        return None

    # Marquer AVANT de générer : deux appels simultanés ne doivent pas produire
    # deux rapports offerts. Un échec laisse la trace, ce qui est le bon
    # compromis — mieux vaut ne pas offrir deux fois que d'offrir deux fois.
    #
    # `deja_offert` ci-dessus ne suffit pas : deux appels concurrents (deux
    # onglets, un rejeu du front, l'API et le rattrapage du worker en même
    # temps) lisent tous deux « pas encore offert » avant que l'un n'écrive.
    # L'index unique partiel `ux_credit_events_premier_rapport_offert`
    # (migration 0023) tranche en base ; le perdant repart d'ici sans rien
    # générer. C'est la seule garantie qui survit à deux workers.
    try:
        billing._log_event(db, user_id, 0, ACTION)
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("Premier rapport déjà offert à %s (course perdue)", user_id)
        return None

    question = question_pour(profil)
    logger.info("Premier rapport offert à %s : %s", user_id, question[:90])
    # Le MÊME moteur suivi que les rapports payants (spec §1) : le rapport
    # offert apparaît dans la liste avec sa progression, il est arrêtable, et
    # il n'existe qu'une implémentation du pipeline à maintenir.
    #
    # `is_admin=True` : archivé sans débiter le compte. C'est le sens de
    # « offert » — l'utilisateur garde ses 40 crédits pour la suite. Le
    # marqueur `credit_events` posé plus haut reste la garantie d'unicité ;
    # `is_admin` ne touche qu'au débit.
    #
    # `attendre=True` : `offrir` est déjà appelé depuis un thread (route
    # `/analysis/premier-rapport`) ou depuis le worker de rattrapage — en
    # relancer un second ne ferait qu'ajouter une session sans rien gagner.
    rapport = service.lancer_rapport(
        db, user_id, query=question, analysis_type=TYPE_RAPPORT, title=None,
        is_admin=True, attendre=True,
    )
    if rapport is None or rapport.statut != rm.TERMINE:
        logger.warning("Premier rapport non abouti pour %s (%s)", user_id,
                       getattr(rapport, "statut", "introuvable"))
        return None

    notification.prevenir(db, user_id, titre=rapport.title,
                          contenu=rapport.content, sources=rapport.sources)
    return str(rapport.id)


def rattraper(db, limite: int = 5) -> int:
    """Comptes éligibles restés sans premier rapport — filet du worker.

    Le rapport se génère dans un thread de l'API : un redémarrage au mauvais
    moment le perdrait. Cette reprise le rattrape sans file d'attente ni table
    supplémentaire.
    """
    lignes = db.execute(text("""
        SELECT u.id
        FROM auth.users u
        JOIN company_profiles cp ON cp.user_id = u.id
        WHERE u.created_at > now() - interval '7 days'
          AND (cp.company_name IS NOT NULL OR cp.sector IS NOT NULL)
          AND NOT EXISTS (SELECT 1 FROM credit_events e
                          WHERE e.user_id = u.id AND e.action = :a)
          -- Les rapports RESTAURÉS de l'ancienne plateforme ne comptent pas :
          -- ils ont été copiés à l'inscription, leur propriétaire n'a jamais vu
          -- Axial produire quoi que ce soit. Les compter excluait de l'offre
          -- exactement les personnes qu'elle vise — Soumeya (22 restaurés,
          -- 0 produit) et Gorjux (5 restaurés, 0 produit) le 26/08.
          AND NOT EXISTS (
                SELECT 1 FROM reports r
                WHERE r.user_id = u.id
                  AND NOT EXISTS (SELECT 1 FROM legacy_reports l
                                  WHERE l.imported_for = u.id
                                    AND l.title = left(r.title, 500)))
        LIMIT :n
    """), {"a": ACTION, "n": limite}).scalars().all()
    faits = 0
    for uid in lignes:
        try:
            if offrir(db, str(uid)):
                faits += 1
        except Exception as e:  # noqa: BLE001 — un compte en échec n'arrête pas les autres
            logger.warning("Premier rapport impossible pour %s : %s", uid, e)
            db.rollback()
    return faits
