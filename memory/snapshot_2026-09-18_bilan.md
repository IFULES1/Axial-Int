# Bilan plateforme du 18/09/2026 (mode complet, période depuis le 16/09)

## Verdict
Plateforme saine : 3 services actifs, parité de version OK (1789727318),
tous les fournisseurs répondent au contrôle réel, aucune erreur applicative
depuis le 17/09, base de connaissance intacte (43 188 points / 148 docs).
Depuis le workshop : 13 comptes créés (dont Offly le 18/09 après le
déploiement du ciblage v2), 26 rapports, 35 messages, 1 carte posée (Clover,
essai Stripe le 16/09), 3 comptes revenus un autre jour.

## Comptes (16/09 → 18/09, hors test/interne)
13 nouveaux comptes, 12 profils remplis (Chloé Le Cossec arrêtée à l'étape 1),
25 rapports terminés + 1 sources insuffisantes, 35 messages. Plus actifs :
OHé (14 msg), Clover (6 msg, carte), Venturix (3 jours actifs), HomePulse
(2 jours). Crédits restants : 16 à 100.

## Fournisseurs (contrôle réel)
Exa 2,3 s, Tavily / Linkup ~4,6 s, Perplexity, Gemini, Claude, Cohere,
Pappers : ok.

## Incidents depuis le 17/09
2 × Tavily 400 (question trop longue, corrigé le 18/09 : requête bornée à
400 car.), 1 graphique replié en tableau (plus de 8 séries, comportement
attendu), 4 redémarrages (déploiements), 5xx nginx uniquement pendant ces
redémarrages. Tick du worker sauté 3 fois (« instance déjà en cours ») : à
surveiller.

## Consommation 7 jours
16 études de marché (10,0 € modèle + 2,0 € recherche), 13 cartographies
investisseurs (3,6 € + 1,4 €), 3 concurrentielles (1,1 € + 0,3 €), 41 messages
(0,8 € + 0,8 €), 16 veilles. ≈ 20 € au total. Crédits : 813 débités, 1 440
d'essai accordés (15 comptes × ~100).

## Infra
RAM 2,0 / 7,9 Go, disque 68 Go libres, certificat jusqu'au 13/11, pool 15+25
sur 60 (14 utilisées), 0 rapport en cours, CREDITS_ESSAI = 100.

## Parcours réel
Rejoué aujourd'hui sur le build courant (compte QA) : connexion, cartographie
investisseurs (bandeau « Montant retenu », réseaux BA en tête), carte d'agent
avec 12 flux « à jour ». Inscription complète rejouée le 15/09 (build
précédent) ; Offly a fait le parcours complet le 18/09 sans incident
(inscription 10 h 34, premier rapport 11 h 53 → 12 h 02, rapport payant
12 h 55 → 12 h 59, emails reçus).

## Décisions ouvertes
Remise de CREDITS_ESSAI à 40, livres du commerce en KB, prompts de rapport,
BA individuels (autre discussion), bons interlocuteurs par fonds.
