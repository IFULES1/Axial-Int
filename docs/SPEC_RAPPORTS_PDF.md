# Spec — Export PDF des Rapports (Phase 2.2)

## Objectif
Le mode **Reports** génère des rapports longs (Claude Sonnet). L'utilisateur doit
pouvoir les **exporter en PDF**, avec l'identité visuelle Axial.

## Filigrane (watermark) — exigence
- **Image de marque Axial** (fond dégradé bleu/violet + logo AXIAL « AI at the axis of Time »
  + triangles filaires + mention `© AXIAL, 2025. Tous droits réservés. www.axial-ia.fr`).
- Appliqué en **filigrane pleine page** sur chaque page du PDF exporté.
- **Grammage transparent** : opacité faible (viser ~8–15 %) pour rester lisible sous
  le texte du rapport, sans gêner la lecture.
- Asset source à déposer dans le repo : **`app/assets/branding/watermark-axial.png`**
  (fourni par l'utilisateur — image haute résolution reçue le 2026-08-14).

## Implémentation (piste)
- Génération PDF côté backend (au choix : `weasyprint` HTML→PDF, ou `reportlab`).
- Avec WeasyPrint : CSS `@page { background: url(watermark) ...; }` ou une couche
  `position: fixed` en `opacity: 0.1` derrière le contenu.
- Avec ReportLab : dessiner l'image en fond de chaque page via un `onPage` callback,
  avec `setFillAlpha`/transparence.
- Le bouton **« Exporter »** existe déjà dans l'UI (vu dans App.jsx) → le brancher
  sur l'endpoint d'export PDF.

## À faire au démarrage de la Phase 2.2
1. Déposer l'asset `watermark-axial.png` dans `app/assets/branding/`.
2. Choisir la lib PDF (WeasyPrint recommandé pour un rendu HTML/CSS fidèle au rapport).
3. Câbler le bouton Exporter → endpoint `/reports/{id}/export.pdf`.
4. Vérifier la lisibilité du texte par-dessus le filigrane (ajuster l'opacité).
