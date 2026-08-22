"""Connexions OAuth aux outils du client.

**Notion** passe par son serveur MCP hébergé : une fois le jeton de l'utilisateur
stocké, on le transmet à l'API Claude qui interroge directement l'espace Notion
pendant la rédaction du rapport. C'est ce qui permet d'« enrichir les rapports
avec les outils du client » sans écrire un connecteur par fonctionnalité.

**Google** n'a pas de serveur MCP officiel : on passe par son API directe.
"""
from __future__ import annotations

import base64
import datetime as dt
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.modules.integrations.crypto import chiffrer, dechiffrer
from app.modules.integrations.models import UserConnection

logger = logging.getLogger("axial.integrations")

NOTION_MCP_URL = "https://mcp.notion.com/mcp"
NOTION_AUTORISE = "https://api.notion.com/v1/oauth/authorize"
NOTION_JETON = "https://api.notion.com/v1/oauth/token"
GOOGLE_AUTORISE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_JETON = "https://oauth2.googleapis.com/token"
# `drive.file` ne donne accès qu'aux fichiers créés par Axial — périmètre
# minimal, et surtout pas soumis à la validation Google des portées sensibles.
GOOGLE_SCOPES = "https://www.googleapis.com/auth/drive.file"

BASE_PUBLIQUE = "https://app.axial-ia.fr"


def _redirection(provider: str) -> str:
    return f"{BASE_PUBLIQUE}/api/integrations/{provider}/callback"


def configure(provider: str) -> bool:
    s = get_settings()
    if provider == "notion":
        return bool(s.notion_client_id and s.notion_client_secret
                    and s.integrations_secret_key)
    if provider == "google":
        return bool(s.google_client_id and s.google_client_secret
                    and s.integrations_secret_key)
    return False


def url_autorisation(provider: str, state: str) -> str:
    """URL vers laquelle envoyer l'utilisateur pour qu'il autorise Axial."""
    s = get_settings()
    if not configure(provider):
        raise AppError(f"Intégration {provider} non configurée.", 503,
                       code="integration_unconfigured")
    if provider == "notion":
        return (f"{NOTION_AUTORISE}?client_id={s.notion_client_id}"
                f"&response_type=code&owner=user"
                f"&redirect_uri={_redirection('notion')}&state={state}")
    return (f"{GOOGLE_AUTORISE}?client_id={s.google_client_id}"
            f"&response_type=code&access_type=offline&prompt=consent"
            f"&scope={GOOGLE_SCOPES}"
            f"&redirect_uri={_redirection('google')}&state={state}")


def echanger_code(provider: str, code: str) -> dict:
    """Échanger le code d'autorisation contre un jeton d'accès."""
    s = get_settings()
    if provider == "notion":
        # Notion attend l'authentification client en Basic auth.
        creds = base64.b64encode(
            f"{s.notion_client_id}:{s.notion_client_secret}".encode()).decode()
        r = httpx.post(NOTION_JETON,
                       headers={"Authorization": f"Basic {creds}",
                                "Content-Type": "application/json",
                                "Notion-Version": "2022-06-28"},
                       json={"grant_type": "authorization_code", "code": code,
                             "redirect_uri": _redirection("notion")},
                       timeout=30.0)
    else:
        r = httpx.post(GOOGLE_JETON,
                       data={"code": code, "client_id": s.google_client_id,
                             "client_secret": s.google_client_secret,
                             "redirect_uri": _redirection("google"),
                             "grant_type": "authorization_code"},
                       timeout=30.0)
    if r.status_code >= 300:
        logger.warning("Échange de code %s échoué : %s", provider, r.text[:200])
        raise AppError("L'autorisation a échoué. Réessaie.", 400,
                       code="oauth_exchange_failed")
    return r.json()


