import json

import pytest
from pydantic import ValidationError

from app.modules.viz import registry, render, selector
from app.modules.viz.insight import point_cle
from app.modules.viz.schema import VizSpec

PARTS = {"version": "1", "intent": "domination", "title": "Parts de marché 2026", "unit": "%",
         "series": [{"label": "Alpha Audit", "value": 41}, {"label": "BetaCheck", "value": 25},
                    {"label": "Gamma Ctrl", "value": 14}, {"label": "Autres", "value": 20}],
         "sources": [3, 7]}
CROISSANCE = {"version": "1", "intent": "croissance", "title": "SAM 2024-2028", "unit": "M€",
              "series": [{"label": "2024", "value": 330}, {"label": "2025", "value": 372},
                         {"label": "2026", "value": 420}, {"label": "2027", "value": 471}]}


def test_le_schema_refuse_deux_structures_de_donnees():
    with pytest.raises(ValidationError):
        VizSpec.model_validate({**PARTS, "steps": [{"label": "a", "delta": 1}, {"label": "b", "delta": 2}]})


def test_le_schema_refuse_un_highlight_inconnu():
    with pytest.raises(ValidationError):
        VizSpec.model_validate({**PARTS, "highlight": "Zeta"})


def test_domination_sur_libelles_longs_donne_bar_h():
    assert selector.choisir(VizSpec.model_validate(PARTS)) == "bar_h"


def test_croissance_sur_quatre_annees_donne_line():
    assert selector.choisir(VizSpec.model_validate(CROISSANCE)) == "line"


def test_croissance_sur_deux_points_donne_kpi():
    s = VizSpec.model_validate({**CROISSANCE, "series": CROISSANCE["series"][:2]})
    assert selector.choisir(s) == "kpi"


def test_repartition_a_100_pct_donne_donut_sinon_bar_h():
    assert selector.choisir(VizSpec.model_validate({**PARTS, "intent": "repartition"})) == "donut"
    s = {**PARTS, "intent": "repartition", "series": PARTS["series"] + [{"label": "Delta", "value": 30}]}
    assert selector.choisir(VizSpec.model_validate(s)) == "bar_h"


def test_entonnoir_donne_funnel():
    s = {"version": "1", "intent": "entonnoir", "title": "TAM SAM SOM", "unit": "M€",
         "series": [{"label": "TAM", "value": 3200}, {"label": "SAM", "value": 420}, {"label": "SOM", "value": 38}]}
    assert selector.choisir(VizSpec.model_validate(s)) == "funnel"


def test_un_pont_donne_waterfall():
    s = VizSpec.model_validate({**PARTS, "intent": "pont", "series": None,
                                "steps": [{"label": "Revenu", "delta": 100}, {"label": "Coûts", "delta": -60}]})
    assert selector.choisir(s) == "waterfall"


def test_un_kind_fourni_et_coherent_est_conserve():
    assert selector.choisir(VizSpec.model_validate({**PARTS, "kind": "bar"})) == "bar"


def test_un_kind_fourni_et_incoherent_est_corrige():
    assert selector.choisir(VizSpec.model_validate({**CROISSANCE, "kind": "donut"})) == "line"


def test_insight_domination_met_le_max_en_avant():
    label, note = point_cle(VizSpec.model_validate(PARTS))
    assert label == "Alpha Audit"


def test_insight_croissance_annote_le_multiplicateur():
    label, note = point_cle(VizSpec.model_validate(CROISSANCE))
    assert label == "2027" and note.startswith("×1.4")


def test_chaque_kind_du_registre_compile_en_vegalite_valide():
    specs = {
        "bar_h": PARTS, "bar": {**PARTS, "intent": "comparaison"}, "line": CROISSANCE,
        "donut": {**PARTS, "intent": "repartition"}, "kpi": {**CROISSANCE, "series": CROISSANCE["series"][:2]},
        "funnel": {"version": "1", "intent": "entonnoir", "title": "TAM SAM SOM", "unit": "M€",
                   "series": [{"label": "TAM", "value": 3200}, {"label": "SAM", "value": 420}, {"label": "SOM", "value": 38}]},
        "scatter": {"version": "1", "intent": "positionnement", "title": "Positionnement", "unit": "",
                    "axes": {"x": "Revenu (M€)", "y": "Croissance (%)"},
                    "points": [{"label": "A", "x": 10, "y": 5}, {"label": "B", "x": 20, "y": 15},
                               {"label": "C", "x": 5, "y": 30}, {"label": "D", "x": 40, "y": 2}]},
    }
    for kind, brut in specs.items():
        vl = registry.REGISTRE[kind].compiler(VizSpec.model_validate(brut))
        assert render.compile_ou_none(vl) is not None, kind
        assert "<svg" in render.vers_svg(vl)


def test_le_png_est_un_png_et_l_empreinte_est_stable():
    vl = registry.REGISTRE["bar_h"].compiler(VizSpec.model_validate(PARTS))
    assert render.vers_png(vl)[:8] == b"\x89PNG\r\n\x1a\n"
    assert render.empreinte(vl) == render.empreinte(json.loads(json.dumps(vl)))


def test_le_catalogue_est_genere_depuis_le_registre():
    cat = registry.catalogue_pour_prompt()
    for kind in registry.REGISTRE:
        assert kind in cat
