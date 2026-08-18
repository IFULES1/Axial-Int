# Snapshot — 2026-08-17 — Prod live + audit offres + analyse test produit Notion

## Objectif de la session (15→17/08, session continue)
Déployer l'app en production, fiabiliser les offres, puis analyser les retours du test produit V1.2 (Notion) et de la réunion hebdo pour cadrer la suite.

## Tâches complétées
- [✓] **PROD LIVE : https://app.axial-ia.fr** — VPS Hostinger (à côté d'insight-mvp, intact), 4 services systemd (axial-qdrant :6355 + KB 875 Mo, axial-backend :8090, axial-worker, axial-frontend :3005), nginx `/etc/nginx/sites-enabled/axial`, HTTPS certbot (renouv. auto), Doppler prd, Supabase prod (projet ahkgziflrmhgrxucmvmk), Stripe LIVE.
- [✓] **Auth ES256** : Supabase signe en asymétrique → `auth/security.py` réécrit (PyJWKClient/JWKS + repli HS256). Sans ça : 401 partout après login.
- [✓] **Audit offres** (`docs/AUDIT_OFFRES_2026-08-16.md`) : grant 120→20, `grant_subscription()` (reset mensuel, pas de cumul) vs packs (cumul), pages front alignées (DocsCredits, modale quota, section landing #pricing + #trust), clés renommées **pro/premium**, pack **boost**, comptes test reset à 20. 5/5 tests verts.
- [✓] **GitHub** : repo poussé sur https://github.com/IFULES1/Axial-Int.git (main, 2 commits). Prochaines MàJ = git pull sur VPS.
- [✓] **Webhook Stripe live** : créé par l'utilisateur vers `https://app.axial-ia.fr/api/billing/webhook`, secret posé en prd, backend le charge (rejette les non-signées en 400). **Validation finale différée au 1er vrai paiement (option C).**
- [✓] **Resend DNS vérifié** (confirmé par l'utilisateur le 17/08).
- [✓] **Analyse des 2 pages Notion** (Test produit V1.2 + Réunion 17/08) croisée avec le code — voir écarts ci-dessous.

## Décisions prises (réunion 17/08 + arbitrages utilisateur du 17/08 au soir)
- **Pricing** : PAS d'offre annuelle (retour Tess — flexibilité). ⚠️ **CORRECTION UTILISATEUR : le « 20 crédits sans limite de temps » est FAUX** — le trial actuel (20 crédits / expire 14 jours) est le comportement voulu, NE PAS y toucher. Pro ~40€ évoqué en réunion vs 50€ implémenté → à trancher.
- **Onboarding paiement** : carte bancaire en **étape 4 de l'onboarding** (Stripe), 20 crédits gratuits, puis débit auto 50€ après 2 sem.-1 mois. Mesure l'engagement réel.
- **Workspace** : sélecteur de mode **Conversation libre / Market Scanner / Competitor Radar** près du champ de prompt (modèle Perplexity).
- Rester simple en v1, accumuler de la data comportementale.

## 🔴 Écarts constatés (test Notion ↔ code vérifié) — le plan de la suite
1. **Pas de refresh token** (`bridge.js` stocke access_token, jamais le refresh) → JWT expire à ~1h → **tout passe en 401 silencieux** (upload docs, messages, mémoire). C'est LA cause racine probable de « upload impossible » + « erreurs en conversation » du test (prouvé par les logs nginx : 401 à ~1h après login).
2. **Estimation Rapports FICTIVE** : front `estCredits` 240-400 × profondeur (0.4/1/2) → affiche 96-800 cr (le « 128 » du test = 320×0.4). Réel backend : le front envoie toujours `synthese_executive` = **25 cr** (App.jsx:4956). Le « Pro ne couvre pas 1 rapport » du test est donc FAUX en réel, mais l'UI le laisse croire. Vestige prototype à purger.
3. **Onboarding n'envoie que 4 champs** (sector, stage, challenge, geo — App.jsx:5058), en catch silencieux → pas de nom, site, positionnement. Le backend `company_profiles` n'a **pas de champ website**. La mémoire paraît vide après onboarding.
4. **Le contexte startup EST injecté au chat** (intelligence/service.py:196 `memory.build_context`) — mais profil quasi vide (cf. #3) + 401 (cf. #1) → réponses génériques perçues. Le test dit aussi : le recontextualiser explicitement (« Dans votre contexte… »).
5. **Routing agents** : questions concurrents → Market Scanner qui répond « hors périmètre ». Router selon l'intention.
6. UI : dark mode Reports (titres illisibles), page Documentation (mise en page + typo « marcé cible » confirmée dans App.jsx), wording agents/documents.

## État courant
- Prod : 4 services actifs, HTTPS OK, front+API 200. 2 comptes Supabase (reset 20 cr).
- Local = source de vérité, sync VPS par scp/rsync (→ passer à git pull). founder2 local ≠ prod.
- Offres live : free_beta 20 / pro 50€·120 / premium 90€·250 / enterprise ; packs starter·boost·scale 20/40/80€.

## Prochaines étapes — ORDRE ARBITRÉ PAR L'UTILISATEUR (17/08 soir)
**Reprise demain (18/08) : PLANIFIER puis IMPLÉMENTER les gros chantiers d'abord** (méthode : plan court par point → validation utilisateur → exécution). L'utilisateur précisera par lequel commencer. Candidats (issus du croisement test Notion + réunion + ses axes) :
1. **Onboarding V2 + carte** : nom + site + positionnement (+ migration champ `website`), pré-remplissage depuis le site, sync → mémoire visible, cartes démo personnalisées, carte Stripe en étape 4 (Setup Intent, débit auto 50€ après 2 sem.-1 mois) ; trancher Pro 40 vs 50€.
2. **Workspace** : sélecteur de mode Conversation libre / Market Scanner / Competitor Radar (modèle Perplexity), routing par intention, contexte rendu visible (« Dans votre contexte… »).
3. **Robustesse import documents** : fiabiliser upload + OCR/DOCX + prouver l'usage réel dans les réponses (citations).
4. **Robustesse + légal** : durcissement VPS (SSH, fail2ban), RGPD/CGU, monitoring.
5. **Data/veille** : tag Inoreader « concurrents [secteur] » (action utilisateur), filtrage bruit RSS.

**GARDÉS POUR LA FIN (décision utilisateur — ne PAS commencer par ça)** :
- Refresh token frontend (cause racine des 401 à ~1h) + erreurs non silencieuses.
- Cleanage front : estimations rapports fictives (estCredits), typo « marcé », dark mode Rapports, wordings.
- ⚠️ Trial : AUCUN changement — les 20 crédits / 14 jours sont voulus (le « sans limite de temps » des notes de réunion est faux).

## Contexte à ne pas oublier
- SSH VPS : alias `hostinger`. Déploiement : scp fichiers → rebuild front (`NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api npm run build`) → `systemctl restart axial-*`.
- Doppler prd = source des secrets ; jamais manipuler les valeurs. Stripe LIVE en prd (test en dev).
- Les 401 en prod ≈ token expiré (pas de refresh) — ne pas confondre avec le bug ES256 (corrigé).
- Front = `frontend/app/_prototype/App.jsx` (monolithe JSX ~5000 lignes, i18n interne, vestiges prototype).
- Pages Notion de référence : « Test produit AXIAL Intelligence V1.2 » + « Réunion 17/08 » (workspace axial-ia).
