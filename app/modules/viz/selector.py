"""Choix déterministe du type de graphique à partir de l'intention et de la
forme des données. Peut contredire le `kind` demandé par le modèle : un donut
à onze parts devient un classement, une « croissance » sur deux points un
chiffre clé. Renvoie None quand aucun graphique n'est justifié — le rendu
retombe alors en tableau.
"""
from __future__ import annotations

import re

from app.modules.viz.schema import VizSpec

# 2024 · 2024-T1 · T1 2024 · 2024/25 · Q3 2025 · S1 2026
_PERIODE = re.compile(
    r"^(19|20)\d{2}(\s*[-/]\s*((T|Q|S)?\d{1,2}|\d{2}))?$|^(T|Q|S)[1-4]\s*(19|20)\d{2}$",
    re.IGNORECASE,
)

# Un kind demandé par le modèle est gardé s'il reste cohérent avec le kind
# déduit ; sinon le kind déduit l'emporte.
_COMPATIBLES = {
    "bar_h": {"bar_h", "bar"}, "bar": {"bar", "bar_h"}, "line": {"line", "area"},
    "donut": {"donut", "bar_h"}, "kpi": {"kpi"}, "funnel": {"funnel", "bar_h"},
    "scatter": {"scatter", "quadrant"}, "waterfall": {"waterfall"},
}


def nature(spec: VizSpec) -> str:
    if spec.points is not None:
        return "bidim"
    if spec.steps is not None:
        return "pont"
    labels = [p.label.strip() for p in spec.series]
    return "temporel" if all(_PERIODE.match(lb) for lb in labels) else "categoriel"


def _deduire(spec: VizSpec) -> str | None:
    nat, n = nature(spec), spec.n
    if nat == "bidim":
        seuils = bool(spec.note and "seuil" in spec.note.lower())
        return "quadrant" if (spec.intent == "positionnement" and seuils) else "scatter"
    if nat == "pont":
        return "waterfall"
    if spec.intent in ("croissance", "evolution", "projection", "rupture"):
        if nat == "temporel" and n >= 3:
            return "line"
        return "kpi" if n <= 4 else "bar"
    if spec.intent == "entonnoir":
        return "funnel" if 3 <= n <= 6 else "bar_h"
    if spec.intent == "repartition":
        total = sum(p.value for p in spec.series)
        return "donut" if (spec.unit == "%" and n <= 6 and 95 <= total <= 105) else "bar_h"
    if spec.intent in ("domination", "classement", "comparaison", "concentration"):
        court = all(len(p.label) <= 12 for p in spec.series)
        return "bar" if (n <= 4 and court and nat == "temporel") else "bar_h"
    return None


def choisir(spec: VizSpec) -> str | None:
    """Le kind final, ou None (pas de graphique, repli tableau)."""
    kind = _deduire(spec)
    if kind and spec.kind and spec.kind in _COMPATIBLES.get(kind, {kind}):
        return spec.kind
    return kind
