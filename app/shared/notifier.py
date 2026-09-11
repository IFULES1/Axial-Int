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
import os
import re
import threading
import traceback

from app.config import get_settings
from app.modules.emailing.envoi import envoyer_brut

logger = logging.getLogger("axial.notifier")

TRACEBACK_MAX = 4000
DEDUP_FENETRE_SECONDES = 3600

MASQUE = "<masqué>"

# Un traceback part par email : il traverse Resend et finit dans une boîte
# Gmail. `httpx` met l'URL complète dans son message d'erreur — clé d'API
# comprise quand elle voyage en paramètre de requête (Gemini) — et une
# bibliothèque tierce peut aussi journaliser un en-tête d'autorisation. Le
# masquage existait pour les logs (`llm_client._sans_secret`) mais pas ici,
# alors que c'est le même échec qui déclenche les deux.
_MOTIFS_SECRETS = (
    # key=…, api_key: …, token=…, secret=… (URL, dict Python, en-tête)
    re.compile(r"((?<![A-Za-z])(?:api[-_]?key|apikey|key|token|secret|password|passwd)"
               r"['\"]?\s*[=:]\s*['\"]?)[^\s,;&'\"})\]]+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(Authorization['\"]?\s*[=:]\s*['\"]?)\S+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}"),
)

# Longueur minimale d'une valeur d'environnement pour être masquée : un
# `*_TOKEN=1` ou `*_KEY=true` (drapeaux mal nommés) masquerait tous les « 1 »
# du traceback.
_LONGUEUR_MIN_SECRET = 8
_SUFFIXES_SECRETS = ("_KEY", "_SECRET", "_TOKEN")


def _valeurs_d_environnement() -> list[str]:
    """Valeurs des variables d'environnement dont le NOM annonce un secret.

    Le plus long d'abord : une clé qui est le préfixe d'une autre ne doit pas
    en laisser la queue en clair.
    """
    valeurs = {
        valeur for nom, valeur in os.environ.items()
        if valeur and len(valeur) >= _LONGUEUR_MIN_SECRET
        and (nom.upper().endswith(_SUFFIXES_SECRETS)
             # URL avec identifiants (DATABASE_URL, QDRANT_URL…) : le mot de
             # passe est dans la valeur, pas dans le nom.
             or ("://" in valeur and "@" in valeur))
    }
    return sorted(valeurs, key=len, reverse=True)


def _sans_secrets(texte: str) -> str:
    """Retire de `texte` tout ce qui ressemble à un secret. Ne lève jamais."""
    try:
        # Import local : `llm_client` instancie ses fournisseurs au chargement,
        # et ce module-ci est importé par le gestionnaire d'erreurs global.
        from app.shared.llm_client import _sans_secret

        propre = _sans_secret(texte)
        for valeur in _valeurs_d_environnement():
            propre = propre.replace(valeur, MASQUE)
        for motif in _MOTIFS_SECRETS:
            propre = motif.sub(
                lambda m: (m.group(1) + MASQUE) if m.groups() else MASQUE, propre)
        return propre
    except Exception as e:  # noqa: BLE001 — un masquage en échec ne doit pas
        # transformer un incident en second incident ; mais rien ne part en
        # clair pour autant.
        logger.warning("Masquage des secrets en échec : %s", e)
        return MASQUE

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


# Les tests forcent l'envoi synchrone pour observer l'appel ; en production
# l'email part dans un fil démon.
ENVOI_SYNCHRONE = False


def _lancer(cible) -> None:
    if ENVOI_SYNCHRONE:
        cible()
        return
    threading.Thread(target=cible, name="axial-notifier", daemon=True).start()


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
        # Masquer AVANT de tronquer : la limite porte sur ce qui part vraiment.
        trace = _sans_secrets("".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)))
        suffixe = "\n… (tronqué)"
        if len(trace) > TRACEBACK_MAX:
            trace = trace[:TRACEBACK_MAX - len(suffixe)] + suffixe

        sujet = _sans_secrets(f"[Axial] Erreur backend : {methode} {route}")
        texte = _sans_secrets(
            f"{titre}\n\n"
            f"Compte : {user_email or 'inconnu'}\n"
            f"Route : {methode} {route}\n"
            f"Horodatage (UTC) : {horodatage}\n\n"
            f"Action suggérée : {action}\n\n"
            f"Traceback :\n{trace}"
        )

        # La signature est marquée AVANT l'envoi : deux 500 simultanés ne
        # partent pas en double, et l'appel réseau (jusqu'à 30 s) quitte le
        # chemin de la requête — le client reçoit son 500 sans attendre.
        _derniers_envois[signature] = dt.datetime.now(dt.timezone.utc).timestamp()
        destinataire = settings.erreurs_notif_destinataire

        def _envoyer() -> None:
            try:
                envoye, motif = envoyer_brut(destinataire, sujet, texte)
                if not envoye:
                    _derniers_envois.pop(signature, None)
                    logger.warning("Notification d'erreur non envoyée (%s) : %s", route, motif)
            except Exception as e:  # noqa: BLE001
                _derniers_envois.pop(signature, None)
                logger.warning("Notification d'erreur : envoi échoué (%s)", e)

        _lancer(_envoyer)
    except Exception as e:  # noqa: BLE001
        # Jamais d'exception hors de cette fonction : c'est déjà le chemin
        # d'erreur, un échec ici ne doit rien casser de plus.
        logger.warning("notifier_erreur a échoué : %s", e)
