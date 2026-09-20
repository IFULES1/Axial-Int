# Snapshot 20/09/2026 — bilan rapide + mesure d'audience

## État
- Services actifs, parité OK (BUILD_ID 1789745906 = bundle = /version), 0 bundle 127.0.0.1, RAM 2 Go/7,9, disque 69 Go libres, cert 53 j, pool 14/60, 0 rapport en cours.
- Comptes depuis le 18/09 : 1 (Offly, 2 rapports terminés, 73 crédits). 7 j : 32 rapports (16 études de marché, 13 cartographies, 2 concurrentielles, 1 sources insuffisantes), 43 messages, 18 veilles. Coût modèle ≈ 15 €, recherche ≈ 3,6 € (ordre de grandeur).
- Fournisseurs : Exa, Linkup, Perplexity, Gemini, Claude, Cohere, Pappers OK. **Tavily épuisé** : plan Researcher 1 000 crédits/mois, 999 consommés, 432 depuis le 18/09 15:58 ; la cascade (Exa+Linkup, puis Perplexity) compense, aucun rapport échoué pour cette raison.
- Journal : 3 ticks worker sautés (19/09, instance déjà en cours, bénin), 502 = redémarrages du déploiement 18/09 15:13.

## Livré (commit f554ff6, local, PAS déployé : rsync bloqué par le classifieur)
- Mesure d'audience avec consentement : `frontend/app/_prototype/mesure.js`, bandeau FR/EN, GA4 (IP anonymisée), Clarity limité landing/auth/onboarding, événements page_vue/inscription/rapport_lance/conversation_envoyee. 145 tests front.
- En attente des identifiants GA4 et Clarity de Miradie pour déployer (rien ne se charge sans).

## À faire (liste consolidée)
Voir le compte rendu du 20/09 dans la conversation ; reprise dans memory/project_axial_chantiers_sept.md.
