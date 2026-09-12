"""Préparation des visualisations d'un texte : extraction, compilation,
enregistrement des rendus. Appelé à l'archivage d'un rapport ou d'un message,
et à la volée pour le chat en flux.
"""
from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.viz import pipeline
from app.modules.viz.models import VizRendu

logger = logging.getLogger("axial.viz")

# --- Empreintes possédées par un compte (spec §5.3) -------------------------
# Un compte authentifié ne doit voir que SES graphiques : ceux de ses propres
# rapports, et ceux de ses messages de chat (par ses conversations). Sans
# cela, connaître l'empreinte (devinable — c'est le sha256 du spec compilé)
# suffisait à lire l'image d'un graphique appartenant à un autre compte.
#
# Cache en process, 60 s : une page de rapport affiche plusieurs graphiques,
# chacun via une requête HTTP séparée (`<img src=...>`) — sans cache, chaque
# image relirait tous les rapports et messages du compte. Ce n'est PAS un
# substitut à l'autorisation (l'appartenance est revérifiée à chaque appel),
# seulement une amortie du coût de la lecture.
_CACHE_TTL_SECONDES = 60
_cache_empreintes: dict[str, tuple[float, set[str]]] = {}


def empreintes_du_compte(db: Session, user_id: str) -> set[str]:
    """Empreintes des graphiques que `user_id` a le droit de voir."""
    maintenant = time.monotonic()
    entree = _cache_empreintes.get(user_id)
    if entree is not None and maintenant - entree[0] < _CACHE_TTL_SECONDES:
        return entree[1]

    from app.modules.intelligence.models import Conversation, Message
    from app.modules.reports.models import Report

    uid = uuid.UUID(user_id)
    empreintes: set[str] = set()
    for cible in (
        select(Report.viz).where(Report.user_id == uid),
        select(Message.viz)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == uid),
    ):
        for viz in db.scalars(cible):
            if isinstance(viz, list):
                empreintes.update(v.get("empreinte") for v in viz
                                  if isinstance(v, dict) and v.get("empreinte"))

    # Borné : au-delà de 500 comptes en cache, on purge les entrées expirées
    # (un processus long-vivant ne doit pas croître sans limite).
    if len(_cache_empreintes) > 500:
        for cle in [k for k, (t0, _) in _cache_empreintes.items()
                    if maintenant - t0 > _CACHE_TTL_SECONDES]:
            _cache_empreintes.pop(cle, None)
    _cache_empreintes[user_id] = (maintenant, empreintes)
    return empreintes


def preparer(db: Session, markdown: str) -> list[dict]:
    """Liste sérialisable (forme `Viz`) à stocker sur le rapport ou le message.
    Les specs compilés sont enregistrés par empreinte s'ils ne le sont pas déjà."""
    sortie: list[dict] = []
    for v in pipeline.extraire_et_compiler(markdown):
        if v.vl and db.get(VizRendu, v.empreinte) is None:
            db.add(VizRendu(empreinte=v.empreinte, vl=v.vl))
        sortie.append(v.dict())
    if sortie:
        db.flush()
        replis = [v["statut"] for v in sortie if v["statut"] != "ok"]
        if replis:
            logger.info("Viz : %d bloc(s), %d repli(s) : %s", len(sortie), len(replis), replis)
    return sortie


def preparer_sans_faute(db: Session, markdown: str) -> list[dict] | None:
    """Version tolérante pour les chemins d'archivage : une erreur ici ne doit
    jamais empêcher la facturation ni l'enregistrement du texte."""
    try:
        return preparer(db, markdown) or None
    except Exception:  # noqa: BLE001
        logger.exception("Préparation des visualisations échouée")
        return None


def rendu_par_empreinte(db: Session, empreinte: str) -> dict | None:
    r = db.get(VizRendu, empreinte)
    return r.vl if r else None