def enregistrer(db: Session, user_id: str, provider: str, jeton: dict) -> UserConnection:
    uid = uuid.UUID(user_id)
    conn = db.scalar(select(UserConnection).where(
        UserConnection.user_id == uid, UserConnection.provider == provider))
    if conn is None:
        conn = UserConnection(user_id=uid, provider=provider)
        db.add(conn)

    conn.access_token_enc = chiffrer(jeton.get("access_token", ""))
    if jeton.get("refresh_token"):
        conn.refresh_token_enc = chiffrer(jeton["refresh_token"])
    if jeton.get("expires_in"):
        conn.expires_at = (dt.datetime.now(dt.timezone.utc)
                           + dt.timedelta(seconds=int(jeton["expires_in"])))
    conn.scopes = jeton.get("scope")
    if provider == "notion":
        conn.account = {"workspace": jeton.get("workspace_name"),
                        "icon": jeton.get("workspace_icon"),
                        "bot_id": jeton.get("bot_id")}
    db.commit()
    db.refresh(conn)
    return conn


def get(db: Session, user_id: str, provider: str) -> UserConnection | None:
    return db.scalar(select(UserConnection).where(
        UserConnection.user_id == uuid.UUID(user_id),
        UserConnection.provider == provider))


def jeton_actif(db: Session, user_id: str, provider: str) -> str | None:
    """Jeton d'accès en clair, rafraîchi si nécessaire. None si non connecté."""
    conn = get(db, user_id, provider)
    if conn is None:
        return None
    expire = conn.expires_at
    if expire is not None:
        if expire.tzinfo is None:
            expire = expire.replace(tzinfo=dt.timezone.utc)
        if expire < dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=2):
            if not _rafraichir(db, conn):
                return None
    return dechiffrer(conn.access_token_enc)


def _rafraichir(db: Session, conn: UserConnection) -> bool:
    """Renouveler un jeton expiré (Google uniquement — Notion n'expire pas)."""
    if conn.provider != "google" or not conn.refresh_token_enc:
        return conn.provider == "notion"
    s = get_settings()
    try:
        r = httpx.post(GOOGLE_JETON,
                       data={"refresh_token": dechiffrer(conn.refresh_token_enc),
                             "client_id": s.google_client_id,
                             "client_secret": s.google_client_secret,
                             "grant_type": "refresh_token"},
                       timeout=30.0)
        r.raise_for_status()
        jeton = r.json()
        conn.access_token_enc = chiffrer(jeton["access_token"])
        if jeton.get("expires_in"):
            conn.expires_at = (dt.datetime.now(dt.timezone.utc)
                               + dt.timedelta(seconds=int(jeton["expires_in"])))
        db.commit()
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Rafraîchissement Google échoué : %s", e)
        return False


def deconnecter(db: Session, user_id: str, provider: str) -> None:
    conn = get(db, user_id, provider)
    if conn is not None:
        db.delete(conn)
        db.commit()


def etat(db: Session, user_id: str) -> dict:
    """Ce que l'écran Paramètres affiche pour chaque outil."""
    out = {}
    for provider in ("notion", "google"):
        conn = get(db, user_id, provider)
        out[provider] = {
            "configure": configure(provider),
            "connecte": conn is not None,
            "compte": (conn.account or {}) if conn else None,
            "depuis": conn.created_at.isoformat() if conn else None,
        }
    return out


def mcp_pour_rapport(db: Session, user_id: str) -> tuple[list, list]:
    """Serveurs MCP + outils à joindre à l'appel Claude, selon les connexions.

    Renvoie (mcp_servers, tools) — deux listes vides si rien n'est connecté.
    Les deux moitiés sont obligatoires : déclarer un serveur sans son
    `mcp_toolset` est rejeté par l'API.
    """
    jeton = jeton_actif(db, user_id, "notion")
    if not jeton:
        return [], []
    return (
        [{"type": "url", "url": NOTION_MCP_URL, "name": "notion",
          "authorization_token": jeton}],
        [{"type": "mcp_toolset", "mcp_server_name": "notion"}],
    )
