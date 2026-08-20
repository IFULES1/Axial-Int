# Backlog Axial — chantiers notés par Miradie

> Fichier de collecte : les chantiers y sont notés au fil de l'eau pour ne rien oublier,
> sans les mélanger avec les travaux en cours. Retirer les entrées une fois livrées.

## Noté le 18/08/2026

### Parcours & données
- [x] **Purger toutes les données mockées** *(fait 18/08 : MOCK_USER/MOCK_CONVERSATIONS supprimés, fallback neutre, suggestions personnalisées depuis le vrai profil)*
- [x] **Onboarding ↔ Mémoire alignés** *(fait 18/08 : les 12 champs Mémoire sont demandés à l'onboarding — bloc « Précisions (optionnel) » — + upload de documents dès l'étape 1)*.
- [x] **Inverser les étapes 3 et 4** *(fait 18/08 : Contexte → Démo → Activation (carte) → Première analyse ; profil sauvegardé dès l'étape 2)*
- [x] **Ne pas lancer d'analyse automatiquement** *(fait 18/08 : la question suggérée pré-remplit le composer, l'utilisateur envoie lui-même)*

### Crédits & facturation
- [x] Onglet **Crédits** : plan actuel + date du prochain prélèvement *(fait 18/08 : carte « Mon abonnement » + bouton Gérer via portail Stripe)*.
- [x] **Paramètres** : historiques conso + factures Stripe *(fait 18/08 : journal `credit_events` + factures avec PDF, onglet Facturation réel)*.

### Navigation & UI
- [x] Vérifier les **boutons retour** *(audit 18/08 : 8 boutons vérifiés cohérents avec le nouveau flux — RAS)*.
- [x] **Réagencer la page Documentation** *(fait 18/08 : cause racine = les classes .docs-* n'avaient JAMAIS eu de CSS ; feuille de style complète écrite — hiérarchie, tableaux de coûts, cartes, responsive — + typo « marcé » corrigée)*.

### Notifications & paramètres
- [x] **Notifications par email** *(fait 18/08 : préférences persistées (migration 0010) + toggles réels dans Paramètres + emails de veille gérés par la préférence « findings » + récap hebdo lundi matin dans le worker)*.
- [x] Paramètres > Espace de travail : **retirer « Membres »** *(fait 18/08)*

### Légal (ouvert le 18/08)
- [ ] **Compléter les mentions légales** (`frontend/app/legal/mentions/page.tsx`) : forme juridique, capital, adresse du siège, SIREN/RCS, directeur de la publication — puis faire valider CGU + confidentialité par un juriste.

## Déjà en file (sessions précédentes)
- [x] Refresh token frontend *(fait 18/08 : endpoint `/auth/refresh` (Supabase + local) + retry automatique sur 401 dans axFetch et l'upload — fini les échecs silencieux au bout d'une heure)*.
- [x] Cleanage front *(fait 18/08 : coûts de rapports RÉELS (25-40 cr) + types d'analyse réellement câblés + sélecteur de profondeur factice retiré ; titres des tuiles Rapports lisibles en sombre ; wording agents + 3 exemples dans l'état vide ; typo corrigée plus tôt)*.
- [x] Blocage serveur de l'étape carte *(fait 18/08 : table `user_subscriptions` + gate à la reprise de session basé sur l'état Stripe réel, avec backfill)*.
- [ ] Robustesse + légal : durcissement VPS, RGPD/CGU, monitoring.
- [ ] Data/veille : tag Inoreader « concurrents [secteur] », filtrage bruit RSS.

