# Snapshot 29/09/2026 — mesure d'audience, formulaire, rapport offert

## Déployé en prod (par Miradie, builds 1790667848 puis 1790670834)
- Correctif worker (import des modèles, 8ae0670) : le rapport offert ne casse plus dans le worker.
- Validation explicite du formulaire connexion/inscription (bd9a213) : messages affichés, plus de bulle native muette.
- Marqueur du rapport offert libéré après échec, 3 tentatives max, « Rapport offert » libellé dans l'historique (ea583bb).
- GA4 avec bandeau de consentement FR/EN, mode consentement Google, lecture littérale des NEXT_PUBLIC (8ed43a0). Identifiant G-GZEKR57LPF dans /opt/axial-intelligence/frontend/.env.local.
- CREDITS_ESSAI = 50 (Doppler prd), effectif depuis le redémarrage backend.

## En attente de déploiement
- Clarity (projet ypsvvgbaan) : code prêt (suspendu dans l'app, repris sur landing/auth/onboarding), NEXT_PUBLIC_CLARITY_ID à poser dans .env.local du serveur puis rebuild.

## Décisions
- Pas de rattrapage pour iasi / STARTZUP (bénin).
- www.axial-ia.fr (certificat expiré, hébergement vitrine Hostinger) : sujet ouvert, marche à suivre hPanel en mémoire.

## Pourquoi la mesure d'audience
Search Console (acquisition SEO : requêtes, pages indexées), GA4 (d'où viennent les visiteurs, combien passent de la landing à l'inscription, événements inscription / rapport lancé / conversation), Clarity (comment ils se comportent sur landing et onboarding : clics morts, rage clicks, abandons de formulaire — exactement le cas du 28/09), Bing Webmaster (import GSC, 2 min). Tout sous consentement, jamais dans l'app.

## Sujets ouverts
Menu landing sur mobile, needrestart, Tavily à quota, Bing Webmaster, www certificat, fichier parasite à la racine du dépôt.
