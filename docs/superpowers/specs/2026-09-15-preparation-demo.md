# Préparation de la démo du 16/09 (9 h – 13 h)

Contexte : une dizaine de participants créent leur compte eux-mêmes, sans
carte, puis utilisent conversations et rapports. Revue de bout en bout faite
le 15/09 au soir : deux revues de code globales (`.superpowers/sdd/2026-09-15-demo/`)
et un parcours réel joué en prod avec un compte neuf (`qa-demo-1509@axial-qa.fr`).

## Parcours réel vérifié en prod (15/09, 19 h 30 – 20 h 30)

| Étape | Résultat |
|---|---|
| Inscription (email + mot de passe) | OK, arrivée sur l'étape 1 |
| Étape 1 contexte (nom, secteur, stade, défi, marché) | OK, choix bien enregistrés |
| Étape 2 aperçu | OK |
| Étape 3 activation, « Continuer sans carte » | OK, 40 crédits |
| Étape 4 première analyse offerte | lancée (202), terminée en 9 min, email « rapport prêt » envoyé, 0 crédit débité |
| Conversation (question de levée) | réponse en ~40 s, 2 crédits, base investisseurs en tête des sources |
| Rechargement de page | avant correctif : retour sur l'écran carte ; après : retour dans l'app |
| Rapport payant (cartographie concurrentielle, 25 crédits) | lancé, repris après rechargement (voir §3 pour le résultat) |

## Corrigé et déployé le 15/09 au soir

- « Continuer sans carte » mémorisé 24 h : un rechargement ne renvoie plus sur
  l'écran carte (la porte reste à chaque connexion explicite, règle produit
  conservée) ; le drapeau d'un clic « Ajouter ma carte » abandonné est effacé.
- Contexte d'onboarding conservé au rechargement des étapes 1 à 3.
- Rafraîchissement de session : une panne réseau ou Supabase répond 503 et
  garde les jetons, seul un refus avéré donne « Session expirée » (cause
  probable des déconnexions vues le 15/09).
- Mot de passe faible et email invalide : messages nommés à l'inscription.
- Flux de rapport : session fermée à la déconnexion du client (fuite de
  connexion qui aurait épuisé le pool avec 10 rapports simultanés).
- Emails d'erreur dédupliqués par gabarit de route (plus une rafale par UUID).
- Bandeau « Couverture partielle » adouci.
- Doppler : `DB_POOL_SIZE=15`, `DB_MAX_OVERFLOW=25` (40 connexions sur les 60
  de Supabase, ~10 prises par le système), `SEARCH_TIERS="exa,tavily,linkup|perplexity"`
  (Perplexity en second niveau : sa limite de débit bloquait les six angles).
- Sonde de santé réaliste, Perplexity limité à 2 appels simultanés, Pappers
  extraction déterministe et fiches conservées après classement.

## Consignes pour la matinée

1. **Ne rien déployer entre 8 h et 14 h** : un rebuild du front afficherait le
   bandeau « nouvelle version » chez tous les participants.
2. Les participants ont **100 crédits** (`CREDITS_ESSAI=100` dans Doppler depuis
   le 15/09 soir, vérifié par une inscription neuve) : une conversation coûte 2,
   une étude de marché 40, une cartographie concurrentielle ou réglementaire 25,
   une cartographie investisseurs 30. Remettre 40 après la démo :
   `doppler secrets set CREDITS_ESSAI=40 --config prd` puis redémarrage.
3. Le premier rapport offert part automatiquement à chaque inscription
   (4 à 9 min, email à la fin) : dix inscriptions groupées = dix rapports en
   parallèle. Étaler les inscriptions de quelques minutes limite la file.
4. Un participant qui recharge la page revient dans l'app ; un participant qui
   se déconnecte et se reconnecte repasse par l'écran carte (« Continuer sans
   carte » y est).
5. Emails automatiques : bienvenue (envoyée à la minute 20 de chaque heure aux
   comptes de moins de 2 h), « rapport prêt » à la fin du premier rapport.
6. En cas de panne : `ssh hostinger "systemctl is-active axial-backend axial-worker axial-frontend"`
   puis `ssh hostinger "sudo systemctl restart axial-backend axial-worker"` ;
   les services redémarrent seuls après un plantage (Restart=always). Les
   emails d'alerte fournisseur arrivent sur miradie.buranturu@axial-ia.fr.
7. Infra au 15/09 : 1,9 Go de RAM utilisés sur 7,9, 68 Go de disque libres,
   certificat valide jusqu'au 13/11.

## Reliquats connus, non bloquants

- Rapports d'un même type listés « Etude Marche » pendant la génération, titre
  réel à la fin.
- Un seul email « rapport prêt » par compte et par type de rapport.
- Anthropic saturé → repli silencieux sur Gemini pour la rédaction.
- Le worker lance à HH:40 les premiers rapports en attente, hors du sémaphore
  Perplexity (autre processus).
