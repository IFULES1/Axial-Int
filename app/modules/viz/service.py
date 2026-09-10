"""Préparation des visualisations d'un texte : extraction, compilation,
enregistrement des rendus. Appelé à l'archivage d'un rapport ou d'un message,
et à la volée pour le chat en flux.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.modules.viz import pipeline
from app.modules.viz.models import VizRendu

logger = logging.getLogger("axial.viz")


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
