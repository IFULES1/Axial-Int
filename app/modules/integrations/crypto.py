"""Chiffrement symétrique des jetons OAuth.

La clé vient de la configuration (`integrations_secret_key`). Sans elle, le
module refuse de stocker un jeton plutôt que de l'écrire en clair : mieux vaut
une intégration indisponible qu'un secret client exposé en base.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.errors import AppError


def _fernet() -> Fernet:
    settings = get_settings()
    secret = settings.integrations_secret_key or ""
    if not secret:
        raise AppError("Intégrations non configurées (clé de chiffrement absente).",
                       503, code="integrations_unconfigured")
    # Dérive une clé Fernet valide depuis n'importe quel secret lisible.
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def chiffrer(valeur: str) -> str:
    return _fernet().encrypt((valeur or "").encode()).decode()


def dechiffrer(valeur: str) -> str:
    try:
        return _fernet().decrypt((valeur or "").encode()).decode()
    except InvalidToken as e:
        raise AppError("Connexion illisible — reconnecte l'outil.", 400,
                       code="connection_corrupt") from e
