# Forme des rapports — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre les tableaux, relier les citations à leurs sources et ouvrir chaque rapport par une synthèse exécutive — dans l'app et dans le PDF — en réponse aux retours de Christian.

**Architecture:** Un analyseur de blocs markdown partagé côté backend (`app/modules/reports/blocs.py`) alimente le PDF ; le front étend `MarkdownView` pour les tableaux et branche `onCite` dans l'éditeur. Les sources du PDF viennent de `report.sources` (déjà numérotées 1:1 avec les `[N]` par `app/shared/grounding.py`), pas du texte du modèle.

**Tech Stack:** Python 3.12, ReportLab 4 (`Table`, `Paragraph` avec `<a href>` / `<a name>`), pytest ; React 18 (App.jsx monolithe), Next.js 14.

**Spec:** `docs/superpowers/specs/2026-09-10-forme-rapports.md`

## Global Constraints

- `render_pdf(title, markdown, sources=None)` reste compatible avec l'appel actuel à deux arguments.
- Filigrane et polices standard conservés (`_draw_watermark`, Helvetica).
- Tout changement de prompt : diff montré à Miradie **avant** déploiement (règle en mémoire `feedback_valider_contenu_produit`).
- Après tout rebuild front : `grep -c '127.0.0.1:8090' frontend/.next/static/chunks/*.js` doit valoir 0 et une inscription neuve doit passer dans le navigateur.
- Déploiement : un `scp` par fichier (le classifieur bloque les enchaînements), `systemctl restart axial-backend`, `npm run build`, `systemctl restart axial-frontend`.

---

### Task 1: Analyseur de blocs markdown (backend, pur)

**Files:**
- Create: `app/modules/reports/blocs.py`
- Test: `tests/test_blocs_markdown.py`

**Interfaces:**
- Produces: `decouper(markdown: str) -> list[Bloc]` où `Bloc` est une dataclass `(genre: str, texte: str = "", lignes: list[str] = [], cellules: list[list[str]] = [])` avec `genre ∈ {"h1","h2","h3","p","puces","tableau","hr"}`. Utilisé par la Task 2 (PDF).

- [ ] **Step 1: Écrire le test qui échoue**

```python
# tests/test_blocs_markdown.py
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
    # Une seule ligne « | » sans ligne d'en-tête suivante n'est pas un tableau.
    assert decouper("| pas un tableau")[0].genre == "p"
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_blocs_markdown.py -q`
Expected: FAIL — `ModuleNotFoundError: app.modules.reports.blocs`

- [ ] **Step 3: Implémentation minimale**

