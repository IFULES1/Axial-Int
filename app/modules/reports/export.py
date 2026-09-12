"""Exports Markdown et DOCX d'un rapport (spec §4).

Le PDF reste dans `pdf.py` (ReportLab). Les trois formats partent du MÊME
markdown archivé et du MÊME découpage en blocs (`blocs.decouper`) : la
question « qu'est-ce qu'un tableau » n'a pas trois réponses selon le bouton
cliqué.

Aucune nouvelle dépendance : `python-docx` est déjà dans `requirements.txt`.
"""
from __future__ import annotations

import io
import logging
import re

from app.modules.reports.blocs import decouper

logger = logging.getLogger("axial.reports.export")

# Même règle que le PDF : le modèle rédige lui-même une section « Sources » en
# texte, et celle qu'on génère depuis les données ferait doublon.
_TITRE_SOURCES = re.compile(r"^\s*(\d+[.)]\s*)?(sources?|r[ée]f[ée]rences?)\b",
                            re.IGNORECASE)
_GRAS = re.compile(r"\*\*(.+?)\*\*")


def _blocs_sans_sources(markdown: str, sources: list | None) -> list:
    """Blocs du markdown, la section « Sources » du modèle écartée quand on en
    génère une depuis les données (avec URL cliquables)."""
    blocs = decouper(markdown or "")
    if not sources:
        return blocs
    garder, sauter = [], False
    for b in blocs:
        if b.genre in ("h1", "h2"):
            sauter = bool(_TITRE_SOURCES.match(b.texte))
        if not sauter:
            garder.append(b)
    return garder


def _ligne_source(n: int, s: dict) -> str:
    titre = (s.get("title") or s.get("domain") or "Source").strip()
    url = (s.get("url") or "").strip()
    ligne = f"{n}. {titre}"
    if s.get("domain"):
        ligne += f" — {s['domain']}"
    if url:
        ligne += f" — {url}"
    elif s.get("source") == "notion":
        ligne += " — espace Notion"
    elif s.get("source") != "web":
        ligne += " — document interne"
    return ligne


def vers_markdown(report) -> str:
    """Le markdown archivé, plus une section « Sources » numérotée.

    Le contenu n'est pas retouché : c'est le texte exact que le modèle a
    produit et que l'utilisateur a lu à l'écran. Le titre est ajouté en `#`
    seulement s'il n'ouvre pas déjà le document — un rapport archivé avant la
    V1 pouvait n'avoir aucun titre dans son corps.
    """
    contenu = (report.content or "").strip()
    titre = (report.title or "Rapport").strip()
    morceaux: list[str] = []
    if not contenu.startswith("# "):
        morceaux.append(f"# {titre}\n")
    morceaux.append(contenu)
    sources = report.sources if isinstance(report.sources, list) else None
    if sources:
        lignes = [_ligne_source(n, s) for n, s in enumerate(sources, start=1)
                  if isinstance(s, dict)]
        if lignes:
            morceaux.append("\n## Sources\n\n" + "\n".join(lignes))
    return "\n".join(morceaux).rstrip() + "\n"


def _sans_gras(texte: str) -> str:
    """`**gras**` → `gras`. Le gras intra-paragraphe demanderait de découper le
    texte en `runs` ; il ne porte aucune information ici, on garde le mot."""
    return _GRAS.sub(r"\1", texte or "")


def _image_viz(v: dict) -> bytes | None:
    """PNG d'un graphique préparé. `None` si le rendu échoue : un export ne
    doit jamais tomber parce qu'un graphique refuse de se compiler."""
    try:
        from app.modules.viz.render import vers_png

        return vers_png(v["vl"])
    except Exception as e:  # noqa: BLE001 — vl-convert lève des types variés
        logger.warning("Graphique non rendu à l'export DOCX : %s", str(e)[:200])
        return None


def vers_docx(report) -> bytes:
    """Rapport en `.docx` : titres, paragraphes, puces, tableaux, graphiques.

    Les graphiques passent en image PNG quand ils ont été préparés à
    l'archivage ; sinon leurs données restent, en tableau (comme au PDF) —
    perdre les chiffres serait pire que perdre la courbe.
    """
    from docx import Document
    from docx.shared import Inches

    from app.modules.viz import pipeline as viz_pipeline

    document = Document()
    document.add_heading((report.title or "Rapport").strip()[:300], level=0)

    sources = report.sources if isinstance(report.sources, list) else None
    vizs = report.viz if isinstance(report.viz, list) else None
    # Entrée abîmée (sans `index`) ignorée — même règle que `pdf.py` : pas de
    # 500 sur l'export d'une ligne mal formée.
    par_index = {v["index"]: v for v in (vizs or [])
                 if isinstance(v, dict) and v.get("index") is not None}
    if not par_index:
        # Rapport d'avant la V1 : aucun rendu archivé, on compile à la volée —
        # même moteur, même résultat que le PDF.
        par_index = {v.index: v.dict() for v in
                     viz_pipeline.extraire_et_compiler(report.content or "")}

    def tableau(cellules: list[list[str]]) -> None:
        if not cellules:
            return
        colonnes = max(len(ligne) for ligne in cellules)
        t = document.add_table(rows=0, cols=colonnes)
        t.style = "Table Grid"
        for i, ligne in enumerate(cellules):
            cases = t.add_row().cells
            for j in range(colonnes):
                valeur = _sans_gras(ligne[j]) if j < len(ligne) else ""
                cases[j].text = valeur
                if i == 0:
                    # En-tête en gras : un tableau Word sans en-tête distinct
                    # se lit comme une grille de données brutes.
                    for p in cases[j].paragraphs:
                        for r in p.runs:
                            r.bold = True

    for b in _blocs_sans_sources(report.content, sources):
        if b.genre in ("h1", "h2"):
            document.add_heading(_sans_gras(b.texte), level=1)
        elif b.genre == "h3":
            document.add_heading(_sans_gras(b.texte), level=2)
        elif b.genre == "puces":
            for ligne in b.lignes:
                document.add_paragraph(_sans_gras(ligne), style="List Bullet")
        elif b.genre == "tableau":
            tableau(b.cellules)
        elif b.genre in ("viz", "graphique"):
            v = par_index.get(b.index)
            png = _image_viz(v) if v and v.get("vl") else None
            if png:
                document.add_picture(io.BytesIO(png), width=Inches(6.0))
            else:
                if b.genre == "graphique" and b.texte:
                    document.add_heading(_sans_gras(b.texte), level=2)
                tableau(viz_pipeline.tableau_de_repli(v["spec"])
                        if v and v.get("spec")
                        else (b.cellules or [["Graphique non rendu"]]))
        elif b.genre == "hr":
            document.add_paragraph("")
        else:
            document.add_paragraph(_sans_gras(b.texte))

    if sources:
        document.add_heading("Sources", level=1)
        for n, s in enumerate(sources, start=1):
            if isinstance(s, dict):
                document.add_paragraph(_ligne_source(n, s), style="List Number")

    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()
