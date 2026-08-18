# Snapshot — 2026-08-18 (fin de session) — Backlog clos + fix Rapports

## Objectif de la session (15→18/08, session continue)
Passer d'une app en local à une **plateforme live, monétisée et polie** : déploiement prod, audit des offres, exécution intégrale du backlog produit (test V1.2 + réunion + notes Miradie), corrections au fil des retours de test.

## Dernier lot livré (retour de test Miradie, 18/08 soir)
- [✓] **Navigation ne tue plus la génération de rapport** : le reset `setReportsState('empty')` à chaque retour sur l'onglet est supprimé — une génération en cours (ou un rapport ouvert) survit à la navigation ; à la fin, l'éditeur s'ouvre avec le résultat.
- [✓] **Cinématique de génération honnête** : fini le faux document SIRH, les faux % et « 47 sources scannées ». Nouveau : la VRAIE question en titre, timer réel, 3 étapes indicatives (sources → analyse → rédaction), squelettes. Mention explicite « vous pouvez naviguer ailleurs ».
- [✓] **Mocks rapports purgés** : prompt par défaut Lucca/Payfit supprimé (champ vide + templates génériques), `REPORT_OUTLINE/SOURCES/ACTIVITY` et `AGENTS` morts laissés inertes (non rendus).
- [✓] **Liste « Vos rapports »** : le backend archivait déjà chaque rapport (`finalize`) mais ne renvoyait pas l'id et le front n'affichait rien. `AnalysisResponse.report_id` ajouté + liste des rapports sauvegardés dans l'écran Rapports (ouverture via `GET /reports/{id}`) + plus de double archivage à l'export PDF.

## Bilan complet de la session (15→18/08)
1. **PROD LIVE** : https://app.axial-ia.fr (VPS Hostinger + Supabase + Stripe live + nginx/certbot + Doppler prd). Fixes déploiement : psycopg3, tsconfig, domaine `.fr`, **auth ES256/JWKS**.
2. **Audit offres** : grant 20 (pas 120), abo = reset mensuel, clés `pro/premium/boost`, landing #trust+#pricing, docs alignés.
3. **Onboarding V2 + carte** : nom/site/positionnement + prefill LLM, démo/question personnalisées, carte Stripe étape 3 (trial 14j), 12 champs Mémoire + upload docs étape 1, jamais d'analyse auto (pré-remplissage composer).
4. **Workspace** : 3 modes (Conversation libre sans routing — Gemini court/Sonnet long ; spécialistes badgés), routing par intention, ancrage contexte.
5. **Prompts V4 portés** (la V4 de l'ancienne app n'avait jamais été reprise) + personas assouplis. ⚠️ Règle : diff avant/après à valider par Miradie AVANT tout déploiement de contenu produit.
6. **Chat premium** : markdown rendu, citations [N] cliquables → panneau sources (extrait + URL), historique persistant (ids backend), pièces jointes injectées dans le message suivant, RAG+web parallèles.
7. **Documents robustes** : DOCX/XLSX/CSV + OCR, 20 Mo, erreurs claires, indexation atomique.
8. **Monétisation complète** : abonnement tracké (0009), carte « Mon abonnement » (plan + prochain prélèvement), Paramètres > Facturation (factures PDF Stripe + journal `credit_events`), portail client, gate carte serveur avec backfill. admin@axial.com +200 crédits.
9. **Sécurité/légal** : fail2ban, SSH clé-only (⚠️ password désactivé — récup hPanel), watchdog 5 min, pages `/legal/*`.
10. **Notifications** (0010) : prefs réelles, veille gated par `findings`, récap hebdo lundi (worker).
11. **Refresh token** : `/auth/refresh` + retry auto sur 401 — fini les pannes silencieuses à ~1h.
12. **Cleanage** : coûts rapports réels + types câblés, profondeur factice retirée, dark mode, wording agents + exemples, Documentation stylée (`.docs-*` n'avaient JAMAIS eu de CSS), typo « marché », zéro mock visible (Maya/Hapster supprimés).

## État courant
- Prod : 4 services actifs · alembic **0010** · 63/63 tests · GitHub `main` = `e3107eb`.
- Comptes prod : Miradie (abonné Pro trialing, 1er prélèvement 01/09) · admin@axial.com (206 crédits).
- Webhook Stripe live : actif, validation finale au 1er débit réel.
- Backlog (`docs/BACKLOG.md`) : **tout coché** sauf actions Miradie (mentions légales SIREN, tag Inoreader, validation juriste) et le **streaming des réponses** (prochain chantier technique).

## Prochaines étapes
1. **Streaming des réponses LLM** (SSE) — gros gain de vitesse ressenti, seul chantier technique restant.
2. Miradie : re-tester le parcours complet (surtout Rapports : générer → naviguer ailleurs → revenir), mentions légales, 1er paiement réel.
3. Option futur : déploiement par `git pull` sur le VPS (actuellement scp + rebuild), progression réelle de génération streamée dans la cinématique.

## Contexte à ne pas oublier
- Déploiement type : scp fichiers → (alembic upgrade si migration) → `systemctl restart axial-*` → rebuild front avec `NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api`.
- Prompts/wording/offres : montrer le diff à Miradie avant déploiement (feedback mémorisé).
- `REPORT_TYPES` front (id→analysis_type+cost) à garder synchro avec `CREDIT_COSTS` backend.
- La cinématique de génération est time-based (pas de vrai streaming de progression) — honnête mais indicative ; le streaming SSE la rendra réelle.