```python
# app/modules/reports/blocs.py
"""Découpe un markdown de rapport en blocs typés.

Un seul analyseur pour le PDF (et demain pour tout autre rendu) : la logique
« qu'est-ce qu'un tableau » ne doit pas exister deux fois.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEPARATEUR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


@dataclass
class Bloc:
    genre: str
    texte: str = ""
    lignes: list[str] = field(default_factory=list)
    cellules: list[list[str]] = field(default_factory=list)


def _cellules(ligne: str) -> list[str]:
    ligne = ligne.strip()
    if ligne.startswith("|"):
        ligne = ligne[1:]
    if ligne.endswith("|"):
        ligne = ligne[:-1]
    return [c.strip() for c in ligne.split("|")]


def decouper(markdown: str) -> list[Bloc]:
    blocs: list[Bloc] = []
    puces: list[str] = []
    lignes = (markdown or "").splitlines()

    def vider_puces() -> None:
        if puces:
            blocs.append(Bloc("puces", lignes=list(puces)))
            puces.clear()

    i = 0
    while i < len(lignes):
        ligne = lignes[i].rstrip()
        if not ligne.strip():
            vider_puces()
            i += 1
            continue
        # Tableau : une ligne « | … | » suivie d'une ligne de séparation.
        if ligne.lstrip().startswith("|") and i + 1 < len(lignes) \
                and _SEPARATEUR.match(lignes[i + 1].strip()):
            vider_puces()
            cellules = [_cellules(ligne)]
            i += 2
            while i < len(lignes) and lignes[i].lstrip().startswith("|"):
                cellules.append(_cellules(lignes[i]))
                i += 1
            blocs.append(Bloc("tableau", cellules=cellules))
            continue
        if ligne.startswith("### "):
            vider_puces(); blocs.append(Bloc("h3", texte=ligne[4:]))
        elif ligne.startswith("## "):
            vider_puces(); blocs.append(Bloc("h2", texte=ligne[3:]))
        elif ligne.startswith("# "):
            vider_puces(); blocs.append(Bloc("h1", texte=ligne[2:]))
        elif ligne.strip() in ("---", "***"):
            vider_puces(); blocs.append(Bloc("hr"))
        elif re.match(r"^\s*[-*]\s+", ligne):
            puces.append(re.sub(r"^\s*[-*]\s+", "", ligne))
        else:
            vider_puces(); blocs.append(Bloc("p", texte=ligne))
        i += 1
    vider_puces()
    return blocs
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest tests/test_blocs_markdown.py -q && .venv/bin/ruff check app tests`
Expected: `4 passed`, `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add app/modules/reports/blocs.py tests/test_blocs_markdown.py
git commit -m "Rapports : analyseur de blocs markdown partagé (tableaux, titres, puces)"
```

---

### Task 2: Tableaux dans le PDF

**Files:**
- Modify: `app/modules/reports/pdf.py:64-114` (fonction `render_pdf`)
- Test: `tests/test_pdf_rapports.py`

**Interfaces:**
- Consumes: `decouper()` / `Bloc` de la Task 1.
- Produces: `render_pdf(title, markdown, sources=None) -> bytes` (la signature à trois arguments est posée ici ; `sources` n'est exploité qu'en Task 3).

- [ ] **Step 1: Écrire le test qui échoue**

