# Visualisation intelligente des rapports Axial — audit, verdict, architecture, V1

*10/09/2026 — Données → Analyse → Insight → Choix → Spécification JSON → Validation → Rendu*

---

## 1. Audit de l'existant (état réel du code, pas de la doc)

| Sujet | Constat |
|---|---|
| Frontend | Next.js 14.2, React 18, TypeScript minimal ; toute l'app vit dans `frontend/app/_prototype/App.jsx` (6 823 lignes) + `bridge.js` (API). **Aucune bibliothèque de graphiques.** Tailwind installé mais le design est dans `globals.css` (tokens : `--v-bright #7976F7`, `--surface-2`, `--fg-3`, JetBrains Mono / Inter). |
| Backend | FastAPI + SQLAlchemy 2 + Alembic (20 migrations), Python 3.12 sur le VPS, 3.13 en local. Modules : `analysis` (génération), `reports` (archive + PDF), `intelligence` (chat), `watches` (veille). |
| Génération | `analysis/service.run_analysis()` : recherche multi-moteurs + RAG → prompt (`prompts.py`, 421 lignes, bloc `OUTPUT_STYLE`) → `llm_client.generate(tier="report")` (Claude Sonnet 5, repli Gemini). **Sortie = markdown texte**, pas de JSON structuré. Citations `[N]` numérotées 1:1 avec `report.sources` (`app/shared/grounding.py`). |
| Format des données | Il n'y a pas de « données » séparées du texte : les chiffres vivent dans la prose et, depuis aujourd'hui, dans des tableaux markdown (règle 5) avec la marque `Graphique : <titre>` quand le modèle veut un graphique. |
| Rendu app | `MarkdownView` (React, ~60 lignes) : titres, gras, puces, tableaux (`.md-table`), citations `[N]` cliquables. |
| Rendu PDF | `reports/pdf.py` (ReportLab, 208 lignes) sur les blocs de `reports/blocs.py` (121 lignes) : tables, liens internes vers une section Sources générée, **graphique en barres ReportLab** (`reportlab.graphics`) quand un tableau est marqué — rendu correct mais rudimentaire (pas de mise en avant, libellés tronqués à 22 caractères, un seul type). |
| Archive | `reports.content` (markdown), `reports.sources` (JSONB). Pas de colonne pour des données de visualisation. |
| Chat | Même `MarkdownView` ; messages archivés dans `messages` avec `citations` JSONB. |
| Export | PDF uniquement (`GET /reports/{id}/pdf`). Pas de HTML export, pas de PowerPoint. |
| Contrainte dure | **Le PDF est produit côté serveur, en Python, sans navigateur.** Toute bibliothèque qui exige un navigateur pour exporter une image (ECharts, Plotly/Kaleido, D3) casse le PDF ou impose un Chromium headless sur le VPS. |

**Où s'insère la couche** : exactement à la place de la marque `Graphique :` livrée ce soir. Le modèle émet déjà « un tableau + une intention » ; il suffit de remplacer ce couple par un **bloc JSON contraint** (```viz), et de faire rendre ce bloc par un seul moteur, côté serveur, pour l'app et le PDF. Rien d'autre ne bouge : `run_analysis`, `finalize`, `report.content`, `MarkdownView`, `pdf.py` sont **étendus**, pas remplacés.

---

## 2. Comparaison des bibliothèques pour CE cas

Critère décisif ajouté à ta grille : **rendu côté serveur sans navigateur** (le PDF). Notation sur 5.

| Critère (poids) | Vega-Lite | ECharts | Recharts | Plotly | D3 |
|---|---|---|---|---|---|
| Compatibilité stack (TE) | 5 — JSON pur, React via `vega-embed`, **Python via `vl-convert`** | 3 — JS ; Python via `pyecharts` mais export image = navigateur | 4 — React natif, **rien côté Python** | 3 — JS + Python, export image = Kaleido (Chromium embarqué) | 2 — code impératif |
| Génération par IA (TE) | 5 — déclaratif, grammaire stable, très présent dans les corpus | 4 — JSON d'options, très permissif (trop) | 1 — composants JSX = code | 3 — JSON volumineux | 1 — code libre |
| Spécification JSON (TE) | 5 — c'est sa nature, **JSON Schema officiel** pour valider | 4 — JSON mais sans schéma de validation | 1 | 3 | 0 |
| Types de visualisations (E) | 4 — bar/line/area/scatter/arc/heatmap/waterfall/funnel par composition ; pas de Sankey natif | 5 — tout, Sankey/treemap/gauge inclus | 3 | 4 | 5 |
| Esthétique (TE) | 4 — sobre, entièrement thémable par `config` | 4 — belle par défaut, très « dashboard » | 3 | 3 — look Plotly reconnaissable | 5 |
| Personnalisation design (TE) | 5 — un objet `config` = design system | 4 | 3 | 3 | 5 |
| Responsive (E) | 4 — `width: "container"` | 5 | 4 | 4 | 3 |
| **Export PDF / image / SVG (TE)** | **5 — SVG et PNG en Python, 0,36 s mesuré** | 2 — navigateur headless requis | 1 — DOM requis | 2 — Kaleido = Chromium | 1 |
| Performance (E) | 4 | 5 | 4 | 3 | 5 |
| Maintenance (E) | 5 — UW IDL, Altair/Observable | 5 — Apache | 4 | 4 | 5 |
| Documentation (E) | 5 | 4 | 4 | 4 | 4 |
| Intégration (E) | 5 — 1 dépendance Python, 0 dépendance front en V1 | 3 | 4 | 3 | 2 |
| Données financières (TE) | 4 — formats d'axes, waterfall, log | 4 | 3 | 4 | 5 |
| Visualisations complexes (E) | 3 — via Vega complet si besoin | 5 | 2 | 4 | 5 |
| Évolutivité (TE) | 5 — même spec du PDF au dashboard interactif | 4 | 3 | 3 | 4 |

