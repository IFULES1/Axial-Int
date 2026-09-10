from app.modules.reports.blocs import decouper


def test_un_tableau_devient_des_cellules():
    md = "| Acteur | Part |\n|---|---|\n| Alpha | 40 % |\n| Beta | 25 % |"
    blocs = decouper(md)
    assert [b.genre for b in blocs] == ["tableau"]
    assert blocs[0].cellules == [["Acteur", "Part"], ["Alpha", "40 %"], ["Beta", "25 %"]]


def test_la_ligne_de_separation_est_ignoree_meme_avec_alignement():
    md = "| a | b |\n|:---|---:|\n| 1 | 2 |"
    assert decouper(md)[0].cellules == [["a", "b"], ["1", "2"]]


def test_titres_paragraphes_puces_et_regle():
    md = "# T\n\n## 1. S\nUn paragraphe.\n- x\n- y\n\n---\n### 1.1 Sous"
    genres = [b.genre for b in decouper(md)]
    assert genres == ["h1", "h2", "p", "puces", "hr", "h3"]


def test_une_ligne_seule_avec_barre_reste_un_paragraphe():
    # Une seule ligne « | » sans ligne de séparation suivante n'est pas un tableau.
    assert decouper("| pas un tableau")[0].genre == "p"


def test_une_serie_homogene_est_reconnue():
    from app.modules.reports.blocs import serie_numerique

    c = [["Acteur", "Part"], ["Alpha", "40 %"], ["Beta", "25,5 %"]]
    assert serie_numerique(c) == (["Alpha", "Beta"], [40.0, 25.5], "%")


def test_des_unites_melangees_ne_donnent_pas_de_graphique():
    from app.modules.reports.blocs import serie_numerique

    c = [["Pays", "Taille"], ["FR", "3 Md€"], ["DE", "40 %"]]
    assert serie_numerique(c) is None


def test_un_tableau_textuel_ne_donne_pas_de_graphique():
    from app.modules.reports.blocs import serie_numerique

    c = [["Acteur", "Positionnement"], ["Alpha", "Premium"], ["Beta", "Low cost"]]
    assert serie_numerique(c) is None


def test_une_ligne_graphique_devant_un_tableau_donne_un_bloc_graphique():
    md = "Graphique : Parts de marché 2026\n| Acteur | Part |\n|---|---|\n| Alpha | 40 % |\n| Beta | 25 % |"
    blocs = decouper(md)
    assert [b.genre for b in blocs] == ["graphique"]
    assert blocs[0].texte == "Parts de marché 2026"
    assert blocs[0].cellules[1] == ["Alpha", "40 %"]


def test_la_ligne_graphique_sans_tableau_reste_un_paragraphe():
    blocs = decouper("Graphique : sans données\nUn paragraphe.")
    assert [b.genre for b in blocs] == ["p", "p"]


def test_un_tableau_sans_la_ligne_reste_un_tableau():
    md = "| Acteur | Part |\n|---|---|\n| Alpha | 40 % |\n| Beta | 25 % |"
    assert decouper(md)[0].genre == "tableau"


def test_un_bloc_viz_est_un_bloc_type_avec_son_index():
    md = "## 1\n```viz\n{\"a\": 1}\n```\ntexte\n```viz\n{\"b\": 2}\n```"
    vizs = [b for b in decouper(md) if b.genre == "viz"]
    assert [b.index for b in vizs] == [0, 1]
    assert vizs[0].texte == '{"a": 1}'
    assert [b.genre for b in decouper(md)] == ["h2", "viz", "p", "viz"]