```python
# tests/test_pdf_rapports.py
from app.modules.reports.pdf import render_pdf


def _texte(pdf: bytes) -> str:
    from pypdf import PdfReader
    import io
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)


def test_un_tableau_est_rendu_cellule_par_cellule():
    md = "## 1. Parts\n| Acteur | Part |\n|---|---|\n| Alpha | 40 % |"
    pdf = render_pdf("Test", md)
    assert pdf.startswith(b"%PDF-")
    t = _texte(pdf)
    assert "Alpha" in t and "40 %" in t
    assert "|---|" not in t  # la ligne de séparation ne fuit pas dans le document
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_pdf_rapports.py -q`
Expected: FAIL — `"|---|" in t` (les lignes brutes sont écrites telles quelles aujourd'hui)

- [ ] **Step 3: Réécrire la boucle de `render_pdf` sur les blocs**

Remplacer, dans `app/modules/reports/pdf.py`, la signature et la boucle `for raw in markdown.splitlines(): …` par :

```python
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
        n = max(len(l) for l in cellules)
        # Colonnes à largeur égale : lisible sans mesurer le texte, et une
        # cellule longue se replie dans son Paragraph au lieu de déborder.
        donnees = [[Paragraph(_inline(c), cellule) for c in (l + [""] * (n - len(l)))]
                   for l in cellules]
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
        if b.genre == "h1":
            story.append(Paragraph(_inline(b.texte), h2))
        elif b.genre == "h2":
            story.append(Paragraph(_inline(b.texte), h2))
        elif b.genre == "h3":
            story.append(Paragraph(_inline(b.texte), h3))
        elif b.genre == "puces":
            story.append(ListFlowable(
                [ListItem(Paragraph(_inline(l), body), leftIndent=10) for l in b.lignes],
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
```

Supprimer l'ancienne fonction interne `flush_bullets` et l'ancienne boucle.

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest tests/test_pdf_rapports.py tests/test_veille.py -q && .venv/bin/ruff check app tests`
Expected: tous verts (`test_veille.py` contient déjà un test PDF ; il doit rester vert). Si `pypdf` manque en test : il est déjà dans `requirements.txt` (extraction des documents).

- [ ] **Step 5: Commit**

```bash
git add app/modules/reports/pdf.py tests/test_pdf_rapports.py
git commit -m "PDF : les tableaux markdown sont rendus en tables ReportLab"
```

---

### Task 3: Citations cliquables et section Sources dans le PDF

**Files:**
- Modify: `app/modules/reports/pdf.py` (fonction `_inline`, fin de `render_pdf`)
- Modify: `app/modules/reports/service.py:57-58` (`export_pdf`)
- Test: `tests/test_pdf_rapports.py`

**Interfaces:**
- Consumes: `render_pdf(title, markdown, sources)` de la Task 2 ; `report.sources` = liste de dicts `{"title","url","domain","source","excerpt"}` (forme produite par `app/shared/grounding.py`).
- Produces: `_inline(text, liens=False) -> str` ; les `[N]` deviennent `<a href="#src-N" color="#7976F7">[N]</a>` ; une section « Sources » avec ancres `<a name="src-N"/>`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_pdf_rapports.py (ajouter)
from app.modules.reports.pdf import _inline


def test_les_citations_deviennent_des_liens_internes():
    assert _inline("Le marché pèse 3 Md€ [2].", liens=True) == \
        'Le marché pèse 3 Md€ <a href="#src-2" color="#7976F7">[2]</a>.'


def test_les_citations_multiples_sont_toutes_liees():
    out = _inline("vu [1][3]", liens=True)
    assert 'href="#src-1"' in out and 'href="#src-3"' in out


def test_le_pdf_contient_une_section_sources_depuis_les_donnees():
    sources = [{"title": "Rapport Xerfi", "url": "https://xerfi.com/a", "domain": "xerfi.com",
                "source": "web", "excerpt": "…"}]
    pdf = render_pdf("T", "Un chiffre [1].", sources=sources)
    t = _texte(pdf)
    assert "Sources" in t and "Rapport Xerfi" in t and "xerfi.com" in t
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_pdf_rapports.py -q`
Expected: FAIL — `_inline() got an unexpected keyword argument 'liens'`

- [ ] **Step 3: Implémenter**

Dans `app/modules/reports/pdf.py`, remplacer `_inline` :

```python
_CITATION = re.compile(r"\[(\d+)\]")


def _inline(text: str, liens: bool = False) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    if liens:
        # Lien interne vers l'entrée de la section Sources. ReportLab résout
        # « #src-N » sur une ancre <a name="src-N"/> posée plus loin.
        text = _CITATION.sub(r'<a href="#src-\1" color="#7976F7">[\1]</a>', text)
    return text
```

Dans `render_pdf`, passer `liens=bool(sources)` à chaque `_inline(...)` du corps (titres, paragraphes, puces, cellules — pas le titre du document), puis, juste avant `doc.build(...)` :

```python
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
```

Dans `app/modules/reports/service.py`, remplacer `export_pdf` :

```python
def export_pdf(db: Session, user_id: str, report_id: str) -> bytes:
    report = get_report(db, user_id, report_id)
    # `sources` est un JSON : liste de citations, ou parfois un scalaire sur
    # d'anciens rapports restaurés — dans ce cas, pas de section Sources.
    sources = report.sources if isinstance(report.sources, list) else None
    return render_pdf(report.title, report.content, sources=sources)
```

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest tests/ -q && .venv/bin/ruff check app tests`
Expected: tout vert.

- [ ] **Step 5: Vérification manuelle du lien**

Run (local, backend non requis) :
```bash
.venv/bin/python -c "
from app.modules.reports.pdf import render_pdf
open('/tmp/essai.pdf','wb').write(render_pdf('Essai', '## 1. Marché\nLe marché pèse 3 Md€ [1].\n| A | B |\n|---|---|\n| x | 1 |', sources=[{'title':'Xerfi','url':'https://xerfi.com','domain':'xerfi.com','source':'web'}]))"
open /tmp/essai.pdf
```
Expected: `[1]` en violet, cliquable, saute à la ligne « [1] Xerfi — xerfi.com — https://xerfi.com » ; le tableau a un en-tête grisé.

- [ ] **Step 6: Commit**

```bash
git add app/modules/reports/pdf.py app/modules/reports/service.py tests/test_pdf_rapports.py
git commit -m "PDF : citations [N] liées à une section Sources générée depuis les données du rapport"
```

---

### Task 4: Synthèse exécutive en tête de chaque rapport (contenu produit — validation requise)

**Files:**
- Modify: `app/modules/analysis/prompts.py:40-48` (bloc `STYLE DE RÉDACTION`)
- Test: `tests/test_analysis.py`

**Interfaces:**
- Produces: la constante de style contient la règle 7 ; aucun changement de signature.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# tests/test_analysis.py (ajouter)
from app.modules.analysis import prompts


def test_le_style_exige_une_synthese_executive_en_tete():
    assert "## Synthèse exécutive" in prompts.SYSTEM_PROMPT
    assert "## Executive summary" in prompts.SYSTEM_PROMPT
```

(Si le bloc de style est porté par une autre constante que `SYSTEM_PROMPT`, viser celle qui contient « STYLE DE RÉDACTION » : `grep -n "STYLE DE RÉDACTION" app/modules/analysis/prompts.py`.)

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_analysis.py -q -k synthese`
Expected: FAIL

- [ ] **Step 3: Ajouter la règle 7 — puis STOP : montrer le diff à Miradie**

Après la règle 6, ajouter :

```
7. Le rapport s'ouvre par « ## Synthèse exécutive » (« ## Executive summary »
   si le rapport est en anglais) : 5 à 8 phrases, les chiffres clés et la
   conclusion principale, lisibles sans le reste du document. Cette section
   précède la section 1 et ne contient ni puce ni tableau.