**Pourquoi Vega-Lite gagne ici et pas ailleurs.** Dans une app « dashboard web » ECharts gagnerait. Chez Axial le livrable premier est un **document** : le PDF envoyé à un investisseur, le rapport archivé. Une bibliothèque dont la seule voie d'export est un navigateur headless ajoute un Chromium sur le VPS (600 Mo, une source de pannes de plus) pour chaque PDF. Vega-Lite, via `vl-convert` (binaire Rust embarqué dans une roue Python, aucun runtime JS), rend **le même JSON** en SVG pour le PDF et, plus tard, en graphique interactif dans l'app avec `vega-embed`. Et c'est la seule des cinq à avoir un **JSON Schema officiel** : on valide ce que le LLM produit avant de tenter de le dessiner.

**Vega-Lite vs ECharts pour « LLM → JSON → graphique »** :
- Vega-Lite : grammaire réduite (mark + encoding), le LLM ne peut pas y mettre de code ; un spec invalide échoue à la compilation, ce qui est détectable. Limite : Sankey, treemap, jauges demandent Vega complet ou une composition — hors V1.
- ECharts : l'objet `option` accepte des **fonctions JS** (formatters, callbacks) : un LLM qui génère de l'ECharts génère potentiellement du code exécuté dans le navigateur. Il faudrait un sous-ensemble maison et un validateur — c'est réinventer Vega-Lite.

**Mais le point le plus important est ailleurs : le LLM ne doit générer ni Vega-Lite ni ECharts.** Il génère **notre** schéma (`VizSpec`, 10 champs), et c'est du code déterministe qui compile en Vega-Lite. Le modèle choisit *quoi montrer* ; le code décide *comment*. C'est ce qui rend les rapports cohérents entre eux.

---

## 3. Verdict

- **Principal : Vega-Lite** — spec JSON compilée par nous, rendue par `vl-convert` côté serveur (SVG/PNG), affichée dans l'app en V1 comme image SVG servie par l'API, en V2 par `vega-embed` (interactif, même spec).
- **Alternative** : Apache ECharts, uniquement si la V3 « dashboard interactif temps réel » devient le produit principal et que le PDF passe au second plan. On garderait alors `VizSpec` et on écrirait un second compilateur ; rien en amont ne change.
- **Écarté** : Recharts (pas de spec, pas de serveur), Plotly (Chromium), D3 (code libre = interdit par principe ici).

---

## 4. Architecture

```
                 ┌──────────────────────────────────────────────────────────┐
                 │ LLM (Claude Sonnet 5 / Gemini)  — écrit le rapport        │
                 │ markdown + blocs ```viz {VizSpec JSON}```                 │
                 └───────────────┬──────────────────────────────────────────┘
                                 │ texte
 run_analysis ──► finalize ──►  app/modules/viz/pipeline.extraire_et_compiler()
                                 │
        ┌────────────────────────┼────────────────────────────────────┐
        │ 1. extraction  blocs ```viz  (reports/blocs.py)             │ déterministe
        │ 2. validation  VizSpec (pydantic) + règles métier            │ déterministe
        │ 3. sélection   kind absent/incohérent → selector.choisir()  │ déterministe
        │ 4. insight     highlight absent → insight.detecter()        │ déterministe
        │ 5. compilation registry[kind].compiler(spec) → Vega-Lite   │ déterministe
        │ 6. validation  vl_convert compile (erreur = repli tableau)  │ déterministe
        │ 7. stockage    reports.viz = [{index, spec, vl, statut}]    │
        └────────────────────────┬────────────────────────────────────┘
                                 │
              ┌──────────────────┴───────────────────┐
              ▼                                      ▼
   PDF (reports/pdf.py)                    App (MarkdownView)
   vl_convert → PNG ×2 → ReportLab Image   <img src="/api/reports/{id}/viz/{i}.svg">   (V1)
   + titre, insight, source [N]            vega-embed sur reports.viz[i].vl            (V2)
