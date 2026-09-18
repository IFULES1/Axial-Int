# Ciblage investisseurs v2 — récapitulatif (18/09/2026)

Spec : `2026-09-18-ciblage-investisseurs-v2.md`. Exécution : deux tâches en
parallèle (fichiers disjoints), une revue et une re-revue chacune, déployées
le 18/09 (migration `0025_flux_rss`, backend, front 1789727318).

## Livré

| Décision (retours workshop) | Réalisé | Vérifié en prod |
|---|---|---|
| Nombre d'investisseurs demandé respecté, sinon maximum en base avec mention | `nombre_demande` (« 5 à 10 » → 10, « une dizaine », « top 15 », EN), `map_for_profile(question=…)` borne la liste, consigne dynamique au modèle (deux phrases de la spec), `detail.demande` | question réelle : 10 demandés, 12 disponibles, rapport « dix interlocuteurs », bandeau « 10 investisseurs sur 10 demandés » |
| Attention au montant de la levée | `montant_de_levee` : formats FR/EN, « 300 000k€ » ambigu → 300 k€ retenu, plausibilité par stade (pre-seed ≤ 2 M€, seed ≤ 8 M€, série A ≤ 30 M€), montant après le verbe de levée ou avant « en <stade> », « 6 mois » jamais un montant ; bloc « Paramètres de la levée retenus » en tête des sources ; bandeau « Montant retenu » dans l'éditeur (« à vérifier » si ambigu) | « 300k euros en pre seed » → 300 000 €, non ambigu, bandeau affiché |
| Ciblage par stade | `composer_par_stade` : pre-seed → réseaux de BA d'abord puis fonds (plancher 3), seed → parts égales, série A+ → fonds d'abord (plancher 3 réseaux) ; `stade_depuis` (question > profil, « pre seed » avec espace, « pre seed/seed » → pre-seed) ; ordre des sources [N] aligné sur la composition ; « déjà contacté X » exclu | réseaux de BA en [1] et [2], Kima Ventures exclu |
| Flux RSS visibles et testés | `GET /watches/{id}/feeds` (flux de l'agent, état vert/rouge/gris, origine catalogue / ajouté par vous), ligne repliable « Sources : N flux » sur la carte, « Gérer mes flux », vérification parallèle bornée (`POST /watches/feeds/verifier` admin, `scripts/tester_flux_rss.py`), vérification en arrière-plan au premier affichage ou après 7 jours, titre lu à l'ajout d'une URL, colonnes `derniere_verification_at` / `derniere_erreur` | 26 flux vérifiés, 0 en erreur ; carte : 12 flux « à jour » |

Tests : 788 backend (82 ciblage, 31 flux), 137 front.

## Décisions prises en cours d'exécution
- Fiches et réseaux : plancher `min(3, disponibles)` pour la catégorie
  secondaire, pour qu'un pre-seed voie aussi des fonds d'amorçage et qu'une
  série A garde quelques réseaux.
- Les flux du catalogue attachés à la création d'un agent s'affichent
  « catalogue », pas « ajouté par vous ».
- La conversation (`intelligence/service.py`) appelle encore
  `map_for_profile` sans la question : nombre demandé, montant et exclusions
  n'y jouent pas (chantier suivant si besoin).

## Reliquats
- Test paramétré sur 6 des 11 questions réelles du 16/09 (les 5 autres à
  ajouter).
- Chantiers suivants annoncés par Miradie : BA individuels (ciblage dans une
  autre discussion), bons interlocuteurs par fonds avec enrichissement.
