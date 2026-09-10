"""Markdown → PDF export via ReportLab.

Deliberately lightweight: headings (#, ##, ###), bold (**), bullet lists, and
paragraphs. Produces a clean A4 report as bytes. If the Axial watermark asset is
present it is drawn faintly behind every page; otherwise export proceeds without it.
"""
from __future__ import annotations

import functools
import html
import io
import logging
import re
from pathlib import Path

logger = logging.getLogger("axial.reports.pdf")

# app/modules/reports/pdf.py → app/assets/branding/watermark-axial.png
_WATERMARK_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "branding" / "watermark-axial.png"
_WATERMARK_OPACITY = 0.12


@functools.lru_cache(maxsize=1)
def _watermark_reader():
    """Load the brand watermark, fade it to a light 'grammage', cache the result.
    Returns None (no watermark) when the asset or Pillow is unavailable."""
    if not _WATERMARK_PATH.exists():
        return None
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader

        img = Image.open(_WATERMARK_PATH).convert("RGBA")
        faded = img.split()[3].point(lambda a: int(a * _WATERMARK_OPACITY))
        img.putalpha(faded)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception:
        logger.warning("Watermark load failed; exporting without it", exc_info=True)
        return None


def _draw_watermark(canvas, doc) -> None:
    reader = _watermark_reader()
    if reader is None:
        return
    from reportlab.lib.pagesizes import A4

    w, h = A4
    canvas.saveState()
    canvas.drawImage(reader, 0, 0, width=w, height=h, mask="auto", preserveAspectRatio=False)
    canvas.restoreState()


_CITATION = re.compile(r"\[(\d+)\]")
# « Sources », « 8. Sources », « Sources et références », « References »…
_TITRE_SOURCES = re.compile(r"^\s*(\d+[.)]\s*)?(sources?|r[ée]f[ée]rences?)\b", re.IGNORECASE)


def _inline(text: str, liens: bool = False) -> str:
    text = html.escape(text)
    # **bold** → <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    if liens:
        # Lien interne vers l'entrée de la section Sources. ReportLab résout
        # « #src-N » sur une ancre <a name="src-N"/> posée plus loin.
        text = _CITATION.sub(r'<a href="#src-\1" color="#7976F7">[\1]</a>', text)
    return text