```

**Qui fait quoi.**
- **LLM** : décide *qu'une* visualisation est pertinente, choisit l'*intention* (`intent`), fournit les *données* (déjà dans son texte), le *titre*, la *source* `[N]`, et éventuellement le `kind` et le point à mettre en avant. Il ne voit jamais Vega-Lite.
- **Déterministe** : tout le reste. Le sélecteur peut *contredire* le `kind` du modèle (un donut à 11 parts devient un bar_h ; une « croissance » sur 2 points devient un KPI).
- **Templates** : `app/modules/viz/registry.py` — un dict `kind → Entrée(description, use_when, avoid_when, champs, compiler)`. Versionné par `VizSpec.version` ("1") ; un rapport archivé garde son spec, on recompile à la volée avec le registre courant (le rendu s'améliore rétroactivement, les données ne bougent pas).
- **Validation** : pydantic (types, bornes) → règles (`regles.py` : 2 ≤ points ≤ 12 ; unité unique ; pas de NaN ; `line` exige ≥ 3 périodes ordonnées ; `donut` exige somme ≈ 100 % ou parts ≤ 6 ; `scatter` exige 2 mesures et ≥ 4 points) → compilation Vega-Lite réelle (`vl_convert.vegalite_to_svg` dans un try).
- **Incohérence** : jamais d'exception vers l'utilisateur. Un bloc invalide est rendu en **tableau** (les données sont là) avec une note interne ; le statut est journalisé (`viz.statut = "repli_tableau"`) pour mesurer le taux d'échec du modèle.
- **Données manquantes** : `null` interdit dans `value` ; une série avec un trou est refusée pour `line` (repli tableau) et acceptée pour `bar` sans la barre manquante, annotée « n.d. ».
- **Nouveaux types** : une entrée de plus dans le registre + un test = disponible dans le prompt (le catalogue envoyé au modèle est généré depuis le registre, jamais écrit à la main).

---

## 5. Registre de visualisations (V1 en gras, V2/V3 ensuite)

| kind | Quand | Éviter quand | Données requises | Complexité | Intérêt IE |
|---|---|---|---|---|---|
| **kpi** | 1 à 3 chiffres qui résument (TAM, croissance, part du leader) | plus de 4 valeurs | `series` 1-4 `{label, value}` + `unit` | faible | très élevé |
| **bar** | comparer ≤ 8 catégories, ordre imposé (années, tailles) | classement long, libellés longs | `series` 2-8, unité unique | faible | élevé |
| **bar_h** | classement, libellés longs (noms d'acteurs) | données temporelles | `series` 2-12, trié par le compilateur | faible | très élevé |
| **line** | évolution, ≥ 3 périodes, tendance | < 3 points, catégories non ordonnées | `series` 3-20 `{label=période, value}` | faible | très élevé |
| **area** | cumul, volume dans le temps | plusieurs séries qui se croisent | comme line | faible | moyen |
| **donut** | répartition qui totalise 100 %, ≤ 6 parts | > 6 parts, valeurs proches | `series` 2-6, `unit="%"` | faible | élevé (parts) |
| **stacked_bar** | composition par catégorie (mix par segment) | > 5 composantes | `groups` : catégorie × composante | moyen | élevé |
| **scatter** | positionner des acteurs sur 2 mesures (taille × croissance) | < 4 points | `points` `{label, x, y, size?}` + `axes` | moyen | très élevé |
| **quadrant** | matrice 2×2 stratégique (attractivité × capacité) | mesures non normalisables | `points` + seuils | moyen | très élevé |
| **funnel** | TAM → SAM → SOM, entonnoir de conversion | étapes non emboîtées | `series` 3-6 décroissantes | faible | très élevé |
| **waterfall** | pont d'un total à un autre (revenu → marge) | > 8 marches | `steps` `{label, delta}` + total | moyen | élevé (finance) |
| heatmap (V2) | matrice risque × probabilité, benchmark critères × acteurs | > 12×12 | `grid` | moyen | élevé |
| timeline (V2) | jalons réglementaires, roadmap | > 15 jalons | `events` `{date, label}` | moyen | élevé (réglementaire) |
| treemap, sankey (V3) | flux, hiérarchies | — | — | élevée | moyen |

Composants stratégiques non graphiques (V2) : `risk_card`, `opportunity_card`, `benchmark_card`, `recommendation` — ce sont des blocs markdown typés, pas des graphiques ; même mécanique de bloc fencé, autre rendu.

---

## 6. Design system des visualisations (un seul objet `config`, partagé app + PDF)

- **Typographie** : Helvetica dans le PDF (polices standard ReportLab), Inter dans l'app ; titre 13 gras ancré à gauche ; sous-titre insight 10,5 gris `#555` ; libellés 9,5 ; valeurs sur barres 9.
- **Couleurs** : accent `#7976F7` (une seule valeur mise en avant), contexte `#C9C7E8` (tout le reste, désaturé), alerte `#E5484D` (risque, baisse), texte `#222`, grille `#E4E2F0` pointillée. Palette catégorielle (stacked, scatter) : 5 teintes dérivées de l'accent, jamais plus.
- **Axes** : unité dans les libellés (`40 %`, `3,2 Md€`), jamais dans le titre ; pas de bordure de vue ; grille horizontale seule ; origine à zéro pour les barres.
- **Mise en avant automatique** : le compilateur calcule le point clé selon l'`intent` (domination → max ; croissance → dernier point + pente ; rupture → écart max entre deux points ; concentration → cumul des 3 premiers) et l'annote en texte sur le graphique.
- **Cartouche** : titre → graphique → une ligne d'insight (`subtitle`, 1 phrase, écrite par le modèle, vérifiée ≤ 140 caractères) → « Source : [N] » en 8,5 gris. Le tout dans une carte à bord `1px #E4E2F0`, rayon 8, dans l'app ; dans le PDF, un `KeepTogether` pour ne jamais couper titre/graphique.
- **Tailles** : PDF 520 × 220 pt (pleine largeur A4 moins marges), PNG rendu ×2 ; app `width: container`, hauteur 240.
- **Cohérence** : un rapport = mêmes couleurs, même ordre (leader en haut), même format de nombres (`fr-FR`, espace insécable, une décimale max).
- **Responsive** : dans l'app, SVG avec `viewBox` → s'adapte ; en V2, `vega-embed` recalcule.

