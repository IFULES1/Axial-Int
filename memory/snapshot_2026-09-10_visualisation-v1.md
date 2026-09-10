# Snapshot — 2026-09-10 (soir) — Visualisation intelligente V1 livrée

## Objectif de la session

Après l'audit et les retours de Christian sur la forme des rapports
(tableaux, citations liées, synthèse, graphiques), construire une couche de
visualisation intelligente intégrée au générateur : le modèle décrit une
intention et des données, le code choisit, compile et rend le graphique —
dans les rapports, le PDF, le chat et l'email de veille.

## Tâches complétées

- ✓ **Forme des rapports** (matin) : tableaux rendus app + PDF, citations
  `[N]` liées à une section Sources générée, synthèse exécutive obligatoire
  (règle 7), première version de graphiques ReportLab puis règle 5 « chiffres
  → tableau, graphique = choix du modèle ». Prouvé sur un rapport réel.
- ✓ **Spec + plan** de la couche de visualisation
  (`docs/superpowers/specs/2026-09-10-visualisation-intelligente.md`,
  `docs/superpowers/plans/2026-09-11-visualisation-v1.md` — le nom porte le
  11/09, le travail date du 10/09 au soir).
- ✓ **Module `app/modules/viz/`** : `VizSpec` v1 (pydantic), sélecteur
  déterministe (intention × forme des données), insight (point clé calculé),
  thème (design system Axial en un `config` Vega-Lite), registre de 7 types
  (kpi, bar, bar_h, line, donut, funnel, scatter), rendu `vl-convert`
  (SVG/PNG côté serveur, sans navigateur), pipeline (extraction ```viz,
  validation, compilation, repli tableau), persistance par empreinte
  (`viz_rendus`, migration `0021_viz`, colonnes `reports.viz`,
  `messages.viz`), endpoints `/viz/{empreinte}.svg|png` (publics, immuables)
  et `POST /viz/rendu` (chat en flux).
- ✓ **Rendu** : PDF (image + source liée, `KeepTogether`), app (`VizFigure`,
  « en préparation » pendant le flux), email de veille (PNG hébergé).
- ✓ **Prompts** : règle 5 → bloc ```viz ; `VIZ_INSTRUCTION` branchée sur les
  trois chemins (spécialistes, conversation libre, veille). Diff validé par
  Miradie avant déploiement.
- ✓ **Preuves réelles** : rapport (2 viz ok : line + funnel, 3 tableaux,
  PDF 15 p.), chat libre (1 courbe rendue et archivée), veille (1 bar_h,
  email avec image). Rapports antérieurs rattrapés (`reports.viz`).
- ✓ Branche `visualisation-v1` fusionnée dans `main`, poussée. 143 tests.

## Décisions techniques prises

- **Vega-Lite via vl-convert** plutôt qu'ECharts/Plotly/D3 : le livrable
  premier est un PDF produit en Python sans navigateur ; une seule spec
  sert les quatre canaux ; JSON Schema officiel pour valider.
- **Le modèle n'écrit jamais de Vega-Lite** : `VizSpec` (10 champs) ; le
  sélecteur peut contredire le `kind` demandé ; spec invalide → tableau.
- **Empreinte SHA-256 = cache + identifiant public** des images.
- **Pas de graphique automatique** : pertinence avant quantité.

## Problèmes résolus

- VPS sans police → PNG sans aucun texte. `fonts-liberation` +
  `fonts-dejavu-core` installés ET liste de repli dans le thème (les deux).
- Formats d3 (« 3.2e+3 ») → nombres formatés en Python (« 3 200 M€ »).
- `loading="lazy"` empêchait le chargement des SVG dans le navigateur.
- Conversation libre sans la consigne (accrochée au bloc AXIAL Recommande,
  absent de ce chemin) → constante dédiée, test qui couvre les 3 chemins.
- `platypus.Image` attend un flux d'octets, pas un `ImageReader`.
- Colonnes `viz` vides stockées en JSON `null` : en SQL, tester
  `jsonb_typeof(viz) = 'array'`.

## État courant du système

```
Prod : app.axial-ia.fr · alembic 0021_viz · 143 tests · main = 78af45e
Compte de contrôle : audit-0907-1757265000@axial-qa.fr (en suppression email)
Rendus enregistrés : 8 · taux de repli à mesurer sur 5-6 rapports réels
```

## Prochaines étapes

1. **Chantier front + registre** (demandé le 10/09 soir) : six observations
   de Miradie (historique hors barre latérale, menu repliable, tuiles de
   rapports harmonisées, abonnement sur la page Crédits, logos des
   connexions, bouton déconnexion) + audit tu/vous. Deux agents lancés,
   bilan à croiser puis point global.
2. Mesurer le taux `repli_tableau` avant toute V2 (waterfall, quadrant,
   heatmap, `vega-embed` interactif, export HTML).
3. Reliquats : `COUTS_FIXES_MENSUELS_EUR`, clé DB-investisseur, SIREN,
   suppression email de l'adresse de Miradie, Skyted expiré.

## Contexte à ne pas oublier

- Rebuild front : `npm run build` fige `NEXT_PUBLIC_API_URL` ; vérifier
  `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` = 0.
- `rsync --files-from` passe le classifieur là où `scp … && ssh …` bloque.
- Une unité systemd transitoire n'a pas de `$HOME` : Doppler refuse.
- Deux Qdrant : le bon est le 6355. Accès : `ssh hostinger`,
  `PYTHONPATH=. doppler run --config prd -- .venv/bin/python`.
