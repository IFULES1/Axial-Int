"""Notification email des erreurs backend absorbées.

Une erreur inattendue (gestionnaire global) ou une erreur absorbée mais
critique (génération LLM en échec, flux coupé) ne doit pas disparaître dans
les seuls logs serveur : un email technique part vers l'équipe, dédupliqué
par signature (route + type d'exception) pour ne pas noyer la boîte de
réception si la même panne se répète pendant une heure.

Jamais d'exception propagée : un incident de notification ne doit jamais
transformer une erreur déjà gérée en 500 supplémentaire.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import traceback

from app.config import get_settings
from app.modules.emailing.envoi import envoyer_brut

logger = logging.getLogger("axial.notifier")

TRACEBACK_MAX = 4000
DEDUP_FENETRE_SECONDES = 3600

# Signature (sha1 de route+type d'exception) -> horodatage du dernier envoi.
# Dict en mémoire, process-local : suffisant, un seul worker uvicorn en prod
# (même hypothèse que le cache Notion, documentée dans service.py).
_derniers_envois: dict[str, float] = {}


def _reinitialiser() -> None:
    """Vide le dédoublonnage. Réservé aux tests."""
    _derniers_envois.clear()


def _signature(route: str, exc: BaseException) -> str:
    brut = f"{route}:{type(exc).__name__}"
    return hashlib.sha1(brut.encode("utf-8")).hexdigest()


def _deja_notifie_recemment(signature: str) -> bool:
    dernier = _derniers_envois.get(signature)
    if dernier is None:
        return False
    return (dt.datetime.now(dt.timezone.utc).timestamp() - dernier) < DEDUP_FENETRE_SECONDES


def notifier_erreur(*, titre: str, route: str, methode: str,
                     user_email: str | None, exc: BaseException, action: str) -> None:
    """Envoie un email technique d'incident. N'échoue jamais.

    Déduplique par signature (route + type d'exception) sur une heure : une
    même panne qui se répète en boucle n'inonde pas la boîte de réception.
    """
    try:
        settings = get_settings()
        if not settings.erreurs_notif_actives:
            return

        signature = _signature(route, exc)
        if _deja_notifie_recemment(signature):
            return

        horodatage = dt.datetime.now(dt.timezone.utc).isoformat()
        trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if len(trace) > TRACEBACK_MAX:
            trace = trace[:TRACEBACK_MAX] + "\n… (tronqué)"

        sujet = f"[Axial] Erreur backend : {methode} {route}"
        texte = (
            f"{titre}\n\n"
            f"Compte : {user_email or 'inconnu'}\n"
            f"Route : {methode} {route}\n"
            f"Horodatage (UTC) : {horodatage}\n\n"
            f"Action suggérée : {action}\n\n"
            f"Traceback :\n{trace}"
        )

        envoye, motif = envoyer_brut(settings.erreurs_notif_destinataire, sujet, texte)
        if envoye:
            _derniers_envois[signature] = dt.datetime.now(dt.timezone.utc).timestamp()
        else:
            logger.warning("Notification d'erreur non envoyée (%s) : %s", route, motif)
    except Exception as e:  # noqa: BLE001
        # Jamais d'exception hors de cette fonction : c'est déjà le chemin
        # d'erreur, un échec ici ne doit rien casser de plus.
        logger.warning("notifier_erreur a échoué : %s", e)
