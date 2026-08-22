"""Livrer un rapport dans les outils du client : page Notion, fichier Drive.

L'envoi est **déterministe** (appel direct aux API) plutôt que confié au modèle :
publier un document est une action, pas une rédaction — elle doit réussir ou
échouer franchement, pas dépendre d'un choix d'outil.
"""
from __future__ import annotations

import io
import logging
import re

import httpx

from app.errors import AppError

logger = logging.getLogger("axial.integrations.delivery")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
LIMITE_BLOC = 1900  # Notion refuse un bloc de texte au-delà de 2000 caractères


def _blocs_notion(markdown: str) -> list[dict]:
    """Convertir le markdown du rapport en blocs Notion.

    Couvre ce que nos rapports produisent réellement : titres, listes,
    paragraphes. Le gras inline est conservé.
    """
    def texte(contenu: str) -> list[dict]:
        morceaux: list[dict] = []
        for part in re.split(r"(\*\*[^*]+\*\*)", contenu):
            if not part:
                continue
            gras = part.startswith("**") and part.endswith("**")
            brut = part[2:-2] if gras else part
            for i in range(0, len(brut), LIMITE_BLOC):
                morceaux.append({
                    "type": "text",
                    "text": {"content": brut[i:i + LIMITE_BLOC]},
                    "annotations": {"bold": gras},
                })
        return morceaux or [{"type": "text", "text": {"content": ""}}]

    blocs: list[dict] = []
    for ligne in (markdown or "").split("\n"):
        nue = ligne.strip()
        if not nue:
            continue
        if nue.startswith("### "):
            genre, contenu = "heading_3", nue[4:]
        elif nue.startswith("## "):
            genre, contenu = "heading_2", nue[3:]
        elif nue.startswith("# "):
            genre, contenu = "heading_1", nue[2:]
        elif re.match(r"^[-*]\s+", nue):
            genre, contenu = "bulleted_list_item", re.sub(r"^[-*]\s+", "", nue)
        else:
            genre, contenu = "paragraph", nue
        blocs.append({"object": "block", "type": genre,
                      genre: {"rich_text": texte(contenu)}})
    # Notion plafonne à 100 blocs par requête de création.
    return blocs[:100]


def vers_notion(jeton: str, titre: str, contenu: str) -> str:
    """Créer une page Notion et renvoyer son URL."""
    entetes = {"Authorization": f"Bearer {jeton}", "Notion-Version": NOTION_VERSION,
               "Content-Type": "application/json"}
    # La page est créée là où l'utilisateur a autorisé Axial : on prend la
    # première destination accessible plutôt que d'en imposer une.
    r = httpx.post(f"{NOTION_API}/search", headers=entetes,
                   json={"filter": {"property": "object", "value": "page"},
                         "page_size": 1}, timeout=30.0)
    if r.status_code >= 300:
        raise AppError("Notion a refusé la connexion. Reconnecte l'outil.", 502,
                       code="notion_unreachable")
    resultats = r.json().get("results") or []
    if not resultats:
        raise AppError("Aucune page Notion partagée avec Axial. Partage une page "
                       "avec l'intégration, puis réessaie.", 400,
                       code="notion_no_target")

    creation = httpx.post(
        f"{NOTION_API}/pages", headers=entetes,
        json={"parent": {"page_id": resultats[0]["id"]},
              "properties": {"title": [{"text": {"content": titre[:200]}}]},
              "children": _blocs_notion(contenu)},
        timeout=60.0)
    if creation.status_code >= 300:
        logger.warning("Création de page Notion refusée : %s", creation.text[:200])
        raise AppError("Notion a refusé la création de la page.", 502,
                       code="notion_create_failed")
    return creation.json().get("url", "")


def vers_drive(jeton: str, titre: str, pdf: bytes) -> str:
    """Déposer le PDF du rapport dans Drive et renvoyer son lien."""
    limites = {"Authorization": f"Bearer {jeton}"}
    fichiers = {
        "metadata": (None, f'{{"name": "{titre[:120]}.pdf"}}', "application/json"),
        "file": ("rapport.pdf", io.BytesIO(pdf), "application/pdf"),
    }
    r = httpx.post("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                   headers=limites, files=fichiers, timeout=120.0)
    if r.status_code >= 300:
        logger.warning("Envoi Drive refusé : %s", r.text[:200])
        raise AppError("Google Drive a refusé le dépôt. Reconnecte l'outil.", 502,
                       code="drive_upload_failed")
    return f"https://drive.google.com/file/d/{r.json().get('id')}/view"
