# Snapshot — 2026-09-11

## Objectif de la session
Livrer « Conversations v2 » (mémoire de fil, retours utilisateur, gestion des conversations, mobile, dette backend) à partir des retours de Miradie du 10/09, en équipe d'agents (SDD), puis déployer en production.

## Tâches complétées
- [✓] Spec `docs/superpowers/specs/2026-09-10-conversations-v2.md` (réponses aux questions de Miradie : prévisualisation, GET/POST, `/agents` public, projets = dossiers, RAG, routage) et plan en 10 tâches.
- [✓] Tasks 1-9 exécutées en SDD (implémenteurs Opus/Sonnet, revue par tâche, revue globale Opus, contre-revues) — 22 commits `38c483b..d37587a`.
- [✓] Fusion dans `main`, push, **déploiement prod** : `alembic upgrade head` AVANT redémarrage (`0022_conversations_v2`, colonnes et index vérifiés), 270 tests serveur, restarts, build front (bundle sans 127.0.0.1), parcours réel complet (compte `qa-cv2-1109@axial-qa.fr`).
- [✓] Deux correctifs post-parcours déployés à chaud : requête de recherche = titre du fil + question de suite (`d2a03ac`) ; identifiant rétabli sur une réponse arrêtée par Stop pour faire réapparaître Régénérer (`d37587a`).
- [✓] Récap de livraison : `docs/superpowers/specs/2026-09-11-recap-conversations-v2.md`.

## Décisions techniques prises
- Routage réel en `auto` ; sélecteur d'agent conservé pour le choix explicite.
- Archivage du partiel dans une session SQLAlchemy dédiée (la session de requête est fermée avant le premier morceau sous uvicorn).
- Résumé roulant incrémental (`resume_messages`) en fil démon, un par conversation.
- Débit de crédits dans la même transaction que le message ; `partiel`/`degrade` jamais facturés ; clé d'idempotence seulement sur `complet`.
- Index unique composite `(conversation_id, cle_idempotence)` créé en `CONCURRENTLY`.
- Notification email d'erreur active par défaut (`ERREURS_NOTIF_*`), secrets masqués, fil démon.
- Ordre des messages : `(created_at, rôle user d'abord, id)`.

## État courant du système
- Prod `main` = `d37587a` (+ docs à venir). Tests : 271 backend, 29 Node. Services actifs, API et front 200.
- Compte QA prod : 34 crédits, 1 dossier « Tests » vide, conversation supprimée.
- Workspaces SDD (`.superpowers/sdd/…`) supprimés après livraison ; les rapports utiles sont résumés dans le récap.
- Wording global (prompts, descriptions) : toujours en attente de Miradie.

## Problèmes résolus
- Question de suite cherchée telle quelle → sources hors sujet → requête composée.
- Stop avant le `done` → pas d'identifiant → pas de Régénérer → backfill via `axMessagesPage`.
- Revue finale : session fermée dans l'archivage, secrets dans l'email, index non concurrent, ordre question/réponse à horodatage égal — tous corrigés avant fusion.
- `npm run build` pendant `next dev` casse le dev server → toujours arrêter le dev avant de builder.

## Prochaines étapes
1. Mineurs listés au §4 du récap (badge « interrompue » sur bulle vide, compteur de dossier avec épinglées, doublon « ARCHIVÉES », écran carte à chaque rechargement).
2. Observer le premier email d'erreur réel et le coût de recherche par message dans le tableau de bord.
3. Recevoir le wording de Miradie, l'appliquer (diff + OK avant déploiement).
4. Fonction suivante du chantier « une par une » (Rapports ? Agents de veille ?) — à décider avec Miradie.

## Contexte à ne pas oublier
- Déploiement : rsync par liste de fichiers, migration avant restart, tests serveur `PYTHONPATH=. doppler run --config prd -- .venv/bin/pytest -q`, build front puis `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` = 0, inscription neuve.
- Local : backend `uvicorn --port 8090` avec `.env` (AUTH_MODE=local), front `npm run dev -- -p 3005`, compte `qa-front-1009@axial-qa.fr` / `Qa-front-2026!` ; CORS local autorise :3005.
- Le cwd se réinitialise souvent : `cd /Users/mirad/axial-intelligence` d'abord.
- Ne jamais écrire de mot de passe prod ; Qdrant 6355 ; SDD : jamais deux implémenteurs sur `App.jsx` en parallèle, toujours préciser le modèle.
