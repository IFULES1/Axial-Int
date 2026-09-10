from app.modules.viz.pipeline import depuis_graphique, extraire_et_compiler, tableau_de_repli

BON = ('```viz\n{"version":"1","intent":"domination","title":"Parts","unit":"%",'
       '"series":[{"label":"A","value":60},{"label":"B","value":40}],"sources":[1]}\n```')


def test_un_bloc_valide_est_compile():
    v = extraire_et_compiler("intro\n" + BON)[0]
    assert v.statut == "ok" and v.kind == "bar_h"
    assert v.vl["data"]["values"][0]["label"] == "A"
    assert len(v.empreinte) == 64


def test_un_json_casse_retombe_en_tableau():
    v = extraire_et_compiler("```viz\n{pas du json\n```")[0]
    assert v.statut.startswith("repli_tableau:schema") and v.vl is None


def test_un_spec_invalide_retombe_en_tableau_avec_ses_donnees():
    md = BON.replace('"sources":[1]', '"sources":[1],"highlight":"Zeta"')
    v = extraire_et_compiler(md)[0]
    assert v.statut.startswith("repli_tableau:schema")


def test_le_tableau_de_repli_garde_les_donnees():
    v = extraire_et_compiler(BON)[0]
    assert tableau_de_repli(v.spec) == [["", "%"], ["A", "60"], ["B", "40"]]


def test_les_index_suivent_l_ordre_d_apparition_tous_types_confondus():
    md = ("Graphique : Parts 2026\n| Acteur | Part |\n|---|---|\n| A | 60 % |\n| B | 40 % |\n\n"
          "texte\n\n" + BON)
    vizs = extraire_et_compiler(md)
    assert [v.index for v in vizs] == [0, 1]
    assert vizs[0].statut == "ok" and vizs[0].spec["intent"] == "comparaison"


def test_graphique_ancienne_marque_devient_un_spec():
    s = depuis_graphique("Parts 2026", [["Acteur", "Part"], ["A", "60 %"], ["B", "40 %"]])
    assert s and s.intent == "comparaison" and s.unit == "%" and s.series[0].value == 60


def test_graphique_ancienne_marque_heterogene_donne_none():
    assert depuis_graphique("X", [["a", "b"], ["A", "3 Md€"], ["B", "40 %"]]) is None
