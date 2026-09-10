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


def _inline(text: str) -> str:
    text = html.escape(text)
    # **bold** → <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return text


def render_pdf(title: str, markdown: str, sources: list[dict] | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    from app.modules.reports.blocs import decouper

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

    def tableau(cellules: list[list[str]]):
        largeur = A4[0] - 4 * cm
        n = max(len(ligne) for ligne in cellules)
        # Colonnes à largeur égale : lisible sans mesurer le texte, et une
        # cellule longue se replie dans son Paragraph au lieu de déborder.
        donnees = [[Paragraph(_inline(c), cellule) for c in (ligne + [""] * (n - len(ligne)))]
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

    for b in decouper(markdown):
        if b.genre in ("h1", "h2"):
            story.append(Paragraph(_inline(b.texte), h2))
        elif b.genre == "h3":
            story.append(Paragraph(_inline(b.texte), h3))
        elif b.genre == "puces":
            story.append(ListFlowable(
                [ListItem(Paragraph(_inline(ligne), body), leftIndent=10) for ligne in b.lignes],
                bulletType="bullet", start="•"))
        elif b.genre == "tableau":
            story.append(tableau(b.cellules))
            story.append(Spacer(1, 8))
        elif b.genre == "hr":
            story.append(Spacer(1, 10))
        else:
            story.append(Paragraph(_inline(b.texte), body))

    doc.build(story, onFirstPage=_draw_watermark, onLaterPages=_draw_watermark)
    return buffer.getvalue()
