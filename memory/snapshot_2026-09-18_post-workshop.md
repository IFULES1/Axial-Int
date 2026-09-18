# Snapshot 2026-09-18 — après le workshop du 16/09

## Le workshop en chiffres (base de prod)
- 11 comptes créés le 16/09 entre 7 h et 11 h 20 (heure de Paris), 1 de plus le
  17/09 (OHé, 14 messages, revenu le lendemain).
- 21 rapports terminés + 1 « sources insuffisantes » le 16/09, 18 messages de
  conversation ; 15 emails « rapport prêt » et 12 emails de bienvenue partis.
- Crédits restants par compte : de 20 (HomePulse) à 100 (compte sans usage) ;
  100 crédits d'essai (`CREDITS_ESSAI=100` dans Doppler, toujours actif).
- Aucune erreur applicative (500) sur la matinée ; 6 échecs Tavily « 400 »
  sur un seul rapport : un participant avait collé son pitch de 7 024
  caractères en question (Tavily refuse > 400) → requête bornée à 400 le
  18/09 (commit déployé). Trois graphiques repliés en tableau (schéma viz :
  plus de 8 séries) — comportement attendu.

## État du produit
Sources v2 en prod (15/09), Perplexity et Pappers actifs, base de
connaissance 148 documents, dotation d'essai 100 crédits, correctifs de
robustesse pré-démo déployés (carte mémorisée 24 h, refresh 503, session de
flux fermée, pool 15+25, Perplexity niveau 2). Dernier build front
1789502906 (15/09 soir).

## Chantier en cours
- Skill « bilan-plateforme-axial » demandé le 18/09 : bilan exhaustif de bout
  en bout (comptes, santé fournisseurs, parcours réel, revue de chaîne, KB,
  consommation, incidents) — création en cours.
- En attente : retours du workshop (Miradie), décision sur les livres du
  commerce en KB, remise de `CREDITS_ESSAI` à 40, wording et prompts de rapport,
  coût du rerank Cohere non compté, clés Google pour Drive.

## Complément 18/09 après-midi — ciblage investisseurs v2 en prod
Retours du workshop classés (`docs/superpowers/specs/2026-09-18-retours-workshop.md`),
puis chantier livré et déployé (récap `2026-09-18-recap-ciblage-v2.md`) :
nombre demandé respecté, montant de levée retenu et affiché, composition par
stade, flux RSS visibles et vérifiés (26 flux, 0 en erreur). Tavily borné à
400 caractères. Restent : BA individuels (autre discussion), bons
interlocuteurs par fonds, `CREDITS_ESSAI` toujours à 100, livres du commerce
en KB, prompts de rapport.
