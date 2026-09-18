# Axial Intelligence — frontend

Next.js 14. Voir `docs/superpowers/specs/` pour les specs de chantier.

## Variables d'environnement

Ce fichier remplace `frontend/.env.local.example` (revue Task 7, Sources v2,
tour 1) : ce dernier était ignoré par `.gitignore` (`.env.*`), donc absent du
dépôt sur tout nouveau clone — la documentation des variables n'existait
que sur la machine où il avait été créé. À poser dans `frontend/.env.local`
(non versionné, un par environnement).

| Variable | Rôle | Obligatoire |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | URL du backend FastAPI (ex. `http://localhost:8080` en dev, `https://app.axial-ia.fr/api` en prod). | Oui |
| `NEXT_PUBLIC_SUPABASE_URL` | URL du projet Supabase (auth). | Oui |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Clé anonyme Supabase (auth). | Oui |
| `NEXT_PUBLIC_GOOGLE_API_KEY` | Clé API pour le Google Picker (Sources v2 §6, « Importer depuis Drive » dans la surface Mémoire) — Google Cloud Console → APIs & Services → Credentials → API key, restreinte aux API Drive/Picker et au domaine `app.axial-ia.fr`. | Non — sans elle, le bouton « Importer depuis Drive » reste masqué (jamais d'erreur visible). |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Même client OAuth que le `GOOGLE_CLIENT_ID` serveur (Doppler `prd`), côté navigateur — doit être un client OAuth « Web application » dont les origines JavaScript autorisées incluent cette app. | Non — même comportement que ci-dessus. |
| `NEXT_PUBLIC_GA_ID` | Identifiant de mesure Google Analytics 4 (`G-XXXXXXXX`). Chargé uniquement après acceptation du bandeau de consentement, IP anonymisée, signaux publicitaires coupés. | Non — sans elle, ni bandeau ni script. |
| `NEXT_PUBLIC_CLARITY_ID` | Identifiant de projet Microsoft Clarity. Chargé après consentement et **seulement** sur la landing, la connexion et l'onboarding (jamais dans l'app : conversations et rapports confidentiels). | Non — même comportement. |

Le bouton « Importer depuis Drive » n'apparaît que si les DEUX variables
`NEXT_PUBLIC_GOOGLE_*` sont posées **ET** si `GET /integrations/status`
déclare `google.selecteur = true` (c'est-à-dire que le backend a lui-même
`GOOGLE_CLIENT_ID` configuré, indépendamment du secret nécessaire à
l'échange OAuth serveur).

**`process.env.NEXT_PUBLIC_*` est figé à la compilation Next.js.** Poser ces
clés dans Doppler/`.env.local` ne fait pas apparaître le bouton sans
rebuild — et un rebuild du front est précisément le geste qui a déjà cassé
la prod (voir mémoire « Build front Axial : URL API figée à la
compilation »). Après tout changement de ces variables en production,
vérifier le bundle déployé et tester une inscription/un import neuf avant de
considérer le déploiement terminé.
