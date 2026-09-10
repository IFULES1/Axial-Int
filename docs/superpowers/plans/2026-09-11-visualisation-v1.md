# Visualisation intelligente V1 — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Le modèle décrit une visualisation en JSON contraint (`VizSpec`) ; du code déterministe choisit le graphique, le compile en Vega-Lite et le rend côté serveur pour les rapports (app + PDF), le chat en flux, les agents et l'email de veille.

**Architecture:** Nouveau module `app/modules/viz/` (schéma → règles → sélecteur → insight → registre → rendu `vl-convert`). Un bloc fencé ```viz dans le markdown est le seul point de contact avec le modèle. Les rendus sont adressés par empreinte SHA-256 du spec compilé (`viz_rendus`), ce qui sert à la fois le cache, l'endpoint image et l'email.

**Tech Stack:** Python 3.12, pydantic 2, `vl-convert-python` ≥ 1.7, ReportLab 4, SQLAlchemy 2 + Alembic, FastAPI ; React 18 (App.jsx), Next 14.

**Spec:** `docs/superpowers/specs/2026-09-10-visualisation-intelligente.md`

## Global Constraints

- Le LLM n'écrit jamais de Vega-Lite ni de code : uniquement `VizSpec` v1 (spec § 8).
- Une spec invalide ou qui ne compile pas → **tableau de repli**, jamais d'exception vers l'utilisateur ; statut journalisé `repli_tableau:<raison>`.
- `render_pdf(title, markdown, sources=None, vizs=None)` reste compatible avec les appels existants.
- Design system = `app/modules/viz/theme.py` uniquement (spec § 6).
- Tout changement de prompt : `git diff` montré à Miradie **avant** `scp` du fichier.
- Déploiement : un `scp` par fichier ; `alembic upgrade head` puis vérifier `alembic current` **et** la présence des colonnes ; `systemctl restart axial-backend` ; `npm run build` + `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` = 0 ; `systemctl restart axial-frontend`.
- Tests : `.venv/bin/pytest tests/ -q` vert et `.venv/bin/ruff check app tests` propre à chaque tâche.

---

### Task 1: Schéma, sélecteur, insight, thème, registre, rendu (module `viz`)

**Files:**
- Create: `app/modules/viz/__init__.py` (vide), `schema.py`, `selector.py`, `insight.py`, `theme.py`, `registry.py`, `render.py`
- Modify: `requirements.txt` (ajouter `vl-convert-python>=1.7,<2` sous « Billing / reports »)
- Test: `tests/test_viz_core.py`

**Interfaces:**
- Produces: `VizSpec` (pydantic) ; `selector.choisir(spec) -> str | None` ; `insight.point_cle(spec) -> (label|None, annotation|None)` ; `registry.REGISTRE: dict[str, Entree]` avec `Entree.compiler(spec) -> dict` (Vega-Lite) ; `registry.catalogue_pour_prompt() -> str` ; `render.vers_svg(vl) -> str`, `render.vers_png(vl, scale=2.0) -> bytes`, `render.compile_ou_none(vl) -> str | None`, `render.empreinte(vl) -> str` (sha256 hex).

- [ ] **Step 1: Tests qui échouent**

```python
# tests/test_viz_core.py
import json
import pytest
from pydantic import ValidationError

from app.modules.viz import registry, render, selector
from app.modules.viz.insight import point_cle
from app.modules.viz.schema import VizSpec

PARTS = {"version": "1", "intent": "domination", "title": "Parts de marché 2026", "unit": "%",
         "series": [{"label": "Alpha Audit", "value": 41}, {"label": "BetaCheck", "value": 25},
                    {"label": "Gamma Ctrl", "value": 14}, {"label": "Autres", "value": 20}],
         "sources": [3, 7]}
CROISSANCE = {"version": "1", "intent": "croissance", "title": "SAM 2024-2028", "unit": "M€",
              "series": [{"label": "2024", "value": 330}, {"label": "2025", "value": 372},
                         {"label": "2026", "value": 420}, {"label": "2027", "value": 471}]}


def test_le_schema_refuse_deux_structures_de_donnees():
    with pytest.raises(ValidationError):
        VizSpec.model_validate({**PARTS, "steps": [{"label": "a", "delta": 1}, {"label": "b", "delta": 2}]})


def test_le_schema_refuse_un_highlight_inconnu():
    with pytest.raises(ValidationError):
        VizSpec.model_validate({**PARTS, "highlight": "Zeta"})


def test_domination_sur_libelles_longs_donne_bar_h():
    assert selector.choisir(VizSpec.model_validate(PARTS)) == "bar_h"


def test_croissance_sur_quatre_annees_donne_line():
    assert selector.choisir(VizSpec.model_validate(CROISSANCE)) == "line"


def test_croissance_sur_deux_points_donne_kpi():
    s = VizSpec.model_validate({**CROISSANCE, "series": CROISSANCE["series"][:2]})
    assert selector.choisir(s) == "kpi"