---

## 7. Sélection automatique — la logique

Entrées : `nature` (déduite des données : `temporel` si les libellés sont des années/trimestres/mois ordonnés ; `categoriel` sinon ; `bidim` si `points`), `n` (nombre de points), `unit`, `intent` (donné par le modèle, parmi 11 valeurs), `kind` (optionnel).

```
si kind fourni et regles(kind, données) OK        → kind
sinon :
  intent ∈ {croissance, evolution, projection, rupture}
      nature temporel, n ≥ 3                        → line   (area si intent=cumul)
      n < 3                                         → kpi
  intent ∈ {domination, classement, comparaison}
      n ≤ 4, libellés courts                        → bar
      sinon                                         → bar_h
  intent = repartition
      unit = "%" et n ≤ 6 et somme ∈ [95, 105]      → donut
      sinon                                         → bar_h
  intent = concentration                            → bar_h (annotation cumul top 3)
  intent = entonnoir                                → funnel
  intent ∈ {positionnement, correlation}, points    → scatter (quadrant si seuils fournis)
  intent = pont                                     → waterfall
  intent = risque / opportunite                     → kpi (valeur + tendance) — carte en V2
  aucun intent reconnu                              → tableau (pas de graphique)
```

Exemples : `2022→100 … 2025→250` + intent croissance → **line**, insight « ×2,5 en trois ans » annoté. `A 42 %, B 27 %, C 18 %, D 13 %` + intent domination → **bar_h**, A en accent. Même données + intent repartition → **donut** (somme 100, 4 parts). `Company, Revenue, Growth` → **scatter** (x = revenu, y = croissance, taille = revenu).

---

## 8. Schéma JSON (`VizSpec` v1) — ce que le LLM écrit

```json
{
  "version": "1",
  "intent": "domination",
  "kind": "bar_h",
  "title": "Parts de marché 2026",
  "subtitle": "Alpha Audit détient 41 % du marché, plus que ses deux suivants réunis.",
  "unit": "%",
  "series": [
    {"label": "Alpha Audit", "value": 41},
    {"label": "BetaCheck", "value": 25},
    {"label": "Gamma Ctrl", "value": 14},
    {"label": "Autres", "value": 20}
  ],
  "highlight": "Alpha Audit",
  "sources": [3, 7]
}
```

