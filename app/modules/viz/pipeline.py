"""Du markdown du modèle aux rendus : extraction des blocs de visualisation,
validation du VizSpec, sélection du type, compilation Vega-Lite, et vérité
d'exécution (une spec qui ne compile pas n'est pas un graphique).

Un bloc invalide ne lève jamais : il devient un tableau de repli et son statut
est conservé pour mesurer, plus tard, à quelle fréquence le modèle se trompe.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from pydantic import ValidationError

from app.modules.reports.blocs import decouper, serie_numerique
from app.modules.viz import registry, render, selector
from app.modules.viz.schema import VizSpec


@dataclass
class Viz:
    index: int
    spec: dict
    kind: str | None
    vl: dict | None
    statut: str  # "ok" | "repli_tableau:<raison>"
    empreinte: str = ""

    def dict(self) -> dict:
        return asdict(self)


def depuis_graphique(titre: str, cellules: list[list[str]]) -> VizSpec | None:
    """Compatibilité avec la marque « Graphique : » des rapports du 10/09 :
    un tableau à deux colonnes d'unité unique devient un VizSpec « comparaison »."""
    s = serie_numerique(cellules)
    if not s:
        return None
    etiquettes, valeurs, unite = s
    try:
        return VizSpec(intent="comparaison", title=(titre or "Graphique")[:80], unit=unite[:8],
                       series=[{"label": e[:60], "value": v} for e, v in zip(etiquettes, valeurs)])
    except ValidationError:
        return None


def compiler_spec(index: int, spec: VizSpec) -> Viz:
    kind = selector.choisir(spec)
    if kind is None or kind not in registry.REGISTRE:
        return Viz(index, spec.model_dump(), kind, None, f"repli_tableau:aucun_kind:{kind}")
    vl = registry.REGISTRE[kind].compiler(spec)
    if render.compile_ou_none(vl) is None:
        return Viz(index, spec.model_dump(), kind, None, "repli_tableau:vegalite")
    return Viz(index, spec.model_dump(), kind, vl, "ok", render.empreinte(vl))


def extraire_et_compiler(markdown: str) -> list[Viz]:
    sortie: list[Viz] = []
    for b in decouper(markdown or ""):
        if b.genre == "viz":
            try:
                spec = VizSpec.model_validate(json.loads(b.texte))
            except (ValueError, ValidationError) as e:
                sortie.append(Viz(b.index, {"brut": b.texte[:2000]}, None, None,
                                  f"repli_tableau:schema:{str(e)[:120]}"))
                continue
            sortie.append(compiler_spec(b.index, spec))
        elif b.genre == "graphique":
            spec = depuis_graphique(b.texte, b.cellules)
            if spec is None:
                sortie.append(Viz(b.index, {"title": b.texte, "cellules": b.cellules}, None, None,
                                  "repli_tableau:graphique_heterogene"))
            else:
                sortie.append(compiler_spec(b.index, spec))
    return sortie


def tableau_de_repli(spec: dict) -> list[list[str]]:
    """Les données du bloc, en cellules — pour que rien ne se perde quand le
    graphique n'est pas rendu."""
    if spec.get("cellules"):
        return spec["cellules"]
    if spec.get("series"):
        return [["", spec.get("unit") or "Valeur"]] + [
            [p["label"], f"{p['value']:g}"] for p in spec["series"]]
    if spec.get("points"):
        axes = spec.get("axes") or {}
        return [["", axes.get("x", "x"), axes.get("y", "y")]] + [
            [p["label"], f"{p['x']:g}", f"{p['y']:g}"] for p in spec["points"]]
    if spec.get("steps"):
        return [["", "Δ"]] + [[s["label"], f"{s['delta']:+g}"] for s in spec["steps"]]
    return [["Graphique non rendu"]]
