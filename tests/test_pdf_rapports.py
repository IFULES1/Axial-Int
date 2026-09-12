import io
import re

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


# --- Parité écran / PDF : les titres de niveau 2 (spec §6) ------------------
#
# L'écran rend le markdown tel quel ; le PDF le reconstruit en flowables
# ReportLab. La seule garantie qui compte pour le lecteur est que la STRUCTURE
# soit la même : les mêmes titres de section, dans le même ordre, sans perte ni
# ajout. Les titres attendus sont relus du markdown par une expression
# indépendante (et non par `blocs.decouper`, que `pdf.py` utilise déjà) — sinon
# le test et le code partageraient le même bug d'analyse.

_H2_MARKDOWN = re.compile(r"^##[ \t]+(.+?)\s*$", re.MULTILINE)

MD_CINQ_SECTIONS = """Chapeau introductif.

## 1. Contexte du marché
La demande a progressé de 18 % sur l'exercice. Le texte est volontairement
long pour que le document dépasse une page et que les sections se répartissent
sur plusieurs pages du PDF. """ + ("Phrase de remplissage. " * 40) + """

## 2. Acteurs en présence
| Acteur | Part |
|---|---|
| Alpha | 40 % |

### 2.1 Une sous-partie qui ne doit pas compter
Un titre de niveau 3 n'est pas une section.

## 3. Dynamique de la demande
""" + ("Encore du texte pour remplir la page. " * 40) + """

## 4. Scénarios à trois ans
- Scénario haut
- Scénario bas

## 5. Recommandations
Conclusion.
"""


def _titres_h2_du_markdown(md: str) -> list[str]:
    return _H2_MARKDOWN.findall(md)


def _lignes(pdf: bytes) -> list[str]:
    return [ligne.strip() for ligne in _texte(pdf).splitlines() if ligne.strip()]


# Corps de fonte des styles de `pdf.py` : H1 18, H2 14, H3 12, corps 10,5.
# Lire la TAILLE et non seulement le texte est ce qui distingue un vrai titre
# de niveau 2 d'un paragraphe ou d'un `###` — l'extraction de texte seule les
# confondrait.
TAILLE_H2 = 14.0


def _titres_du_pdf(pdf: bytes, taille: float = TAILLE_H2) -> list[str]:
    """Les titres rendus à `taille`, dans l'ordre de lecture du document."""
    from pypdf import PdfReader

    titres: list[str] = []
    courant: list[str] = []

    def visiter(texte, cm, tm, police, corps):
        nonlocal courant
        if round(corps or 0, 1) == taille:
            courant.append(texte)
        elif courant:
            titres.append("".join(courant).strip())
            courant = []

    for page in PdfReader(io.BytesIO(pdf)).pages:
        page.extract_text(visitor_text=visiter)
    if courant:
        titres.append("".join(courant).strip())
    return [t for t in titres if t]


def test_les_titres_h2_du_pdf_sont_exactement_ceux_du_markdown_dans_le_meme_ordre():
    """Parité de structure écran / PDF (spec §6) : même liste de sections, même
    ordre, ni perte ni ajout. Le `###` du markdown ne doit PAS y figurer."""
    attendus = _titres_h2_du_markdown(MD_CINQ_SECTIONS)
    assert len(attendus) == 5, attendus

    obtenus = _titres_du_pdf(render_pdf("Marché européen du lithium", MD_CINQ_SECTIONS))
    assert obtenus == attendus, (obtenus, attendus)

    # Le titre de niveau 3 existe bien dans le document, mais à sa taille.
    assert "2.1 Une sous-partie qui ne doit pas compter" in _lignes(
        render_pdf("T", MD_CINQ_SECTIONS))


def test_un_titre_de_niveau_1_dans_le_corps_compte_comme_une_section():
    """`pdf.py` rend `#` et `##` au même niveau : le H1 du document est le titre
    passé à `render_pdf`, donc un `#` dans le corps est une section comme une
    autre. Comportement volontaire, fixé ici pour qu'il ne dérive pas."""
    md = "# Partie liminaire\nTexte.\n\n## 1. Marché\nTexte."
    assert _titres_du_pdf(render_pdf("T", md)) == ["Partie liminaire", "1. Marché"]


def test_la_section_sources_ajoutee_est_le_seul_titre_en_plus():
    """Quand les données fournissent des sources, le PDF ajoute « Sources » —
    et rien d'autre : c'est le seul écart de structure autorisé avec l'écran."""
    md = MD_CINQ_SECTIONS
    sources = [{"title": "Rapport Xerfi", "url": "https://xerfi.com/a",
                "domain": "xerfi.com", "source": "web"}]
    obtenus = _titres_du_pdf(render_pdf("T", md, sources=sources))
    assert obtenus == _titres_h2_du_markdown(md) + ["Sources"], obtenus


def test_un_titre_h2_en_gras_ou_avec_citation_reste_un_titre_h2():
    """`_inline` traite les titres comme le corps : ni le `**` ni le lien de
    citation ne doivent casser le titre, sinon l'écran et le PDF ne montrent
    pas la même section."""
    md = "## 1. **Marché** du lithium [2]\nTexte."
    obtenus = _titres_du_pdf(render_pdf("T", md, sources=[
        {"title": "A", "url": "https://a.fr", "domain": "a.fr", "source": "web"},
        {"title": "B", "url": "https://b.fr", "domain": "b.fr", "source": "web"}]))
    assert obtenus == ["1. Marché du lithium [2]", "Sources"], obtenus


# --- Entrées `viz` abîmées : export dégradé, jamais 500 (revue Task 5, f. 2) --

def test_une_entree_viz_sans_index_est_ignoree_sans_erreur():
    md = "## 1. Parts\n" + VIZ_OK
    # Ligne écrite à la main, telle qu'une migration ou un correctif manuel
    # pourrait en laisser : ni `index`, ni `vl`.
    pdf = render_pdf("T", md, vizs=[{"spec": {"title": "Parts"}}])
    assert pdf.startswith(b"%PDF-")
    assert "1. Parts" in _lignes(pdf)


def test_une_entree_viz_sans_vl_ni_spec_retombe_sur_le_markdown():
    md = "Graphique : Parts de marché\n| Acteur | Part |\n|---|---|\n| Alpha | 40 % |"
    t = _texte(render_pdf("T", md, vizs=[{"index": 0}]))
    # Aucun rendu, aucune spec : les chiffres du tableau markdown restent.
    assert "Alpha" in t and "40 %" in t


def test_le_docx_survit_a_une_entree_viz_abimee():
    from app.modules.reports.export import vers_docx

    class _R:
        title = "T"
        content = "## 1. Parts\n" + VIZ_OK
        sources = None
        viz = [{"spec": {"title": "Parts"}}, {"index": 0}]

    octets = vers_docx(_R())
    assert octets.startswith(b"PK")   # un .docx est un zip
