"""Prévenir l'utilisateur quand son rapport est prêt.

Une étude de fond demande plusieurs minutes. Sans notification, l'utilisateur
soit attend devant un écran de progression, soit part — et ne revient pas.
C'est la principale raison pour laquelle un rapport terminé peut n'être jamais
lu.

L'envoi ne bloque jamais la génération : un email raté ne doit pas transformer
un rapport réussi en échec.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("axial.reports.notification")

OBJET = {
    "fr": "Ton rapport Axial est prêt",
    "en": "Your Axial report is ready",
}

CORPS = {
    "fr": """Hello,

Ton rapport « {titre} » est terminé.

{volume} mots, {sources} sources citées.

Tu le retrouves dans l'onglet Rapports : app.axial-ia.fr

Si quelque chose cloche — un chiffre qui te paraît faux, une source qui manque — dis-le-moi en répondant à ce message. C'est comme ça que l'app s'améliore.

Miradie""",
    "en": """Hello,

Your report "{titre}" is ready.

{volume} words, {sources} cited sources.

You will find it in the Reports tab: app.axial-ia.fr

If something looks off — a figure that seems wrong, a missing source — tell me by replying to this message. That is how the app gets better.

Miradie""",
}


def prevenir(db, user_id: str, *, titre: str, contenu: str,
             sources: list | None) -> bool:
    """Envoie la notification. Retourne False sans jamais lever."""
    try:
        from sqlalchemy import text

        from app.modules.emailing.envoi import envoyer, supprime

        ligne = db.execute(
            text("SELECT email FROM auth.users WHERE id = :u"), {"u": user_id}
        ).scalar()
        if not ligne:
            return False
        email = ligne.lower().strip()
        if supprime(db, email):
            return False

        langue = (db.execute(
            text("SELECT language FROM company_profiles WHERE user_id = :u"),
            {"u": user_id}).scalar() or "fr")
        langue = "en" if langue.lower().startswith("en") else "fr"

        # Une campagne par rapport : sans cela, l'unicité par (email, campagne)
        # empêcherait la deuxième notification du même utilisateur.
        campagne = f"rapport_pret_{str(user_id)[:8]}_{abs(hash(titre)) % 10**8}"
        texte = CORPS[langue].format(
            titre=titre, volume=f"{len((contenu or '').split()):,}".replace(",", " "),
            sources=len(sources or []))
        ok, info = envoyer(db, email, campagne[:64], OBJET[langue], texte,
                           langue=langue, simulation=False)
        if not ok:
            logger.info("Notification de rapport non envoyée à %s : %s", email, info)
        return ok
    except Exception as e:  # noqa: BLE001 — un email raté n'invalide pas un rapport
        logger.warning("Notification de rapport échouée : %s", e)
        return False
