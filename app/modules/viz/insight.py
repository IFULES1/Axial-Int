"""Le point important du graphique, calculé — pas seulement « toutes les
données affichées ». Le modèle peut l'imposer (`highlight`) ; sinon
l'intention décide : domination → le max, croissance → le dernier point et
le multiplicateur, rupture → le plus grand écart, concentration → le cumul
des trois premiers, entonnoir → la part restante au bas.
"""
from __future__ import annotations

from app.modules.viz.schema import VizSpec


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",") if v % 1 else f"{v:.0f}"


def point_cle(spec: VizSpec) -> tuple[str | None, str | None]:
    """(label à mettre en avant, annotation courte) — déterministe."""
    if spec.highlight:
        return spec.highlight, None
    s = spec.series or []
    if not s:
        return None, None
    u = f" {spec.unit}" if spec.unit else ""
    if spec.intent in ("domination", "classement", "comparaison", "repartition"):
        return max(s, key=lambda p: p.value).label, None
    if spec.intent == "concentration":
        top = max(s, key=lambda p: p.value)
        cumul = sum(sorted((p.value for p in s), reverse=True)[:3])
        return top.label, f"Top 3 = {_fmt(cumul)}{u}"
    if spec.intent in ("croissance", "evolution", "projection"):
        a, b = s[0].value, s[-1].value
        if a > 0:
            return s[-1].label, f"×{b / a:.1f} entre {s[0].label} et {s[-1].label}"
        return s[-1].label, None
    if spec.intent == "rupture":
        i = max(range(1, len(s)), key=lambda k: abs(s[k].value - s[k - 1].value))
        delta = s[i].value - s[i - 1].value
        return s[i].label, f"{'+' if delta >= 0 else '−'}{_fmt(abs(delta))}{u} en {s[i].label}"
    if spec.intent == "entonnoir":
        if s[0].value:
            return s[-1].label, f"{100 * s[-1].value / s[0].value:.0f} % du sommet"
        return s[-1].label, None
    return None, None