def test_repartition_a_100_pct_donne_donut_sinon_bar_h():
    assert selector.choisir(VizSpec.model_validate({**PARTS, "intent": "repartition"})) == "donut"
    s = {**PARTS, "intent": "repartition", "series": PARTS["series"] + [{"label": "Delta", "value": 30}]}
    assert selector.choisir(VizSpec.model_validate(s)) == "bar_h"


def test_entonnoir_donne_funnel():
    s = {"version": "1", "intent": "entonnoir", "title": "TAM SAM SOM", "unit": "M€",
         "series": [{"label": "TAM", "value": 3200}, {"label": "SAM", "value": 420}, {"label": "SOM", "value": 38}]}
    assert selector.choisir(VizSpec.model_validate(s)) == "funnel"


def test_sans_intention_reconnue_pas_de_kind():
    s = VizSpec.model_validate({**PARTS, "intent": "pont", "series": None,
                                "steps": [{"label": "Revenu", "delta": 100}, {"label": "Coûts", "delta": -60}]})
    assert selector.choisir(s) == "waterfall"


def test_insight_domination_met_le_max_en_avant():
    label, note = point_cle(VizSpec.model_validate(PARTS))
    assert label == "Alpha Audit"


def test_insight_croissance_annote_le_multiplicateur():
    label, note = point_cle(VizSpec.model_validate(CROISSANCE))
    assert label == "2027" and note.startswith("×1.4")


def test_chaque_kind_du_registre_compile_en_vegalite_valide():
    specs = {
        "bar_h": PARTS, "bar": {**PARTS, "intent": "comparaison"}, "line": CROISSANCE,
        "donut": {**PARTS, "intent": "repartition"}, "kpi": {**CROISSANCE, "series": CROISSANCE["series"][:2]},
        "funnel": {"version": "1", "intent": "entonnoir", "title": "T", "unit": "M€",
                   "series": [{"label": "TAM", "value": 3200}, {"label": "SAM", "value": 420}, {"label": "SOM", "value": 38}]},
        "scatter": {"version": "1", "intent": "positionnement", "title": "T", "unit": "",
                    "axes": {"x": "Revenu (M€)", "y": "Croissance (%)"},
                    "points": [{"label": "A", "x": 10, "y": 5}, {"label": "B", "x": 20, "y": 15},
                               {"label": "C", "x": 5, "y": 30}, {"label": "D", "x": 40, "y": 2}]},
    }
    for kind, brut in specs.items():
        vl = registry.REGISTRE[kind].compiler(VizSpec.model_validate(brut))
        assert render.compile_ou_none(vl) is not None, kind
        assert "<svg" in render.vers_svg(vl)


def test_le_png_est_un_png_et_l_empreinte_est_stable():
    vl = registry.REGISTRE["bar_h"].compiler(VizSpec.model_validate(PARTS))
    assert render.vers_png(vl)[:8] == b"\x89PNG\r\n\x1a\n"
    assert render.empreinte(vl) == render.empreinte(json.loads(json.dumps(vl)))


def test_le_catalogue_est_genere_depuis_le_registre():
    cat = registry.catalogue_pour_prompt()
    for kind in registry.REGISTRE:
        assert kind in cat
```

- [ ] **Step 2: Vérifier l'échec** — `.venv/bin/pytest tests/test_viz_core.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Écrire le module**

`schema.py`, `selector.py`, `insight.py`, `theme.py` : **reprendre tel quel le code de la spec § 11** (mêmes noms, mêmes signatures). Compléter `selector.choisir` pour que `kind` fourni et cohérent soit conservé :

```python
def choisir(spec: VizSpec) -> str | None:
    kind = _deduire(spec)          # le corps de la spec § 11, renommé
    if spec.kind and spec.kind in _COMPATIBLES.get(kind, {kind}):
        return spec.kind
    return kind

_COMPATIBLES = {"bar_h": {"bar_h", "bar"}, "bar": {"bar", "bar_h"}, "line": {"line", "area"},
                "donut": {"donut", "bar_h"}, "kpi": {"kpi"}, "funnel": {"funnel", "bar_h"},
                "scatter": {"scatter", "quadrant"}, "waterfall": {"waterfall"}}
```

`registry.py` : `Entree`, `_fmt`, `_base`, `bar_h`, `line` de la spec § 11, plus :

