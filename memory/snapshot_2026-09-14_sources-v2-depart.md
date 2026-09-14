# Snapshot 2026-09-14 (soir) — départ du chantier Sources v2

## Décisions de Miradie (14/09)
- Prompts de rapport inchangés pour l'instant, sujet ouvert et à améliorer.
- Base investisseurs branchée aussi en conversation (questions de levée).
- Filtres de fraîcheur et de pertinence dérivés de la question.
- Pappers ajouté pour étude de marché et cartographie concurrentielle.
- Base de connaissance Axial alimentable avec tout type de corpus (admin).
- Veilles inchangées (« leur travail est de surveiller internet »).
- Drive lisible comme source de documents.
- Recherche à plusieurs niveaux, du plus performant au moins performant,
  Perplexity en plus ; la cohérence sémantique des sources vis-à-vis de la
  question doit être contrôlée.
- Ensuite : next steps consommation / recharge pour une app solide.

## Fait avant ce chantier (14/09)
- Alerte email « fournisseur indisponible » en prod (notifier_fournisseur).
- Constat `docs/superpowers/specs/2026-09-14-constat-sources-par-fonction.md`
  et inventaire `2026-09-14-inventaire-stack-api.md`.
- Consommation 30 j : ≈ 6 € modèle + 1 € recherche pour 16 rapports / 43 réponses.

## Chantier
Spec `docs/superpowers/specs/2026-09-14-sources-v2.md`, plan
`docs/superpowers/plans/2026-09-14-sources-v2.md`, exécution SDD dans
`.superpowers/sdd/2026-09-14-sources-v2/`. Clés à fournir par Miradie dans
Doppler : `PERPLEXITY_API_KEY`, `PAPPERS_API_KEY`, `GOOGLE_CLIENT_ID/SECRET`
(+ `NEXT_PUBLIC_GOOGLE_API_KEY` pour le sélecteur Drive).