Champs : `version` (const "1") · `intent` (enum 11) · `kind` (enum registre, optionnel) · `title` (≤ 80) · `subtitle` (≤ 140, optionnel) · `unit` (string court, `""` autorisé) · **une seule** structure de données parmi `series` (label/value), `points` (label/x/y/size?) avec `axes` {x, y}, `groups` (categorie → {composante: valeur}), `steps` (label/delta) · `highlight` (label, optionnel) · `sources` (liste d'entiers = citations `[N]`) · `note` (≤ 200, optionnel).

Le schéma pydantic est dans le code (§ 10). Le JSON Schema équivalent est généré par `VizSpec.model_json_schema()` et versionné dans `docs/viz/vizspec-v1.schema.json`.

---

## 9. Prompt — ce qui remplace la ligne « Graphique : »

Ajout au bloc `OUTPUT_STYLE`, règle 5 (partie graphique) :

```
Quand une COMPARAISON, une RÉPARTITION, une ÉVOLUTION ou un POSITIONNEMENT se
lit mieux d'un coup d'œil qu'en tableau, écris à la place du tableau un bloc :

```viz
{"version":"1","intent":"<domination|classement|comparaison|repartition|
concentration|croissance|evolution|projection|rupture|entonnoir|positionnement|
pont>","title":"<titre court>","subtitle":"<l'insight en une phrase>",
"unit":"<% | M€ | Md€ | k | ''>","series":[{"label":"…","value":<nombre>}],
"highlight":"<label du point clé, optionnel>","sources":[<N>, …]}
```

Règles : nombres sans unité ni séparateur de milliers dans "value" ; une seule
unité par bloc ; 2 à 12 points ; les mêmes chiffres doivent apparaître dans le
texte avec leurs citations ; "sources" reprend ces citations. Ne choisis pas le
type de graphique : l'application le déduit de "intent" et des données. Un
tableau reste un tableau quand plusieurs colonnes ou une lecture ligne à ligne
sont nécessaires. Jamais un ```viz et un tableau pour la même donnée.
Catalogue des intentions :
{CATALOGUE_GENERE_DEPUIS_LE_REGISTRE}
```

Le catalogue (une ligne par `intent` : quand l'utiliser, quand l'éviter, exemple) est **généré** depuis `registry.py` à chaque construction du prompt, jamais recopié.

---

## 10. Plan d'intégration, dans l'ordre (V1 — 5 tâches, ~1,5 jour)

1. **`app/modules/viz/`** (nouveau) : `schema.py` (pydantic `VizSpec`), `regles.py`, `selector.py`, `insight.py`, `registry.py` (compilateurs Vega-Lite : kpi, bar, bar_h, line, donut, funnel, scatter), `theme.py` (config), `render.py` (`vers_svg`, `vers_png` via `vl_convert`, cache LRU par hash du spec), `pipeline.py` (`extraire_et_compiler(markdown) -> list[Viz]`). Tests unitaires sur chaque brique (sélecteur, règles, compilateur → spec valide compilée par vl-convert).
2. **`reports/blocs.py`** : bloc fencé ```viz → `Bloc("viz", texte=json)` ; la marque `Graphique :` reste supportée et est **convertie** en VizSpec (`intent=comparaison`, `series` depuis le tableau) — compatibilité avec les rapports d'aujourd'hui.
3. **Migration 0021** : `reports.viz JSONB` (liste `{index, spec, vl, statut}`) ; `analysis/service.finalize()` appelle `pipeline` et remplit la colonne. Endpoint `GET /reports/{id}/viz/{index}.svg` (auth, cache).
4. **PDF** : `pdf.py` rend `Bloc("viz")` en `Image(PNG ×2)` dans un `KeepTogether` avec titre, insight, source. Le graphique ReportLab actuel est supprimé (remplacé, pas conservé en double).
5. **App** : `MarkdownView` rend ```viz → `<figure class="viz"><img src=/api/reports/{id}/viz/{i}.svg>` + légende ; pour le chat (pas de `report_id`), `POST /viz/render` (spec → SVG) — V1 ne l'active que dans les rapports.
6. **Prompt** : règle 5 mise à jour (diff à valider) ; `Graphique :` retiré du prompt mais toujours accepté par le code.
7. **Preuve** : rapport de contrôle réel + PDF ; mesure du taux `repli_tableau`.

Dépendances : `vl-convert-python>=1.7` (backend, roue Linux vérifiée) ; **aucune** côté front en V1.

---

## 11. Code V1 (extraits complets des briques centrales)

### `app/modules/viz/schema.py`
```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Intent = Literal["domination", "classement", "comparaison", "repartition", "concentration",
                 "croissance", "evolution", "projection", "rupture", "entonnoir",
                 "positionnement", "pont"]
Kind = Literal["kpi", "bar", "bar_h", "line", "area", "donut", "stacked_bar",
               "scatter", "quadrant", "funnel", "waterfall"]

class Point1(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    value: float

class Point2(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    x: float
    y: float
    size: float | None = None

class Step(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    delta: float

class VizSpec(BaseModel):
    version: Literal["1"] = "1"
    intent: Intent
    kind: Kind | None = None
    title: str = Field(min_length=3, max_length=80)
    subtitle: str | None = Field(default=None, max_length=140)
    unit: str = Field(default="", max_length=8)
    series: list[Point1] | None = Field(default=None, min_length=2, max_length=20)
    points: list[Point2] | None = Field(default=None, min_length=4, max_length=40)
    axes: dict[str, str] | None = None          # {"x": "Revenu (M€)", "y": "Croissance (%)"}
    steps: list[Step] | None = Field(default=None, min_length=2, max_length=8)
    highlight: str | None = None
    sources: list[int] = Field(default_factory=list, max_length=8)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _une_seule_structure(self):
        n = sum(x is not None for x in (self.series, self.points, self.steps))
        if n != 1:
            raise ValueError("exactement une structure de données : series, points ou steps")
        if self.points is not None and not (self.axes and "x" in self.axes and "y" in self.axes):
            raise ValueError("points exige axes.x et axes.y")
        if self.highlight and self.series and self.highlight not in {p.label for p in self.series}:
            raise ValueError("highlight doit être un label de series")
        return self
```

### `app/modules/viz/selector.py`
```python
from __future__ import annotations
import re
from app.modules.viz.schema import VizSpec

_PERIODE = re.compile(r"^(19|20)\d{2}(\s*[-/]\s*(T|Q|S)?\d)?$|^(T|Q)[1-4]\s*(19|20)\d{2}$", re.I)

def nature(spec: VizSpec) -> str:
    if spec.points is not None:
        return "bidim"
    if spec.steps is not None:
        return "pont"
    labels = [p.label.strip() for p in spec.series]
    return "temporel" if all(_PERIODE.match(l) for l in labels) else "categoriel"

def choisir(spec: VizSpec) -> str | None:
    """Le kind final. None = pas de graphique (repli tableau)."""
    nat, n = nature(spec), len(spec.series or spec.points or spec.steps)
    if nat == "bidim":
        return "quadrant" if spec.intent == "positionnement" and spec.note and "seuil" in spec.note else "scatter"
    if nat == "pont":
        return "waterfall"
    if spec.intent in ("croissance", "evolution", "projection", "rupture"):
        return "line" if (nat == "temporel" and n >= 3) else "kpi" if n <= 4 else "bar"
    if spec.intent == "entonnoir":
        return "funnel" if 3 <= n <= 6 else "bar_h"
    if spec.intent == "repartition":
        total = sum(p.value for p in spec.series)
        return "donut" if (spec.unit == "%" and n <= 6 and 95 <= total <= 105) else "bar_h"
    if spec.intent in ("domination", "classement", "comparaison", "concentration"):
        court = all(len(p.label) <= 12 for p in spec.series)
        return "bar" if (n <= 4 and court and nat == "temporel") else "bar_h"
    return None
```

### `app/modules/viz/insight.py`
```python
from __future__ import annotations
from app.modules.viz.schema import VizSpec

def point_cle(spec: VizSpec) -> tuple[str | None, str | None]:
    """(label à mettre en avant, annotation) selon l'intention. Déterministe."""
    if spec.highlight:
        return spec.highlight, None
    s = spec.series or []
    if not s:
        return None, None
    if spec.intent in ("domination", "classement", "comparaison", "concentration", "repartition"):
        top = max(s, key=lambda p: p.value)
        if spec.intent == "concentration":
            cumul = sum(sorted((p.value for p in s), reverse=True)[:3])
            return top.label, f"Top 3 = {cumul:g} {spec.unit}".strip()
        return top.label, None
    if spec.intent in ("croissance", "evolution", "projection"):
        a, b = s[0].value, s[-1].value
        if a > 0:
            return s[-1].label, f"×{b / a:.1f} entre {s[0].label} et {s[-1].label}"
        return s[-1].label, None
    if spec.intent == "rupture":
        i = max(range(1, len(s)), key=lambda k: abs(s[k].value - s[k - 1].value))
        return s[i].label, f"{s[i].value - s[i-1].value:+g} {spec.unit} en {s[i].label}".strip()
    if spec.intent == "entonnoir":
        return s[-1].label, f"{100 * s[-1].value / s[0].value:.0f} % du sommet" if s[0].value else None
    return None, None
```

### `app/modules/viz/theme.py`
```python
ACCENT, CONTEXTE, ALERTE, TEXTE, GRIS, GRILLE = "#7976F7", "#C9C7E8", "#E5484D", "#222222", "#555555", "#E4E2F0"
CATEGORIES = ["#7976F7", "#A5A3F2", "#C9C7E8", "#5E5BD1", "#8E8CF4"]
CONFIG = {
    "background": "white",
    "font": "Helvetica",
    "view": {"stroke": None},
    "axis": {"labelFont": "Helvetica", "labelFontSize": 9.5, "labelColor": GRIS, "titleColor": GRIS,
             "titleFontSize": 9.5, "titleFontWeight": "normal", "domain": False, "tickColor": GRILLE,
             "gridColor": GRILLE, "gridDash": [2, 2]},
    "title": {"font": "Helvetica", "fontSize": 13, "fontWeight": "bold", "color": TEXTE, "anchor": "start",
              "subtitleFontSize": 10.5, "subtitleColor": GRIS, "subtitlePadding": 4},
    "legend": {"labelFontSize": 9.5, "labelColor": GRIS, "symbolType": "circle"},
    "range": {"category": CATEGORIES},
}
```

### `app/modules/viz/registry.py` (deux entrées montrées ; les autres suivent le même moule)
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from app.modules.viz import theme
from app.modules.viz.insight import point_cle
from app.modules.viz.schema import VizSpec

@dataclass(frozen=True)
class Entree:
    kind: str
    description: str
    use_when: str
    avoid_when: str
    compiler: Callable[[VizSpec], dict]

def _fmt(unit: str) -> str:
    return {"%": "datum.label + ' %'", "M€": "datum.label + ' M€'", "Md€": "datum.label + ' Md€'",
            "k": "datum.label + ' k'"}.get(unit, "datum.label")

def _base(spec: VizSpec, w=520, h=220) -> dict:
    return {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "width": w, "height": h,
            "title": {"text": spec.title, **({"subtitle": spec.subtitle} if spec.subtitle else {})},
            "config": theme.CONFIG}

def bar_h(spec: VizSpec) -> dict:
    cle, annotation = point_cle(spec)
    values = [{"label": p.label, "value": p.value} for p in spec.series]
    vl = _base(spec, h=28 * len(values) + 20)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "bar", "cornerRadiusEnd": 3},
             "encoding": {"x": {"field": "value", "type": "quantitative", "title": None,
                                "axis": {"labelExpr": _fmt(spec.unit)}},
                          "y": {"field": "label", "type": "nominal", "sort": "-x", "title": None},
                          "color": {"condition": {"test": f"datum.label == {cle!r}", "value": theme.ACCENT},
                                    "value": theme.CONTEXTE}}},
            {"mark": {"type": "text", "align": "left", "dx": 4, "fontSize": 9, "color": theme.TEXTE},
             "encoding": {"x": {"field": "value", "type": "quantitative"},
                          "y": {"field": "label", "type": "nominal", "sort": "-x"},
                          "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
        ],
    })
    if annotation:
        vl["title"]["subtitle"] = (spec.subtitle + " — " if spec.subtitle else "") + annotation
    return vl

def line(spec: VizSpec) -> dict:
    cle, annotation = point_cle(spec)
    values = [{"label": p.label, "value": p.value, "cle": p.label == cle} for p in spec.series]
    vl = _base(spec)
    vl.update({
        "data": {"values": values},
        "layer": [
            {"mark": {"type": "area", "opacity": 0.12, "color": theme.ACCENT},
             "encoding": {"x": {"field": "label", "type": "ordinal", "title": None},
                          "y": {"field": "value", "type": "quantitative", "title": None,
                                "axis": {"labelExpr": _fmt(spec.unit)}}}},
            {"mark": {"type": "line", "point": True, "color": theme.ACCENT, "strokeWidth": 2},
             "encoding": {"x": {"field": "label", "type": "ordinal"},
                          "y": {"field": "value", "type": "quantitative"}}},
            {"mark": {"type": "text", "dy": -10, "fontSize": 9.5, "fontWeight": "bold", "color": theme.TEXTE},
             "transform": [{"filter": "datum.cle"}],
             "encoding": {"x": {"field": "label", "type": "ordinal"},
                          "y": {"field": "value", "type": "quantitative"},
                          "text": {"field": "value", "type": "quantitative", "format": ".3~g"}}},
        ],
    })
    if annotation:
        vl["title"]["subtitle"] = (spec.subtitle + " — " if spec.subtitle else "") + annotation
    return vl

REGISTRE: dict[str, Entree] = {
    "bar_h": Entree("bar_h", "Classement horizontal", "classement, domination, libellés longs", "séries temporelles", bar_h),
    "line": Entree("line", "Évolution dans le temps", "≥ 3 périodes ordonnées", "catégories, < 3 points", line),
    # kpi, bar, donut, funnel, scatter : même signature compiler(spec) -> dict
}

def catalogue_pour_prompt() -> str:
    return "\n".join(f"- {e.kind} : {e.description}. Utiliser : {e.use_when}. Éviter : {e.avoid_when}."
                     for e in REGISTRE.values())
```

### `app/modules/viz/render.py`
```python
from __future__ import annotations
import functools, hashlib, json
import vl_convert as vlc

def _cle(vl: dict) -> str:
    return hashlib.sha256(json.dumps(vl, sort_keys=True).encode()).hexdigest()

@functools.lru_cache(maxsize=256)
def _svg(cle: str, vl_json: str) -> str:
    return vlc.vegalite_to_svg(vl_json)

def vers_svg(vl: dict) -> str:
    return _svg(_cle(vl), json.dumps(vl))

def vers_png(vl: dict, scale: float = 2.0) -> bytes:
    return vlc.vegalite_to_png(json.dumps(vl), scale=scale)

def compile_ou_none(vl: dict) -> str | None:
    """Une spec qui ne compile pas = pas de graphique (repli tableau), jamais une exception."""
    try:
        return vers_svg(vl)
    except Exception:
        return None
```

### `app/modules/viz/pipeline.py`
```python
from __future__ import annotations
import json, re
from dataclasses import dataclass, asdict
from pydantic import ValidationError
from app.modules.viz import registry, render, selector
from app.modules.viz.schema import VizSpec

_BLOC = re.compile(r"```viz\s*\n(.*?)\n```", re.S)

@dataclass
class Viz:
    index: int
    spec: dict
    kind: str | None
    vl: dict | None
    statut: str          # ok | repli_tableau:<raison>

def extraire_et_compiler(markdown: str) -> list[Viz]:
    sortie = []
    for i, m in enumerate(_BLOC.finditer(markdown or "")):
        try:
            spec = VizSpec.model_validate(json.loads(m.group(1)))
        except (ValueError, ValidationError) as e:
            sortie.append(Viz(i, {"brut": m.group(1)[:2000]}, None, None, f"repli_tableau:schema:{str(e)[:120]}"))
            continue
        kind = selector.choisir(spec)
        if kind is None or kind not in registry.REGISTRE:
            sortie.append(Viz(i, spec.model_dump(), None, None, "repli_tableau:aucun_kind"))
            continue
        vl = registry.REGISTRE[kind].compiler(spec)
        if render.compile_ou_none(vl) is None:
            sortie.append(Viz(i, spec.model_dump(), kind, None, "repli_tableau:vegalite"))
            continue
        sortie.append(Viz(i, spec.model_dump(), kind, vl, "ok"))
    return sortie

def tableau_de_repli(spec: dict) -> list[list[str]]:
    """Les données du bloc, en cellules — pour que rien ne se perde."""
    s = spec.get("series") or []
    return [["", spec.get("unit") or "Valeur"]] + [[p["label"], f"{p['value']:g}"] for p in s]
```

### Rendu PDF (`reports/pdf.py`, branche `viz`)
```python
        elif b.genre == "viz":
            v = vizs.get(b.index)   # dict index → Viz, préparé par export_pdf depuis report.viz
            if v and v.vl:
                img = ImageReader(io.BytesIO(vers_png(v.vl)))
                story.append(KeepTogether([
                    Image(img, width=A4[0] - 4 * cm, height=(A4[0] - 4 * cm) * v.vl["height"] / v.vl["width"]),
                    Paragraph("Source : " + ", ".join(f'<a href="#src-{n}">[{n}]</a>' for n in v.spec["sources"]), petit),
                ]))
            else:
                story.append(tableau(tableau_de_repli(v.spec if v else {}), liens))
```

### App (`MarkdownView`, bloc fencé)
```jsx
// ```viz … ``` → figure ; l'index suit l'ordre d'apparition, comme côté serveur
if (line.startsWith('```viz')) {
  flush(idx); let j = idx + 1; while (j < lines.length && !lines[j].startsWith('```')) j += 1;
  const k = vizIndex++; idx = j + 1;
  blocks.push(reportId
    ? <figure key={'v' + k} className="viz"><img src={`${AX_API}/reports/${reportId}/viz/${k}.svg`} alt="" /></figure>
    : <p key={'v' + k} className="viz-attente">{libelle('Graphique disponible dans le rapport archivé.')}</p>);
  continue;
}
```

---

## 12. Exemple complet — données → insight → choix → JSON → rendu

**Données** (issues du rapport de contrôle de ce soir) : parts de marché 2026 — Alpha Audit 41 %, BetaCheck 25 %, Gamma Ctrl 14 %, Autres 20 %, citées `[3]` et `[7]`.

**Insight** que le modèle veut communiquer : un acteur domine.

**Ce que le modèle écrit** (bloc ```viz, § 8) : `intent: "domination"`, sans `kind`.

**Sélecteur** : nature `categoriel`, n = 4, libellés > 12 caractères → **bar_h**. **Insight** : max = Alpha Audit → mis en accent, les trois autres en contexte. `subtitle` conservé.

**Vega-Lite compilé** : barres horizontales triées, Alpha en `#7976F7`, valeurs à droite des barres, axe en « % », titre + sous-titre insight.

**Rendu attendu** : exactement l'image produite ce soir par `vl-convert` (`vl_test.png`, 0,36 s) — jointe au message.

**PDF** : la même image ×2 dans une carte insécable, « Source : [3], [7] » cliquables sous le graphique. **App** : `<img src="/api/reports/{id}/viz/0.svg">`, net à toute taille.

---

## 13. Roadmap

**V1 — indispensable (1,5 j)** : `VizSpec` + sélecteur + 7 kinds (kpi, bar, bar_h, line, donut, funnel, scatter) + rendu serveur SVG/PNG + PDF + app en image + prompt + migration + mesure du taux de repli. Aucune dépendance front.

**V2 — quand 5 rapports réels ont tourné** : `vega-embed` dans l'app (survol, export PNG depuis l'écran), waterfall, stacked_bar, quadrant avec seuils, heatmap risque, timeline réglementaire ; cartes stratégiques (`risk_card`, `benchmark_card`) comme blocs typés ; ```viz dans le chat via `POST /viz/render` ; export HTML autonome du rapport (même SVG).

**V3 — produit** : dashboards multi-rapports (benchmark sectoriel, comparaison d'entreprises) sur les mêmes specs stockées ; export PowerPoint (`python-pptx` + PNG) ; données financières/macro structurées en amont du LLM (le `VizSpec` devient alors produit par du code sur des données réelles, le LLM n'écrivant que l'`intent` et l'insight) ; scénarios et projections avec bandes d'incertitude.

**Ce qui ne change jamais** : le LLM n'écrit jamais de code de graphique, ni Vega-Lite ; il écrit un `VizSpec`. Tout le reste est déterministe, testé, et remplaçable.
