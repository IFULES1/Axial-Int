# Snapshot — 2026-08-18 (soir) — Backlog intégralement livré

## Objectif de la session
Dérouler tout le backlog produit issu du test V1.2 + réunion + notes de Miradie. **Tout est livré, déployé en prod, poussé sur GitHub** (`06225f2`).

## Livré aujourd'hui (ordre chronologique)
1. **Onboarding V2 + carte** : nom/site/positionnement + prefill LLM (`/memory/prefill`), démo & 1re question personnalisées, étape carte Stripe (trial 14j, garde facture 0€), migration 0008.
2. **Workspace** : sélecteur 3 modes (Conversation libre SANS routing — Gemini court/Sonnet long ; spécialistes explicites avec badge), persona `conseiller`, ancrage « Dans votre contexte — [Nom]… ».
3. **Documents robustes** : DOCX/XLSX/CSV + OCR tesseract (PDF scannés), 20 Mo, erreurs claires, indexation atomique.
4. **Robustesse/légal** : fail2ban, sshd clé-only, `.env` dev neutralisé, watchdog 5 min, pages `/legal/*` branchées.
5. **Abonnement tracké** (migration 0009) : `user_subscriptions` + `credit_events`, endpoints subscription/history/invoices/portal, carte « Mon abonnement », Paramètres > Facturation réel, gate carte serveur avec backfill Stripe.
6. **Backlog v1** : étapes onboarding réordonnées (carte=3, analyse=4, jamais auto — pré-remplit le composer), purge totale des mocks (Maya/Hapster), suggestions personnalisées, Paramètres sans Membres.
7. **Prompts V4 portés** (réponse à la question : la V4 de l'ancienne app n'avait PAS été reprise — port complet + personas assouplis « cadre = grille de lecture »). ⚠️ Feedback : montrer le diff AVANT de déployer du contenu produit (cf. mémoire feedback).
8. **Chat premium** : citations [N] cliquables → panneau latéral (titre, provenance, extrait, URL), markdown rendu (gras/titres), historique conversations persistant (ids backend réels, chargement paresseux), RAG+web parallélisés + skip trivial.
9. **Pièces jointes conversation** : docs importés via ➕ injectés dans le contexte du message suivant (chips, max 3, 8k car/doc).
10. **Onboarding↔Mémoire alignés** (12 champs + upload docs étape 1), boutons retour audités (RAS), **Documentation stylée** (cause racine : classes `.docs-*` jamais stylées — CSS complet écrit), typo « marché » corrigée.
11. **Notifications email réelles** (migration 0010) : prefs persistées, toggles branchés, emails de veille gérés par pref `findings`, récap hebdo lundi 6h UTC (worker `weekly_recap`).
12. **Refresh token** : `/auth/refresh` (Supabase + local) + retry auto sur 401 (axFetch + upload) — fini les 401 silencieux à ~1h.
13. **Cleanage final** : coûts rapports réels (25/40 cr) + types d'analyse câblés (market→etude_marche etc.) + profondeur factice retirée, dark mode tuiles, wording agents + 3 exemples.
+ admin@axial.com rechargé (+200 → 206 crédits).

## État courant
- Prod : https://app.axial-ia.fr — 4 services actifs, alembic **0010**, HTTPS, watchdog. GitHub `main` = source (déploiement encore par scp + rebuild ; passer à git pull un jour).
- Webhook Stripe live : opérationnel, validation finale au 1er vrai paiement (option C).
- Tests : 63/63. Déploiement type : scp fichiers → (alembic upgrade si migration) → restart services → rebuild front (`NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api`).

## Reste (rien de bloquant)
1. **Streaming des réponses LLM** (SSE) — le prochain gros gain de vitesse ressenti. Seul chantier technique restant.
2. **Mentions légales** : compléter SIREN/adresse (`frontend/app/legal/mentions/page.tsx`) + validation juriste — action Miradie.
3. Data/veille : tag Inoreader « concurrents [secteur] » — action Miradie.
4. Blocage carte 100 % serveur (aujourd'hui : gate à la reprise basé sur l'état Stripe réel) si besoin de strict.

## Contexte à ne pas oublier
- ⚠️ SSH VPS = clé uniquement (password désactivé) ; récupération via console hPanel.
- Prompts/wording/offres : TOUJOURS montrer l'avant/après à Miradie avant déploiement.
- Le front est un monolithe JSX (`App.jsx` ~5300 lignes) ; docs CSS dans `globals.css` (section DOCUMENTATION).
- Types de rapport front : `REPORT_TYPES` mappe id→`at` (analysis_type backend) + `cost` réel — garder synchronisé avec `CREDIT_COSTS`.
- Récap hebdo : requiert `axial-worker` actif ; requête SQL sur `auth.users` + `notification_prefs` (défaut weekly=true).