```

Puis :
```bash
git diff app/modules/analysis/prompts.py
```
Envoyer ce diff à Miradie et **attendre son accord** avant tout déploiement de ce fichier. Les tâches 1 à 3 peuvent être déployées sans attendre.

- [ ] **Step 4: Vérifier le succès**

Run: `.venv/bin/pytest tests/ -q && .venv/bin/ruff check app tests`
Expected: tout vert.

- [ ] **Step 5: Commit (local ; déploiement conditionné à l'accord)**

```bash
git add app/modules/analysis/prompts.py tests/test_analysis.py
git commit -m "Prompts : synthèse exécutive obligatoire en tête de chaque rapport"
```

---

### Task 5: Tableaux et citations cliquables dans l'app

**Files:**
- Modify: `frontend/app/_prototype/App.jsx:3351-3376` (`MarkdownView`)
- Modify: `frontend/app/_prototype/App.jsx:~3468-3485` (`ReportsEditor` : `<MarkdownView text={content} />` et la liste `sources.map`)
- Modify: `frontend/app/globals.css` (styles `.md-table`)

**Interfaces:**
- Consumes: `renderInline(text, kp, onCite)` existant.
- Produces: `MarkdownView` rend `<table className="md-table">` pour un bloc `|…|` ; `ReportsEditor` passe `onCite={(n) => …scrollIntoView}` et chaque source porte `id={'src-' + (i + 1)}`.

- [ ] **Step 1: Ajouter la détection de tableau dans `MarkdownView`**

Dans la boucle `lines.forEach((raw, idx) => { … })`, la boucle ligne à ligne ne permet pas de regarder la ligne suivante ; la remplacer par une boucle indexée. Nouveau corps de `MarkdownView` :

```jsx
function MarkdownView({ text, onCite }) {
  const lines = (text || '').split('\n');
  const blocks = [];
  let bullets = [];
  const flush = (k) => {
    if (bullets.length) {
      blocks.push(
        <ul key={'ul' + k} style={{ margin: '6px 0 6px 20px', display: 'flex', flexDirection: 'column', gap: 5 }}>
          {bullets.map((b, i) => <li key={i} style={{ lineHeight: 1.55 }}>{renderInline(b, 'l' + k + i, onCite)}</li>)}
        </ul>,
      );
      bullets = [];
    }
  };
  const isSep = (l) => /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$/.test((l || '').trim());
  const cells = (l) => {
    let s = l.trim();
    if (s.startsWith('|')) s = s.slice(1);
    if (s.endsWith('|')) s = s.slice(0, -1);
    return s.split('|').map((c) => c.trim());
  };
  let idx = 0;
  while (idx < lines.length) {
    const line = lines[idx].replace(/\s+$/, '');
    if (!line.trim()) { flush(idx); idx += 1; continue; }
    // Tableau : ligne « | … | » suivie d'une ligne de séparation « |---|---| ».
    if (line.trim().startsWith('|') && isSep(lines[idx + 1])) {
      flush(idx);
      const head = cells(line);
      const rows = [];
      idx += 2;
      while (idx < lines.length && lines[idx].trim().startsWith('|')) { rows.push(cells(lines[idx])); idx += 1; }
      blocks.push(
        <div key={'t' + idx} className="md-table-wrap">
          <table className="md-table">
            <thead><tr>{head.map((c, i) => <th key={i}>{renderInline(c, 'th' + idx + i, onCite)}</th>)}</tr></thead>
            <tbody>{rows.map((r, ri) => (
              <tr key={ri}>{head.map((_, ci) => <td key={ci}>{renderInline(r[ci] || '', 'td' + idx + ri + ci, onCite)}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (line.startsWith('### ')) { flush(idx); blocks.push(<h3 key={idx} style={{ fontSize: 15, fontWeight: 700, margin: '14px 0 6px' }}>{renderInline(line.slice(4), 'h' + idx, onCite)}</h3>); }
    else if (line.startsWith('## ')) { flush(idx); blocks.push(<h2 key={idx} style={{ fontSize: 17, fontWeight: 700, margin: '18px 0 8px' }}>{renderInline(line.slice(3), 'h' + idx, onCite)}</h2>); }
    else if (line.startsWith('# ')) { flush(idx); blocks.push(<h1 key={idx} style={{ fontSize: 20, fontWeight: 800, margin: '8px 0 10px' }}>{renderInline(line.slice(2), 'h' + idx, onCite)}</h1>); }
    else if (line.trim() === '---' || line.trim() === '***') { flush(idx); blocks.push(<hr key={idx} style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '16px 0' }} />); }
    else if (/^\s*[-*]\s+/.test(line)) { bullets.push(line.replace(/^\s*[-*]\s+/, '')); }
    else { flush(idx); blocks.push(<p key={idx} style={{ margin: '6px 0', lineHeight: 1.6 }}>{renderInline(line, 'p' + idx, onCite)}</p>); }
    idx += 1;
  }
  flush('end');
  return <div>{blocks}</div>;
}
```

- [ ] **Step 2: Styles**

Ajouter à `frontend/app/globals.css`, après la règle `.conv-item-meta` :

```css
/* Tableaux markdown des rapports et des réponses */
.md-table-wrap { overflow-x: auto; margin: 10px 0 14px; border: 1px solid var(--border); border-radius: 8px; }
.md-table { border-collapse: collapse; width: 100%; font-size: 13px; background: var(--surface-2); }
.md-table th { text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase;
               letter-spacing: .05em; color: var(--fg-3); border-bottom: 1px solid var(--v-soft); white-space: nowrap; }
.md-table td { padding: 7px 10px; border-bottom: 1px solid var(--border); vertical-align: top; line-height: 1.45; }
.md-table tr:last-child td { border-bottom: 0; }
```

- [ ] **Step 3: Relier les citations dans l'éditeur de rapport**

Dans `ReportsEditor`, remplacer `<MarkdownView text={content} />` par :

```jsx
<MarkdownView text={content}
  onCite={(n) => { const el = document.getElementById('src-' + n); if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.classList.add('src-flash'); setTimeout(() => el.classList.remove('src-flash'), 1200); } }} />
```

Dans la liste `sources.map((s, i) => (…))` du même composant, ajouter `id={'src-' + (i + 1)}` sur l'élément racine de chaque source. Ajouter le style :

```css
.src-flash { outline: 2px solid var(--v-bright); outline-offset: 2px; border-radius: 6px; transition: outline-color .6s; }
```

- [ ] **Step 4: Vérifier à l'écran**

Run (local) : `cd frontend && npm run build` puis lancer le front sur 3005 (`npm run start -- -p 3005`) et le backend sur 8090 (`doppler run -- .venv/bin/uvicorn app.main:app --port 8090`). Ouvrir un rapport archivé qui contient un tableau (ex. l'étude de marché de `s.gorjux@skyted.io` du 26/08).
Expected : le tableau est une vraie table avec en-tête ; un clic sur `[3]` fait défiler jusqu'à la source 3, encadrée une seconde. Aucune erreur console. Vérifier aussi un message de chat : le rendu des puces et titres est inchangé.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/_prototype/App.jsx frontend/app/globals.css
git commit -m "App : tableaux markdown rendus, citations cliquables dans l'éditeur de rapport"
```

---

### Task 6 (option, réserve assumée): Graphique en barres sous un tableau numérique du PDF

**Files:**
- Modify: `app/modules/reports/blocs.py` (fonction `serie_numerique`)
- Modify: `app/modules/reports/pdf.py` (après `story.append(tableau(...))`)
- Test: `tests/test_blocs_markdown.py`

**Interfaces:**
- Produces: `serie_numerique(cellules) -> tuple[list[str], list[float], str] | None` : étiquettes (1re colonne), valeurs (2e colonne), unité ; `None` si le tableau n'est pas homogène.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_blocs_markdown.py (ajouter)
from app.modules.reports.blocs import serie_numerique


def test_une_serie_homogene_est_reconnue():
    c = [["Acteur", "Part"], ["Alpha", "40 %"], ["Beta", "25,5 %"]]
    assert serie_numerique(c) == (["Alpha", "Beta"], [40.0, 25.5], "%")


def test_des_unites_melangees_ne_donnent_pas_de_graphique():
    c = [["Pays", "Taille"], ["FR", "3 Md€"], ["DE", "40 %"]]
    assert serie_numerique(c) is None


def test_un_tableau_textuel_ne_donne_pas_de_graphique():
    c = [["Acteur", "Positionnement"], ["Alpha", "Premium"], ["Beta", "Low cost"]]
    assert serie_numerique(c) is None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `.venv/bin/pytest tests/test_blocs_markdown.py -q -k serie`
Expected: FAIL — `ImportError: serie_numerique`

- [ ] **Step 3: Implémenter**

```python
# app/modules/reports/blocs.py (ajouter)
_NOMBRE = re.compile(r"^\s*([-+]?\d[\d\s ]*(?:[.,]\d+)?)\s*(%|Md€|M€|k€|€|M\$|\$|k)?\s*$")


def serie_numerique(cellules: list[list[str]]):
    """Étiquettes + valeurs + unité, si et seulement si la 2e colonne est
    entièrement numérique et de même unité. Un graphique tracé sur des
    unités mélangées mentirait : mieux vaut aucun graphique."""
    if len(cellules) < 3 or any(len(l) < 2 for l in cellules):
        return None
    etiquettes, valeurs, unites = [], [], set()
    for l in cellules[1:]:
        m = _NOMBRE.match(l[1])
        if not m:
            return None
        brut = m.group(1).replace(" ", "").replace(" ", "").replace(",", ".")
        valeurs.append(float(brut))
        unites.add(m.group(2) or "")
        etiquettes.append(l[0])
    if len(unites) != 1:
        return None
    return etiquettes, valeurs, unites.pop()
```

Dans `render_pdf`, après `story.append(tableau(b.cellules))` :

```python
            serie = serie_numerique(b.cellules)
            if serie and len(serie[0]) <= 12:
                story.append(graphique(*serie))
```

et la fonction locale, à côté de `tableau` :

```python
    def graphique(etiquettes, valeurs, unite):
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.graphics.shapes import Drawing, String
        d = Drawing(A4[0] - 4 * cm, 150)
        bc = VerticalBarChart()
        bc.x, bc.y, bc.width, bc.height = 30, 25, d.width - 40, 100
        bc.data = [valeurs]
        bc.categoryAxis.categoryNames = [e[:18] for e in etiquettes]
        bc.categoryAxis.labels.fontSize = 7
        bc.valueAxis.labels.fontSize = 7
        bc.valueAxis.valueMin = 0
        bc.bars[0].fillColor = colors.HexColor("#7976F7")
        d.add(bc)
        if unite:
            d.add(String(0, 135, unite, fontSize=8, fillColor=colors.HexColor("#555")))
        return d
```

Importer `serie_numerique` avec `decouper`.

- [ ] **Step 4: Vérifier**

Run: `.venv/bin/pytest tests/ -q && .venv/bin/ruff check app tests`, puis rejouer la commande de la Task 3 Step 5 avec un tableau à valeurs numériques homogènes.
Expected: un graphique en barres sous le tableau, aucun sur un tableau textuel.

- [ ] **Step 5: Commit**

```bash
git add app/modules/reports/blocs.py app/modules/reports/pdf.py tests/test_blocs_markdown.py
git commit -m "PDF : graphique en barres sous les tableaux numériques homogènes"
```

---

### Task 7: Déploiement et preuve sur un vrai rapport

**Files:** aucun nouveau.

- [ ] **Step 1: Déployer le backend** (un `scp` par fichier)

```bash
scp app/modules/reports/blocs.py hostinger:/opt/axial-intelligence/app/modules/reports/blocs.py
scp app/modules/reports/pdf.py hostinger:/opt/axial-intelligence/app/modules/reports/pdf.py
scp app/modules/reports/service.py hostinger:/opt/axial-intelligence/app/modules/reports/service.py
scp tests/test_blocs_markdown.py hostinger:/opt/axial-intelligence/tests/test_blocs_markdown.py
scp tests/test_pdf_rapports.py hostinger:/opt/axial-intelligence/tests/test_pdf_rapports.py
ssh hostinger "cd /opt/axial-intelligence && PYTHONPATH=. doppler run --config prd -- .venv/bin/python -m pytest tests/ -q | tail -1 && systemctl restart axial-backend"
```
`prompts.py` ne part **que** si Miradie a validé le diff de la Task 4.

- [ ] **Step 2: Déployer le front**

```bash
scp frontend/app/_prototype/App.jsx hostinger:/opt/axial-intelligence/frontend/app/_prototype/App.jsx
scp frontend/app/globals.css hostinger:/opt/axial-intelligence/frontend/app/globals.css
ssh hostinger "cd /opt/axial-intelligence/frontend && npm run build 2>&1 | grep -E '✓ Compiled|rror' && systemctl restart axial-frontend && grep -c '127.0.0.1:8090' .next/static/chunks/*.js"
```
Expected : `✓ Compiled successfully`, puis `0` sur chaque chunk.

- [ ] **Step 3: Preuve**

Depuis un compte de contrôle (`…@axial-qa.fr`, à mettre en `email_suppressions`) : ouvrir l'étude de marché archivée, vérifier tableau + clic `[N]` ; télécharger le PDF, vérifier tableau, lien `[N]` → section Sources, URL cliquable. Joindre le PDF au message de retour à Christian.

- [ ] **Step 4: Snapshot**

Compléter `memory/` avec la date, ce qui est déployé, et ce qui attend la validation de prompt.