## Noté le 18/08/2026 (après-midi)
- [x] **Prompt engineering** *(fait 18/08 : réponse = NON, la V4 n'était PAS reprise — port complet de `business_prompts.py` V4 dans `analysis/prompts.py` + socle commun et personas assouplis « cadre = grille de lecture, pas une contrainte »)*.
- [x] **Sources consultables** *(fait 18/08 : citations [N] cliquables → panneau latéral avec titre, provenance, extrait, URL pour le web)*.
- [x] **Rendu du texte dans le chat** *(fait 18/08 : MarkdownView appliqué aux messages — gras, titres, listes, avec streaming conservé)*.
- [x] **Historique des conversations persistant** *(fait 18/08 : conversations rechargées à la connexion, messages chargés à l'ouverture, envois liés aux vrais ids backend)*.
- [ ] **Vitesse des réponses** *(quick wins faits 18/08 : RAG + recherche web parallélisés, zéro recherche sur les messages triviaux en conversation libre. Levier suivant = streaming des réponses LLM — chantier à part)*.

## Noté le 20/08/2026
- [ ] **Migration des utilisateurs de l'ancienne version** : transférer comptes (+ données pertinentes : profils, historique si utile) de l'ancienne app (insight-map) vers app.axial-ia.fr, avec communication aux utilisateurs.
- [ ] **Connexion DB-investisseur** : brancher la base investisseurs (Supabase DB-investisseur : fonds VC/PE, SGP, réseaux BA, crowdequity, partners) à l'app — activée à la demande pour produire une **cartographie des investisseurs** pertinents (secteur + stade + zone, cf. script `rechercher_investisseurs.py`).
- [ ] **Connexions MCP (Notion, Google)** : intégrations Notion + Gmail + Drive côté app — (a) enrichir les rapports avec les données des outils du client, (b) livrer les réponses/rapports directement dans Notion, Drive, etc.
- [ ] **Vérification du système de rapports vs ancienne app** — comparer le pipeline actuel (`app/modules/analysis/`) à l'audit de l'ancienne version (artifact « Anatomie des rapports » : https://claude.ai/code/artifact/f2368db0-3d36-4ad9-bc21-fe684e74641d). Écarts déjà identifiés : LLM principal (Perplexity `sonar-pro` + recherche web native vs Claude Sonnet 5 single-pass), volumes cibles (8000-10000 mots / 40 sources min pour la synthèse exécutive vs ~1800 mots / 8 sources aujourd'hui), enrichissements absents (Pappers, stats macro, Serper, APA), progression SSE réelle, garde PII (Presidio) avant envoi LLM.

> **Chantiers du jour (20/08)** : ① streaming SSE · ② migration des utilisateurs · ③ connexion DB-investisseur · ④ connexions MCP Notion/Google · ⑤ vérification des rapports vs ancienne app.
  - ⏸ **Lot A déployé le 20/08 — chantier laissé OUVERT** : la forme est validée par Miradie (volumes, sources, progression). Retour sur le FOND (le rapport apprend-il vraiment quelque chose, ou meuble-t-il pour atteindre 10 000 mots ?) attendu plus tard → ajustements ensuite.
  - **Audit réalisé le 20/08** → « Écart de profondeur » : https://claude.ai/code/artifact/0f6507f4-dfbb-4801-b8a6-f9b6d3548b1c
    Causes racines : (1) `top_k=8` alors que l'ancien exigeait 25-40 sources ; (2) aucune longueur cible dans les directives (le port V4 a omis `target_words`) ; (3) `max_tokens=12000` partagé avec le thinking de Sonnet 5.
    Bonnes surprises : `/analysis/stream` (SSE + facturation) déjà complet côté backend, seul le front appelle `/analysis/run` ; garde PII déjà codé mais `PII_GUARD_MODE=off` + sidecar Presidio éteint.
    Plan : lot A (profondeur, à valider — touche au contenu produit) · lot B (Pappers/stats/APA) · lot C (6e type réglementaire + PII activé, avant la migration des utilisateurs).

### Chantier ① — Streaming (20/08, livré)
- [x] **Rapports** : progression réelle SSE + battements de cœur toutes les 8 s (mesuré : 21 battements sur une génération de 4 min, connexion jamais coupée).
- [x] **Chat** : réponse mot à mot (`POST /intelligence/conversations/{id}/messages/stream`), sources envoyées AVANT le premier mot, repli automatique sur la route bloquante.
- [x] Bascule de provider possible tant qu'aucun mot n'est parti ; coupure en cours de réponse → le texte déjà écrit est conservé et signalé.
- Mesures lot A + ① : rapport 1 692 → **3 554 mots**, 8 → **25 sources** (dont documents internes), 87 citations sur 24 sources distinctes, aucun numéro orphelin.
