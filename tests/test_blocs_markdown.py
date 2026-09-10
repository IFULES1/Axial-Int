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
