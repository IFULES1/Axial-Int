"""Registre des visualisations : pour chaque `kind`, sa description (elle
alimente le prompt, jamais recopiée à la main) et son compilateur
VizSpec → Vega-Lite. Ajouter un type = une entrée ici + un test.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.modules.viz import theme
from app.modules.viz.insight import point_cle
from app.modules.viz.schema import VizSpec


@dataclass(frozen=True)
class Entree:
    kind: str
    description: str
    use_when: str
    avoid_when: str
    compiler: Callable[[VizSpec], dict]


def _fmt(unit: str) -> str:
    """Expression Vega pour afficher l'unité sur l'axe, jamais dans le titre."""
    if not unit:
        return "datum.label"
    return f"datum.label + ' {unit}'"


def _base(spec: VizSpec, w: int = theme.LARGEUR, h: int = 220) -> dict:
    titre: dict = {"text": spec.title}
    if spec.subtitle:
        titre["subtitle"] = spec.subtitle
    return {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "width": w, "height": h,
            "title": titre, "config": theme.CONFIG}


def _annoter(vl: dict, spec: VizSpec, annotation: str | None) -> None:
    if annotation:
        vl["title"]["subtitle"] = (spec.subtitle + " — " if spec.subtitle else "") + annotation


def _valeurs(spec: VizSpec) -> list[dict]:
    return [{"label": p.label, "value": p.value} for p in spec.series]


def bar_h(spec: VizSpec) -> dict:
    cle, annotation = point_cle(spec)
    values = _valeurs(spec)
    vl = _base(spec, h=28 * len(values) + 20)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "bar", "cornerRadiusEnd": 3},
             "encoding": {"x": {"field": "value", "type": "quantitative", "title": None,
                                "axis": {"labelExpr": _fmt(spec.unit), "grid": True}},
                          "y": {"field": "label", "type": "nominal", "sort": "-x", "title": None},
                          "color": {"condition": {"test": f"datum.label == {cle!r}", "value": theme.ACCENT},
                                    "value": theme.CONTEXTE}}},
            {"mark": {"type": "text", "align": "left", "dx": 4, "fontSize": 9, "color": theme.TEXTE},
             "encoding": {"x": {"field": "value", "type": "quantitative"},
                          "y": {"field": "label", "type": "nominal", "sort": "-x"},
                          "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
        ],
    })
    _annoter(vl, spec, annotation)
    return vl


def bar(spec: VizSpec) -> dict:
    cle, annotation = point_cle(spec)
    values = _valeurs(spec)
    vl = _base(spec)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3, "width": {"band": 0.55}},
             "encoding": {"x": {"field": "label", "type": "ordinal", "title": None, "sort": None},
                          "y": {"field": "value", "type": "quantitative", "title": None,
                                "axis": {"labelExpr": _fmt(spec.unit)}},
                          "color": {"condition": {"test": f"datum.label == {cle!r}", "value": theme.ACCENT},
                                    "value": theme.CONTEXTE}}},
            {"mark": {"type": "text", "dy": -6, "fontSize": 9, "color": theme.TEXTE},
             "encoding": {"x": {"field": "label", "type": "ordinal", "sort": None},
                          "y": {"field": "value", "type": "quantitative"},
                          "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
        ],
    })
    _annoter(vl, spec, annotation)
    return vl


def line(spec: VizSpec) -> dict:
    cle, annotation = point_cle(spec)
    values = [{"label": p.label, "value": p.value, "cle": p.label == cle} for p in spec.series]
    vl = _base(spec)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "area", "opacity": 0.12, "color": theme.ACCENT},
             "encoding": {"x": {"field": "label", "type": "ordinal", "title": None, "sort": None},
                          "y": {"field": "value", "type": "quantitative", "title": None,
                                "axis": {"labelExpr": _fmt(spec.unit)}}}},
            {"mark": {"type": "line", "point": True, "color": theme.ACCENT, "strokeWidth": 2},
             "encoding": {"x": {"field": "label", "type": "ordinal", "sort": None},
                          "y": {"field": "value", "type": "quantitative"}}},
            {"mark": {"type": "text", "dy": -10, "fontSize": 9.5, "fontWeight": "bold", "color": theme.TEXTE},
             "transform": [{"filter": "datum.cle"}],
             "encoding": {"x": {"field": "label", "type": "ordinal", "sort": None},
                          "y": {"field": "value", "type": "quantitative"},
                          "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
        ],
    })
    _annoter(vl, spec, annotation)
    return vl


def donut(spec: VizSpec) -> dict:
    values = _valeurs(spec)
    vl = _base(spec, h=220)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "arc", "innerRadius": 62, "outerRadius": 100, "padAngle": 0.01, "cornerRadius": 3},
             "encoding": {"theta": {"field": "value", "type": "quantitative", "stack": True},
                          "color": {"field": "label", "type": "nominal", "sort": "-value",
                                    "legend": {"title": None, "orient": "right"},
                                    "scale": {"range": theme.CATEGORIES}}}},
            {"mark": {"type": "text", "radius": 82, "fontSize": 9, "color": "white", "fontWeight": "bold"},
             "encoding": {"theta": {"field": "value", "type": "quantitative", "stack": True},
                          "text": {"field": "value", "type": "quantitative", "format": ".0f"}}},
        ],
    })
    return vl


def kpi(spec: VizSpec) -> dict:
    values = [{"label": p.label, "value": p.value, "i": i} for i, p in enumerate(spec.series)]
    n = len(values)
    vl = _base(spec, h=110)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "text", "fontSize": 28, "fontWeight": "bold", "color": theme.ACCENT, "dy": -12},
             "encoding": {"x": {"field": "i", "type": "quantitative", "axis": None,
                                "scale": {"domain": [-0.5, n - 0.5]}},
                          "y": {"value": 55},
                          "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
            {"mark": {"type": "text", "fontSize": 10, "color": theme.GRIS, "dy": 14},
             "encoding": {"x": {"field": "i", "type": "quantitative"},
                          "y": {"value": 55},
                          "text": {"field": "label", "type": "nominal"}}},
        ],
    })
    if spec.unit:
        vl["title"]["subtitle"] = f"{spec.subtitle + ' — ' if spec.subtitle else ''}en {spec.unit}"
    return vl


def funnel(spec: VizSpec) -> dict:
    values = [{"label": p.label, "value": p.value, "ordre": i} for i, p in enumerate(spec.series)]
    vl = _base(spec, h=34 * len(values) + 10)
    vl.update({
        "data": {"values": values},
        "transform": [{"calculate": "-datum.value/2", "as": "x0"}, {"calculate": "datum.value/2", "as": "x1"}],
        "layer": [
            {"mark": {"type": "bar", "cornerRadius": 3},
             "encoding": {"x": {"field": "x0", "type": "quantitative", "axis": None}, "x2": {"field": "x1"},
                          "y": {"field": "label", "type": "nominal", "sort": {"field": "ordre"}, "title": None},
                          "color": {"field": "ordre", "type": "quantitative", "legend": None,
                                    "scale": {"range": [theme.CONTEXTE, theme.ACCENT]}}}},
            {"mark": {"type": "text", "fontSize": 9.5, "fontWeight": "bold", "color": theme.TEXTE},
             "encoding": {"x": {"value": theme.LARGEUR / 2},
                          "y": {"field": "label", "type": "nominal", "sort": {"field": "ordre"}},
                          "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
        ],
    })
    _, annotation = point_cle(spec)
    _annoter(vl, spec, annotation)
    return vl


def scatter(spec: VizSpec) -> dict:
    values = [{"label": p.label, "x": p.x, "y": p.y, "size": p.size or 1} for p in spec.points]
    vl = _base(spec, h=260)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "circle", "opacity": 0.85, "color": theme.ACCENT},
             "encoding": {"x": {"field": "x", "type": "quantitative", "title": spec.axes["x"]},
                          "y": {"field": "y", "type": "quantitative", "title": spec.axes["y"]},
                          "size": {"field": "size", "type": "quantitative", "legend": None,
                                   "scale": {"range": [80, 900]}}}},
            {"mark": {"type": "text", "dy": -12, "fontSize": 9, "color": theme.TEXTE},
             "encoding": {"x": {"field": "x", "type": "quantitative"},
                          "y": {"field": "y", "type": "quantitative"},
                          "text": {"field": "label", "type": "nominal"}}},
        ],
    })
    return vl


REGISTRE: dict[str, Entree] = {
    "kpi": Entree("kpi", "Chiffres clés", "1 à 4 valeurs qui résument", "plus de 4 valeurs", kpi),
    "bar": Entree("bar", "Barres verticales", "≤ 4 catégories courtes ou périodes", "libellés longs", bar),
    "bar_h": Entree("bar_h", "Classement horizontal", "classement, domination, libellés longs",
                    "séries temporelles", bar_h),
    "line": Entree("line", "Évolution", "≥ 3 périodes ordonnées", "catégories, < 3 points", line),
    "donut": Entree("donut", "Répartition", "parts qui totalisent 100 %, ≤ 6", "> 6 parts, valeurs proches", donut),
    "funnel": Entree("funnel", "Entonnoir", "TAM → SAM → SOM, étapes emboîtées", "étapes non emboîtées", funnel),
    "scatter": Entree("scatter", "Positionnement", "acteurs sur deux mesures", "< 4 points", scatter),
}


def catalogue_pour_prompt() -> str:
    """Le catalogue envoyé au modèle — généré, jamais recopié."""
    return "\n".join(
        f"- {e.kind} : {e.description}. Utiliser : {e.use_when}. Éviter : {e.avoid_when}."
        for e in REGISTRE.values()
    )