def render_pdf(title: str, markdown: str, sources: list[dict] | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    from app.modules.reports.blocs import decouper, serie_numerique

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm, title=title)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, spaceBefore=10, spaceAfter=6)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=12, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10.5, leading=15,
                          alignment=TA_LEFT, spaceAfter=6)
    cellule = ParagraphStyle("Cellule", parent=body, fontSize=9, leading=12, spaceAfter=0)

    story: list = [Paragraph(_inline(title), h1), Spacer(1, 6)]

    def tableau(cellules: list[list[str]], liens: bool = False):
        largeur = A4[0] - 4 * cm
        n = max(len(ligne) for ligne in cellules)
        # Colonnes à largeur égale : lisible sans mesurer le texte, et une
        # cellule longue se replie dans son Paragraph au lieu de déborder.
        donnees = [[Paragraph(_inline(c, liens), cellule)
                    for c in (ligne + [""] * (n - len(ligne)))]
                   for ligne in cellules]
        t = Table(donnees, colWidths=[largeur / n] * n, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECEAFB")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#7976F7")),
            ("GRID", (0, 1), (-1, -1), 0.25, colors.HexColor("#D9D7E8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    def graphique(etiquettes, valeurs, unite, titre=""):
        # Le graphique remplace le tableau : chaque barre porte donc sa valeur
        # en clair, pour que rien ne se perde par rapport aux chiffres.
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.graphics.shapes import Drawing, String

        d = Drawing(A4[0] - 4 * cm, 190)
        bc = VerticalBarChart()
        bc.x, bc.y, bc.width, bc.height = 30, 30, d.width - 40, 115
        bc.data = [valeurs]
        bc.categoryAxis.categoryNames = [e[:22] for e in etiquettes]
        bc.categoryAxis.labels.fontSize = 7
        bc.categoryAxis.labels.angle = 0 if len(etiquettes) <= 6 else 20
        bc.valueAxis.labels.fontSize = 7
        bc.valueAxis.valueMin = 0
        bc.bars[0].fillColor = colors.HexColor("#7976F7")
        bc.barLabelFormat = (lambda v: f"{v:g} {unite}".strip())
        bc.barLabels.fontSize = 7
        bc.barLabels.nudge = 6
        d.add(bc)
        if titre:
            d.add(String(0, 172, titre[:90], fontSize=9, fontName="Helvetica-Bold",
                         fillColor=colors.HexColor("#222222")))
        if unite:
            d.add(String(d.width - 30, 172, unite, fontSize=8, fillColor=colors.HexColor("#555555")))
        return d

    # Les [N] ne deviennent des liens que si une section Sources existe pour
    # les recevoir : un lien vers une ancre absente est pire qu'un [N] inerte.
    liens = bool(sources)

    # Le modèle rédige lui-même une section « Sources » en texte (règle 6 du
    # prompt). Quand on en génère une depuis les données — avec ancres et URL
    # cliquables — la sienne ferait doublon : on l'écarte jusqu'au prochain titre.
    blocs = decouper(markdown)
    if sources:
        garder, sauter = [], False
        for b in blocs:
            if b.genre in ("h1", "h2"):
                sauter = bool(_TITRE_SOURCES.match(b.texte))
            if not sauter:
                garder.append(b)
        blocs = garder

    for b in blocs:
        if b.genre in ("h1", "h2"):
            story.append(Paragraph(_inline(b.texte, liens), h2))
        elif b.genre == "h3":
            story.append(Paragraph(_inline(b.texte, liens), h3))
        elif b.genre == "puces":
            story.append(ListFlowable(
                [ListItem(Paragraph(_inline(ligne, liens), body), leftIndent=10)
                 for ligne in b.lignes],
                bulletType="bullet", start="•"))
        elif b.genre == "tableau":
            story.append(tableau(b.cellules, liens))
            story.append(Spacer(1, 8))
        elif b.genre == "graphique":
            # Le modèle a demandé un graphique. On ne le trace que si les
            # données s'y prêtent (deux colonnes, une unité) ; sinon le tableau
            # reste, avec son titre — mieux qu'un graphique faux.
            serie = serie_numerique(b.cellules)
            if serie and len(serie[0]) <= 12:
                story.append(graphique(*serie, titre=b.texte))
            else:
                story.append(Paragraph(_inline(b.texte, liens), h3))
                story.append(tableau(b.cellules, liens))
            story.append(Spacer(1, 8))
        elif b.genre == "hr":
            story.append(Spacer(1, 10))
        else:
            story.append(Paragraph(_inline(b.texte, liens), body))

    if sources:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Sources", h2))
        petit = ParagraphStyle("Src", parent=body, fontSize=9, leading=12, spaceAfter=3)
        for n, s in enumerate(sources, start=1):
            titre = html.escape((s.get("title") or s.get("domain") or "Source").strip())
            url = (s.get("url") or "").strip()
            domaine = html.escape(s.get("domain") or "")
            ligne = f'<a name="src-{n}"/><b>[{n}]</b> {titre}'
            if domaine:
                ligne += f" — {domaine}"
            if url:
                ligne += f' — <a href="{html.escape(url)}" color="#7976F7">{html.escape(url)}</a>'
            elif s.get("source") == "notion":
                ligne += " — espace Notion"
            elif s.get("source") != "web":
                ligne += " — document interne"
            story.append(Paragraph(ligne, petit))

    doc.build(story, onFirstPage=_draw_watermark, onLaterPages=_draw_watermark)
    return buffer.getvalue()