```python
def bar(spec):                       # vertical, ≤ 4 catégories courtes
    cle, annotation = point_cle(spec)
    values = [{"label": p.label, "value": p.value} for p in spec.series]
    vl = _base(spec)
    vl.update({"data": {"values": values}, "layer": [
        {"mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3, "width": {"band": 0.55}},
         "encoding": {"x": {"field": "label", "type": "ordinal", "title": None, "sort": None},
                      "y": {"field": "value", "type": "quantitative", "title": None, "axis": {"labelExpr": _fmt(spec.unit)}},
                      "color": {"condition": {"test": f"datum.label == {cle!r}", "value": theme.ACCENT}, "value": theme.CONTEXTE}}},
        {"mark": {"type": "text", "dy": -6, "fontSize": 9, "color": theme.TEXTE},
         "encoding": {"x": {"field": "label", "type": "ordinal", "sort": None}, "y": {"field": "value", "type": "quantitative"},
                      "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}}]})
    _annoter(vl, spec, annotation)
    return vl

def donut(spec):
    cle, _ = point_cle(spec)
    values = [{"label": p.label, "value": p.value} for p in spec.series]
    vl = _base(spec, w=520, h=220)
    vl.update({"data": {"values": values}, "layer": [
        {"mark": {"type": "arc", "innerRadius": 62, "outerRadius": 100, "padAngle": 0.01, "cornerRadius": 3},
         "encoding": {"theta": {"field": "value", "type": "quantitative", "stack": True},
                      "color": {"field": "label", "type": "nominal", "sort": "-value",
                                "legend": {"title": None, "orient": "right"},
                                "scale": {"range": [theme.ACCENT] + theme.CATEGORIES[1:]}}}},
        {"mark": {"type": "text", "radius": 82, "fontSize": 9, "color": "white", "fontWeight": "bold"},
         "encoding": {"theta": {"field": "value", "type": "quantitative", "stack": True},
                      "text": {"field": "value", "type": "quantitative", "format": ".0f"}}}]})
    return vl

def kpi(spec):                       # 1-4 chiffres, texte grand, pas d'axes
    values = [{"label": p.label, "value": p.value, "i": i} for i, p in enumerate(spec.series)]
    n = len(values); vl = _base(spec, w=520, h=110)
    vl.update({"data": {"values": values}, "layer": [
        {"mark": {"type": "text", "fontSize": 28, "fontWeight": "bold", "color": theme.ACCENT, "dy": -12},
         "encoding": {"x": {"field": "i", "type": "quantitative", "axis": None, "scale": {"domain": [-0.5, n - 0.5]}},
                      "y": {"value": 55},
                      "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
        {"mark": {"type": "text", "fontSize": 10, "color": theme.GRIS, "dy": 14},
         "encoding": {"x": {"field": "i", "type": "quantitative"}, "y": {"value": 55},
                      "text": {"field": "label", "type": "nominal"}}}]})
    if spec.unit:
        vl["title"]["subtitle"] = f"{spec.subtitle + ' — ' if spec.subtitle else ''}en {spec.unit}"
    return vl

def funnel(spec):                    # barres horizontales centrées, du plus large au plus étroit
    values = [{"label": p.label, "value": p.value, "ordre": i} for i, p in enumerate(spec.series)]
    vl = _base(spec, h=34 * len(values) + 10)
    vl.update({"data": {"values": values}, "transform": [{"calculate": "-datum.value/2", "as": "x0"}, {"calculate": "datum.value/2", "as": "x1"}],
               "layer": [
        {"mark": {"type": "bar", "cornerRadius": 3},
         "encoding": {"x": {"field": "x0", "type": "quantitative", "axis": None}, "x2": {"field": "x1"},
                      "y": {"field": "label", "type": "nominal", "sort": {"field": "ordre"}, "title": None},
                      "color": {"field": "ordre", "type": "quantitative", "legend": None,
                                "scale": {"range": [theme.CONTEXTE, theme.ACCENT]}}}},
        {"mark": {"type": "text", "fontSize": 9.5, "fontWeight": "bold", "color": theme.TEXTE},
         "encoding": {"x": {"value": 260}, "y": {"field": "label", "type": "nominal", "sort": {"field": "ordre"}},
                      "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}}]})
    _, annotation = point_cle(spec); _annoter(vl, spec, annotation)
    return vl

def scatter(spec):
    values = [{"label": p.label, "x": p.x, "y": p.y, "size": p.size or 1} for p in spec.points]
    vl = _base(spec, h=260)
    vl.update({"data": {"values": values}, "layer": [
        {"mark": {"type": "circle", "opacity": 0.85, "color": theme.ACCENT},
         "encoding": {"x": {"field": "x", "type": "quantitative", "title": spec.axes["x"]},
                      "y": {"field": "y", "type": "quantitative", "title": spec.axes["y"]},
                      "size": {"field": "size", "type": "quantitative", "legend": None, "scale": {"range": [80, 900]}}}},
        {"mark": {"type": "text", "dy": -12, "fontSize": 9, "color": theme.TEXTE},
         "encoding": {"x": {"field": "x", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"},
                      "text": {"field": "label", "type": "nominal"}}}]})
    return vl

def _annoter(vl, spec, annotation):
    if annotation:
        vl["title"]["subtitle"] = (spec.subtitle + " — " if spec.subtitle else "") + annotation

REGISTRE = {
    "kpi": Entree("kpi", "Chiffres clés", "1 à 4 valeurs qui résument", "plus de 4 valeurs", kpi),
    "bar": Entree("bar", "Barres verticales", "≤ 4 catégories courtes ou périodes", "libellés longs", bar),
    "bar_h": Entree("bar_h", "Classement horizontal", "classement, domination, libellés longs", "séries temporelles", bar_h),
    "line": Entree("line", "Évolution", "≥ 3 périodes ordonnées", "catégories, < 3 points", line),
    "donut": Entree("donut", "Répartition", "parts qui totalisent 100 %, ≤ 6", "> 6 parts, valeurs proches", donut),
    "funnel": Entree("funnel", "Entonnoir", "TAM → SAM → SOM, étapes emboîtées", "étapes non emboîtées", funnel),
    "scatter": Entree("scatter", "Positionnement", "acteurs sur deux mesures", "< 4 points", scatter),
}
```

