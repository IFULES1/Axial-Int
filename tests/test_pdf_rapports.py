import io

from app.modules.reports.pdf import _inline, render_pdf


def test_les_citations_deviennent_des_liens_internes():
    assert _inline("Le marché pèse 3 Md€ [2].", liens=True) == \
        'Le marché pèse 3 Md€ <a href="#src-2" color="#7976F7">[2]</a>.'


def test_les_citations_multiples_sont_toutes_liees():
    out = _inline("vu [1][3]", liens=True)
    assert 'href="#src-1"' in out and 'href="#src-3"' in out


def test_sans_sources_les_citations_restent_du_texte():
    assert _inline("vu [1]") == "vu [1]"


def test_le_pdf_contient_une_section_sources_depuis_les_donnees():
    sources = [{"title": "Rapport Xerfi", "url": "https://xerfi.com/a", "domain": "xerfi.com",
                "source": "web", "excerpt": "…"}]
    pdf = render_pdf("T", "Un chiffre [1].", sources=sources)
    t = _texte(pdf)
    assert "Sources" in t and "Rapport Xerfi" in t and "xerfi.com" in t


def _texte(pdf: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)


def test_un_tableau_est_rendu_cellule_par_cellule():
    md = "## 1. Parts\n| Acteur | Part |\n|---|---|\n| Alpha | 40 % |"
    pdf = render_pdf("Test", md)
    assert pdf.startswith(b"%PDF-")
    t = _texte(pdf)
    assert "Alpha" in t and "40 %" in t
    assert "|---|" not in t  # la ligne de séparation ne fuit pas dans le document


def test_la_section_sources_du_modele_est_remplacee_par_celle_des_donnees():
    md = "## 1. Marché\nUn chiffre [1].\n\n## Sources\n1. Truc texte du modèle\n2. Machin"
    pdf = render_pdf("T", md, sources=[{"title": "Vraie source", "url": "https://x.fr",
                                        "domain": "x.fr", "source": "web"}])
    t = _texte(pdf)
    assert "Vraie source" in t
    assert "Truc texte du modèle" not in t  # la liste textuelle du modèle ne double pas la nôtre
    assert t.count("Sources") == 1


def test_sans_sources_fournies_la_section_du_modele_est_conservee():
    md = "## 1. Marché\nUn chiffre [1].\n\n## Sources\n1. Truc texte du modèle"
    t = _texte(render_pdf("T", md))
    assert "Truc texte du modèle" in t



def test_un_tableau_marque_graphique_est_trace_et_le_tableau_disparait():
    md = "Graphique : Parts de marché 2026\n| Acteur | Part |\n|---|---|\n| Alpha | 40 % |\n| Beta | 25 % |\n| Gamma | 15 % |"
    pdf = render_pdf("T", md)
    assert b"/XObject" in pdf                   # le graphique est une image (titre inclus dedans)
    assert "Acteur" not in _texte(pdf)          # l'en-tête du tableau n'est plus rendu


def test_un_tableau_sans_marque_reste_un_tableau_sans_graphique():
    md = "| Acteur | Part |\n|---|---|\n| Alpha | 40 % |\n| Beta | 25 % |\n| Gamma | 15 % |"
    t = _texte(render_pdf("T", md))
    assert "Acteur" in t and "Gamma" in t


def test_une_marque_graphique_sur_des_donnees_heterogenes_garde_le_tableau():
    md = "Graphique : Tailles\n| Pays | Taille |\n|---|---|\n| FR | 3 Md€ |\n| DE | 40 % |\n| IT | 2 Md€ |"
    t = _texte(render_pdf("T", md))
    assert "Tailles" in t and "Pays" in t and "3 Md€" in t


def _vizs(md):
    from app.modules.viz.pipeline import extraire_et_compiler

    return [v.dict() for v in extraire_et_compiler(md)]


VIZ_OK = ('```viz\n{"version":"1","intent":"domination","title":"Parts de marché","unit":"%",'
          '"series":[{"label":"A","value":60},{"label":"B","value":40}],"sources":[1]}\n```')


def test_un_bloc_viz_compile_devient_une_image_dans_le_pdf():
    md = "## 1. Parts\n" + VIZ_OK
    pdf = render_pdf("T", md, sources=[{"title": "S", "url": "https://s.fr", "domain": "s.fr", "source": "web"}],
                     vizs=_vizs(md))
    assert b"/XObject" in pdf                 # une image est embarquée
    t = _texte(pdf)
    assert "version" not in t and "intent" not in t   # le JSON brut n'apparaît jamais


def test_un_bloc_viz_invalide_devient_un_tableau():
    md = VIZ_OK.replace('"sources":[1]', '"sources":[1],"highlight":"Zeta"')
    t = _texte(render_pdf("T", md, vizs=_vizs(md)))
    assert "version" not in t


def test_un_bloc_viz_sans_rendus_prepares_est_compile_a_la_volee():
    md = "## 1\n" + VIZ_OK
    pdf = render_pdf("T", md)           # vizs=None : ancien appel, rapport archivé avant la V1
    assert b"/XObject" in pdf and "intent" not in _texte(pdf)


def test_l_ancienne_marque_graphique_passe_par_le_meme_moteur():
    md = "Graphique : Parts 2026\n| Acteur | Part |\n|---|---|\n| Alpha | 40 % |\n| Beta | 25 % |\n| Gamma | 15 % |"
    pdf = render_pdf("T", md)
    assert b"/XObject" in pdf
    assert "Acteur" not in _texte(pdf)    # le tableau est remplacé par le graphique
