import io

from app.modules.reports.pdf import render_pdf


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