(`waterfall`, `area`, `quadrant`, `stacked_bar` : le sélecteur peut les nommer ; s'ils ne sont pas dans le registre, la pipeline retombe en tableau — V2.)

`render.py` : code de la spec § 11 plus `def empreinte(vl) -> str: return _cle(vl)`.

- [ ] **Step 4: Installer, tester, lint** — `.venv/bin/pip install "vl-convert-python>=1.7,<2"` ; `.venv/bin/pytest tests/test_viz_core.py -q` → tous verts ; `.venv/bin/ruff check app tests`.

- [ ] **Step 5: Commit** — `git add app/modules/viz tests/test_viz_core.py requirements.txt && git commit -m "Viz : schéma VizSpec, sélecteur, insight, registre Vega-Lite et rendu vl-convert"`

---

### Task 2: Bloc ```viz dans l'analyseur et pipeline d'extraction

**Files:**
- Modify: `app/modules/reports/blocs.py`
- Create: `app/modules/viz/pipeline.py`
- Test: `tests/test_blocs_markdown.py`, `tests/test_viz_pipeline.py`

**Interfaces:**
- Produces: `Bloc(genre="viz", texte=<json brut>, index=<n>)` — ajouter le champ `index: int = -1` à la dataclass `Bloc` ; `pipeline.extraire_et_compiler(markdown) -> list[Viz]` (dataclass `Viz(index, spec, kind, vl, statut, empreinte)`) ; `pipeline.tableau_de_repli(spec) -> list[list[str]]` ; `pipeline.depuis_graphique(titre, cellules) -> VizSpec | None` (compatibilité « Graphique : »).

- [ ] **Step 1: Tests**

```python
# tests/test_blocs_markdown.py (ajouter)
def test_un_bloc_viz_est_un_bloc_typé_avec_son_index():
    md = "## 1\n```viz\n{\"a\": 1}\n```\ntexte\n```viz\n{\"b\": 2}\n```"
    vizs = [b for b in decouper(md) if b.genre == "viz"]
    assert [b.index for b in vizs] == [0, 1] and vizs[0].texte == '{"a": 1}'
```

```python
# tests/test_viz_pipeline.py
from app.modules.viz.pipeline import depuis_graphique, extraire_et_compiler, tableau_de_repli

BON = '```viz\n{"version":"1","intent":"domination","title":"Parts","unit":"%","series":[{"label":"A","value":60},{"label":"B","value":40}],"sources":[1]}\n```'


def test_un_bloc_valide_est_compile():
    v = extraire_et_compiler("intro\n" + BON)[0]
    assert v.statut == "ok" and v.kind == "bar_h" and v.vl["data"]["values"][0]["label"] == "A"
    assert len(v.empreinte) == 64


def test_un_json_casse_retombe_en_tableau():
    v = extraire_et_compiler("```viz\n{pas du json\n```")[0]
    assert v.statut.startswith("repli_tableau:schema") and v.vl is None


def test_le_tableau_de_repli_garde_les_donnees():
    v = extraire_et_compiler(BON)[0]
    assert tableau_de_repli(v.spec) == [["", "%"], ["A", "60"], ["B", "40"]]


def test_graphique_ancienne_marque_devient_un_spec():
    s = depuis_graphique("Parts 2026", [["Acteur", "Part"], ["A", "60 %"], ["B", "40 %"]])
    assert s and s.intent == "comparaison" and s.unit == "%" and s.series[0].value == 60


def test_graphique_ancienne_marque_heterogene_donne_none():
    assert depuis_graphique("X", [["a", "b"], ["A", "3 Md€"], ["B", "40 %"]]) is None
```

- [ ] **Step 2: Vérifier l'échec** — `pytest tests/test_viz_pipeline.py tests/test_blocs_markdown.py -q`.

- [ ] **Step 3: Implémenter**

`blocs.py` : ajouter `index: int = -1` à `Bloc` ; dans `decouper`, avant la détection de tableau :

```python
        if ligne.strip().startswith("```viz"):
            vider_puces()
            j = i + 1
            contenu = []
            while j < len(lignes) and not lignes[j].strip().startswith("```"):
                contenu.append(lignes[j]); j += 1
            blocs.append(Bloc("viz", texte="\n".join(contenu).strip(), index=compteur_viz))
            compteur_viz += 1
            i = j + 1
            continue
```
(`compteur_viz = 0` initialisé en tête de `decouper`.)

`pipeline.py` : code de la spec § 11 (`Viz`, `extraire_et_compiler`, `tableau_de_repli`) avec `empreinte = render.empreinte(vl) if vl else ""` dans `Viz`, plus :

```python
def depuis_graphique(titre: str, cellules: list[list[str]]) -> VizSpec | None:
    """Compatibilité avec la marque « Graphique : » des rapports du 10/09."""
    from app.modules.reports.blocs import serie_numerique
    s = serie_numerique(cellules)
    if not s:
        return None
    etiquettes, valeurs, unite = s
    try:
        return VizSpec(intent="comparaison", title=titre[:80], unit=unite[:8],
                       series=[{"label": e[:60], "value": v} for e, v in zip(etiquettes, valeurs)])
    except ValidationError:
        return None
```

et dans `extraire_et_compiler`, après les blocs ```viz, parcourir `decouper(markdown)` pour convertir les blocs `graphique` (index continus après les ```viz) — de sorte que `Viz.index` corresponde à l'ordre d'apparition **tous types confondus**. Pour rester simple : indexer par ordre d'apparition dans `decouper` ; le bloc `graphique` reçoit lui aussi un `index` (même compteur).

- [ ] **Step 4: Tests + lint + commit** — `git commit -m "Viz : bloc \`\`\`viz dans l'analyseur, pipeline d'extraction et compatibilité Graphique :"`

---

### Task 3: Persistance, endpoints image, archivage rapports et messages

**Files:**
- Create: `alembic/versions/0021_viz.py`, `app/modules/viz/models.py`, `app/modules/viz/router.py`, `app/modules/viz/service.py`
- Modify: `app/modules/reports/models.py` (colonne `viz`), `app/modules/intelligence/models.py` (colonne `viz` sur `Message`), `app/modules/analysis/service.py` (`finalize`), `app/modules/intelligence/service.py` (`_finalize_turn`), `app/main.py`, `alembic/env.py` (import `viz.models`)
- Test: `tests/test_viz_service.py`

**Interfaces:**
- Produces: table `viz_rendus(empreinte text pk, vl jsonb, created_at)` ; colonnes `reports.viz jsonb`, `messages.viz jsonb` (liste de `Viz` sérialisés) ; `service.preparer(db, markdown) -> list[dict]` (extrait, compile, enregistre les rendus, renvoie la liste à stocker) ; `GET /viz/{empreinte}.svg` et `GET /viz/{empreinte}.png` (**publics** : l'empreinte de 64 hex est le secret ; en-tête `Cache-Control: public, max-age=31536000, immutable`) ; `POST /viz/rendu` (auth) : body `VizSpec` → `{empreinte, kind, statut, svg}`.

- [ ] **Step 1: Test**

```python
# tests/test_viz_service.py
from app.modules.viz import service

def test_preparer_renvoie_une_liste_serialisable(db_session):   # fixture SQLite du projet (voir tests/test_wiring.py)
    md = "```viz\n{\"version\":\"1\",\"intent\":\"domination\",\"title\":\"P\",\"unit\":\"%\",\"series\":[{\"label\":\"A\",\"value\":60},{\"label\":\"B\",\"value\":40}]}\n```"
    out = service.preparer(db_session, md)
    assert out[0]["statut"] == "ok" and out[0]["empreinte"]
    assert service.rendu_par_empreinte(db_session, out[0]["empreinte"]) is not None
```

- [ ] **Step 2: Migration**

```python
# alembic/versions/0021_viz.py
revision = "0021_viz"; down_revision = "0020_contacts"
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table("viz_rendus",
        sa.Column("empreinte", sa.String(64), primary_key=True),
        sa.Column("vl", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("reports", sa.Column("viz", sa.JSON().with_variant(postgresql.JSONB(), "postgresql")))
    op.add_column("messages", sa.Column("viz", sa.JSON().with_variant(postgresql.JSONB(), "postgresql")))

def downgrade():
    op.drop_column("messages", "viz"); op.drop_column("reports", "viz"); op.drop_table("viz_rendus")
```

- [ ] **Step 3: Modèle, service, router**

```python
# app/modules/viz/models.py
class VizRendu(Base):
    __tablename__ = "viz_rendus"
    empreinte: Mapped[str] = mapped_column(String(64), primary_key=True)
    vl: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

```python
# app/modules/viz/service.py
def preparer(db, markdown: str) -> list[dict]:
    sortie = []
    for v in pipeline.extraire_et_compiler(markdown):
        if v.vl and db.get(VizRendu, v.empreinte) is None:
            db.add(VizRendu(empreinte=v.empreinte, vl=v.vl))
        sortie.append(asdict(v))
    db.flush()
    return sortie

def rendu_par_empreinte(db, empreinte: str) -> dict | None:
    r = db.get(VizRendu, empreinte)
    return r.vl if r else None
```

```python
# app/modules/viz/router.py
router = APIRouter(prefix="/viz", tags=["viz"])
_IMMUABLE = {"Cache-Control": "public, max-age=31536000, immutable"}

@router.get("/{empreinte}.svg")
def svg(empreinte: str, db: Session = Depends(get_db)):
    vl = service.rendu_par_empreinte(db, empreinte)
    if not vl: raise AppError("Graphique introuvable.", 404, code="not_found")
    return Response(render.vers_svg(vl), media_type="image/svg+xml", headers=_IMMUABLE)

@router.get("/{empreinte}.png")
def png(empreinte: str, db: Session = Depends(get_db)):
    vl = service.rendu_par_empreinte(db, empreinte)
    if not vl: raise AppError("Graphique introuvable.", 404, code="not_found")
    return Response(render.vers_png(vl), media_type="image/png", headers=_IMMUABLE)

@router.post("/rendu")
def rendu(spec: VizSpec, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Chat en flux : le navigateur envoie le bloc dès qu'il est fermé."""
    md = "```viz\n" + spec.model_dump_json() + "\n```"
    v = service.preparer(db, md)[0]; db.commit()
    return {"empreinte": v["empreinte"], "kind": v["kind"], "statut": v["statut"],
            "svg": render.vers_svg(v["vl"]) if v["vl"] else None,
            "tableau": pipeline.tableau_de_repli(v["spec"]) if not v["vl"] else None}
```

Monter dans `main.py` (`from app.modules.viz.router import router as viz_router` + `app.include_router(viz_router)`), importer `app.modules.viz.models` dans `alembic/env.py`.

`analysis/service.finalize` : après la création du `Report`, `report.viz = viz_service.preparer(db, res.content)` (dans le même `try` que l'archivage ; une erreur ici ne doit pas empêcher la facturation : `except Exception: logger.exception(...)`).

`intelligence/service._finalize_turn` : idem, `assistant_msg.viz = viz_service.preparer(db, answer)`.

Exposer `viz` dans `ReportDetail` (reports/router.py) et dans la sortie des messages (intelligence/router.py, `MessageOut`).

- [ ] **Step 4: Tests + lint + migration locale** — `.venv/bin/alembic upgrade head` (Postgres local) ; `alembic current` = `0021_viz` ; `pytest -q`.

- [ ] **Step 5: Commit** — `git commit -m "Viz : rendus par empreinte, colonnes reports.viz et messages.viz, endpoints image et rendu à la volée"`

---

### Task 4: PDF

**Files:**
- Modify: `app/modules/reports/pdf.py`, `app/modules/reports/service.py` (`export_pdf` passe `report.viz`)
- Test: `tests/test_pdf_rapports.py`

**Interfaces:**
- Consumes: `render.vers_png`, `pipeline.tableau_de_repli`, `Bloc(genre="viz"|"graphique", index)`.
- Produces: `render_pdf(title, markdown, sources=None, vizs=None)` ; `vizs` = liste de dicts (forme `Viz`) indexée par `index`.

- [ ] **Step 1: Tests**

```python
def test_un_bloc_viz_compile_devient_une_image_dans_le_pdf():
    from app.modules.viz.pipeline import extraire_et_compiler
    from dataclasses import asdict
    md = "## 1. Parts\n```viz\n{\"version\":\"1\",\"intent\":\"domination\",\"title\":\"Parts de marché\",\"unit\":\"%\",\"series\":[{\"label\":\"A\",\"value\":60},{\"label\":\"B\",\"value\":40}],\"sources\":[1]}\n```"
    vizs = [asdict(v) for v in extraire_et_compiler(md)]
    pdf = render_pdf("T", md, sources=[{"title": "S", "url": "https://s.fr", "domain": "s.fr", "source": "web"}], vizs=vizs)
    assert b"/Image" in pdf or b"/XObject" in pdf          # une image est embarquée
    t = _texte(pdf); assert "version" not in t             # le JSON brut n'apparaît jamais

def test_un_bloc_viz_invalide_devient_un_tableau():
    md = "```viz\n{\"version\":\"1\",\"intent\":\"domination\",\"title\":\"P\",\"unit\":\"%\",\"series\":[{\"label\":\"A\",\"value\":60},{\"label\":\"B\",\"value\":40}],\"highlight\":\"Zeta\"}\n```"
    from app.modules.viz.pipeline import extraire_et_compiler
    from dataclasses import asdict
    vizs = [asdict(v) for v in extraire_et_compiler(md)]
    t = _texte(render_pdf("T", md, vizs=vizs))
    assert "A" in t and "60" in t and "version" not in t
```

- [ ] **Step 2: Implémenter** — dans `render_pdf` : nouveau paramètre `vizs=None` ; `par_index = {v["index"]: v for v in (vizs or [])}` ; branche :

```python
        elif b.genre in ("viz", "graphique"):
            v = par_index.get(b.index)
            if b.genre == "graphique" and v is None:            # rapports d'avant la V1
                spec = depuis_graphique(b.texte, b.cellules)
                v = _compiler_a_la_volee(spec) if spec else None
            if v and v.get("vl"):
                png = ImageReader(io.BytesIO(vers_png(v["vl"])))
                largeur = A4[0] - 4 * cm
                hauteur = largeur * v["vl"]["height"] / v["vl"]["width"]
                elements = [Image(png, width=largeur, height=hauteur)]
                if v["spec"].get("sources"):
                    elements.append(Paragraph("Source : " + ", ".join(
                        f'<a href="#src-{n}" color="#7976F7">[{n}]</a>' for n in v["spec"]["sources"]), petit))
                story.append(KeepTogether(elements)); story.append(Spacer(1, 8))
            else:
                cellules = tableau_de_repli(v["spec"]) if v else b.cellules
                if b.texte and b.genre == "graphique":
                    story.append(Paragraph(_inline(b.texte, liens), h3))
                story.append(tableau(cellules, liens)); story.append(Spacer(1, 8))
```

Supprimer `graphique()` (ReportLab) et la branche `serie_numerique` de `pdf.py` ; `petit` défini avant la boucle. `export_pdf` : `render_pdf(report.title, report.content, sources=sources, vizs=report.viz)`.

- [ ] **Step 3: Tests + lint + commit** — `git commit -m "PDF : les blocs viz sont rendus en image Vega-Lite, repli tableau, ancien graphique ReportLab retiré"`

---

### Task 5: App — rapports, chat en flux, agents

**Files:**
- Modify: `frontend/app/_prototype/bridge.js` (`axRenduViz(spec)`), `frontend/app/_prototype/App.jsx` (`MarkdownView`, `ReportsEditor`, `sendStreamed`), `frontend/app/globals.css`

**Interfaces:**
- Consumes: `POST /viz/rendu`, `GET /viz/{empreinte}.svg`, `report.viz[]`, `message.viz[]`.
- Produces: `MarkdownView({ text, onCite, vizs, live })` ; composant `VizFigure({ viz, brut, live })`.

- [ ] **Step 1: `bridge.js`** — `export async function axRenduViz(spec) { return axFetch("/viz/rendu", { method: "POST", body: spec }); }` ; ajouter à l'import de `App.jsx`.

- [ ] **Step 2: `MarkdownView`** — dans la boucle indexée, avant la détection de tableau :

```jsx
if (line.trim().startsWith('```viz')) {
  flush(idx);
  let j = idx + 1; const corps = [];
  while (j < lines.length && !lines[j].trim().startsWith('```')) { corps.push(lines[j]); j += 1; }
  const ferme = j < lines.length;
  const k = vizIndex++;
  blocks.push(<VizFigure key={'v' + k} viz={(vizs || [])[k]} brut={corps.join('\n')} ferme={ferme} live={live} />);
  idx = ferme ? j + 1 : j;
  continue;
}
```
(`let vizIndex = 0` au début de `MarkdownView` ; le bloc `graphique` d'ancienne marque : rendre `VizFigure` aussi si `vizs[k]` existe, sinon le tableau comme aujourd'hui.)

- [ ] **Step 3: `VizFigure`**

```jsx
function VizFigure({ viz, brut, ferme, live }) {
  const [etat, setEtat] = React.useState(viz ? { statut: viz.statut, empreinte: viz.empreinte, tableau: null } : null);
  React.useEffect(() => {
    if (viz || !ferme || live) return;          // archivé : image directe ; flux : attendre la fermeture et la fin
    let spec; try { spec = JSON.parse(brut); } catch (e) { setEtat({ statut: 'repli' }); return; }
    axRenduViz(spec).then((r) => setEtat({ statut: r.statut, empreinte: r.empreinte, svg: r.svg, tableau: r.tableau }))
                    .catch(() => setEtat({ statut: 'repli' }));
  }, [viz, brut, ferme, live]);
  if (!ferme || (live && !etat)) return <div className="viz-attente">{libelle('Graphique en préparation…')}</div>;
  if (!etat) return <div className="viz-attente">…</div>;
  if (etat.statut === 'ok' && etat.empreinte) {
    return <figure className="viz"><img src={`${AX_API}/viz/${etat.empreinte}.svg`} alt="" /></figure>;
  }
  const t = etat.tableau || (viz && viz.spec && viz.spec.series
    ? [['', viz.spec.unit || '']].concat(viz.spec.series.map((p) => [p.label, String(p.value)])) : null);
  return t ? (
    <div className="md-table-wrap"><table className="md-table">
      <thead><tr>{t[0].map((c, i) => <th key={i}>{c}</th>)}</tr></thead>
      <tbody>{t.slice(1).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
    </table></div>) : null;
}
```

`ReportsEditor` : `<MarkdownView text={content} vizs={report.viz} onCite=… />`. Chat : la bulle assistant passe `vizs={m.viz}` et `live={m.live}` ; pendant le flux `live` est vrai → « en préparation » ; à la réception du message final (`final.viz` renvoyé par `/messages/stream` avec `done`), le rendu part. Historique rechargé : `mapBackendMsg` reprend `viz: m.viz`.

- [ ] **Step 4: CSS**

```css
figure.viz { margin: 12px 0 16px; padding: 12px 12px 8px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface-2); }
figure.viz img { display: block; width: 100%; height: auto; }
.viz-attente { margin: 12px 0; padding: 18px; border: 1px dashed var(--border); border-radius: 8px; color: var(--fg-3); font-size: 12.5px; text-align: center; }
```

- [ ] **Step 5: Build local** — `cd frontend && npm run build` → `✓ Compiled successfully`.

- [ ] **Step 6: Commit** — `git commit -m "App : figures viz dans les rapports et le chat en flux, repli tableau"`

---

### Task 6: Email de veille avec graphiques

**Files:**
- Modify: `app/modules/watches/email.py` (`_md_to_html`, `_send_via_resend`), `app/modules/watches/service.py` (préparer les viz du rapport de veille avant l'envoi)

**Interfaces:**
- Consumes: `service.preparer`, URL publique `https://app.axial-ia.fr/api/viz/{empreinte}.png`.

- [ ] **Step 1: Implémenter** — dans `_md_to_html`, remplacer chaque bloc ```viz par `<img src="https://app.axial-ia.fr/api/viz/{empreinte}.png" width="560" alt="{title}">` quand le rendu existe (les `Viz` préparés sont passés à `_md_to_html(md, vizs)`), sinon par un tableau HTML de repli. Dans `run_watch`, appeler `viz_service.preparer(db, texte)` avant `send_email`. Un client mail charge une image hébergée ; il n'exécute jamais de script — c'est la seule forme qui passe.

- [ ] **Step 2: Test** — `tests/test_veille.py` : `_md_to_html` avec un bloc viz + `vizs=[{index:0, statut:'ok', empreinte:'a'*64, spec:{title:'P'}}]` contient `<img src="https://app.axial-ia.fr/api/viz/aaaa…png"` et ne contient pas `version`.

- [ ] **Step 3: Commit** — `git commit -m "Veille : les graphiques du rapport sont intégrés à l'email en image"`

---

### Task 7: Prompt (validation obligatoire avant déploiement)

**Files:**
- Modify: `app/modules/analysis/prompts.py` (règle 5, partie graphique), `app/modules/intelligence/personas.py` (consigne chat)
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Test** — `assert "```viz" in prompts.OUTPUT_STYLE and "Graphique :" not in prompts.OUTPUT_STYLE` ; `assert "intent" in prompts.OUTPUT_STYLE`.

- [ ] **Step 2: Règle 5** — remplacer le paragraphe « Choisir la forme la plus parlante … » par le texte de la spec § 9, en injectant `{catalogue}` via `registry.catalogue_pour_prompt()` au moment de construire le prompt (pas de f-string au niveau module : ajouter une fonction `style_de_redaction()` appelée là où `OUTPUT_STYLE` est assemblé). Personas : ajouter une phrase après `AXIAL_RECOMMENDE_INSTRUCTION` : « Si ta réponse compare, classe, répartit ou fait évoluer des chiffres, ajoute un bloc ```viz (même format que les rapports) — sinon aucun. »

- [ ] **Step 3: STOP — `git diff app/modules/analysis/prompts.py app/modules/intelligence/personas.py`** montré à Miradie. Déploiement de ces deux fichiers **uniquement** après son accord.

- [ ] **Step 4: Commit local** — `git commit -m "Prompts : bloc viz à la place de la marque Graphique, consigne chat"`

---

### Task 8: Déploiement et preuves

- [ ] **Step 1: Backend** — `scp` (un par fichier) : `requirements.txt`, `app/modules/viz/*`, `blocs.py`, `pdf.py`, `reports/service.py`, `reports/models.py`, `reports/router.py`, `intelligence/models.py`, `intelligence/service.py`, `intelligence/router.py`, `analysis/service.py`, `watches/email.py`, `watches/service.py`, `main.py`, `alembic/env.py`, `alembic/versions/0021_viz.py`, tests. Puis :
```bash
ssh hostinger "cd /opt/axial-intelligence && .venv/bin/pip install -q 'vl-convert-python>=1.7,<2' && PYTHONPATH=. doppler run --config prd -- .venv/bin/alembic upgrade head && PYTHONPATH=. doppler run --config prd -- .venv/bin/alembic current && PYTHONPATH=. doppler run --config prd -- .venv/bin/python -c \"from sqlalchemy import text; from app.db import SessionLocal; db=SessionLocal(); print([r[0] for r in db.execute(text(\\\"SELECT column_name FROM information_schema.columns WHERE table_name IN ('reports','messages') AND column_name='viz'\\\")).all()])\" && PYTHONPATH=. doppler run --config prd -- .venv/bin/python -m pytest tests/ -q | tail -1 && systemctl restart axial-backend axial-worker"
```
Attendu : `0021_viz (head)`, `['viz', 'viz']`, tests verts.

- [ ] **Step 2: Front** — `scp` `App.jsx`, `bridge.js`, `globals.css` ; `npm run build` ; `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` = 0 ; `systemctl restart axial-frontend`.

- [ ] **Step 3: Prompts** — après accord : `scp prompts.py personas.py` ; `systemctl restart axial-backend axial-worker`.

- [ ] **Step 4: Preuves** — (a) rapport de contrôle réel (script du 10/09 adapté) : compter les blocs ```viz, leurs statuts, ouvrir le PDF ; (b) question de chat comparative depuis le compte de contrôle dans le navigateur : « compare les parts de marché des trois leaders » → figure affichée après le flux ; (c) `POST /watches/{id}/run` sur une veille de contrôle avec `email_recipients` = adresse de test → email reçu avec image ; (d) `SELECT statut, count(*) FROM (SELECT jsonb_array_elements(viz)->>'statut' statut FROM reports WHERE viz IS NOT NULL) s GROUP BY 1` pour le taux de repli.

- [ ] **Step 5: Snapshot + push** — compléter `memory/`, `git push origin main`.
