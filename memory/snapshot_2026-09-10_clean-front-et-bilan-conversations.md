# Snapshot — 2026-09-10 (après-midi)

## Objectif de la session
Nettoyer le front et le registre (vouvoiement app / tutoiement emails), déployer, puis ouvrir le chantier « fonction par fonction » en commençant par les Conversations.

## Tâches complétées
- [✓] Branche `clean-front` (12 commits) exécutée en subagent-driven development (implémenteurs Sonnet, revues par tâche, revue globale Opus, une vague de correction), fusionnée dans `main` et **déployée en prod** (rsync, 150 tests verts sur le VPS, alembic `0021_viz` head, restarts, `npm run build` avec bundle vérifié `127.0.0.1:8090` = 0, parcours réel compte neuf `qa-front-1009c@axial-qa.fr`).
  - Registre : `REGISTRE_INSTRUCTION` (personas.py) sur agents, conversation libre et veille ; règle 8 de `OUTPUT_STYLE` (rapports) ; notes de redirection, Stripe, erreurs → vouvoiement ; `tests/test_registre.py` (7 tests, dont emails qui tutoient et chemin libre).
  - Front : historique retiré de la barre latérale ; bouton « Se déconnecter » ; barre repliable (`useSidebar`, `axial_sidebar`, rail 60 px desktop uniquement `@media (min-width:768px)`, tiroir mobile `<767px` + voile + hamburger) ; bascule du menu en tête de barre à la place de « Nouvelle analyse » ; libellé OUTILS masqué en rail ; tuiles de rapports 3×2 avec coût ; `ReportsQuota` câblé (solde < coût → écran avec « Voir les crédits » / « Retour ») ; carte abonnement toujours visible (3 états, badge « Plan actuel » pour active+trialing, `SUB_STATUS` étendu) ; logos officiels Notion / Google Drive (`frontend/public/logos/*.svg`, Wikimedia Commons) ; `.nav-item` sans bordure native ; ~250 lignes CSS mortes et composants prototype supprimés (`frontend/prototype/`, `public/proto/libs`, fixtures, TweaksPanel, ShareModal…).
  - Backend : `_own_conversation` renvoie 404 pour un id non UUID (au lieu de 500).
- [✓] Vérification visuelle locale : backend `uvicorn --port 8090` avec `.env` (AUTH_MODE=local, DB locale migrée à head), front `npm run dev -- -p 3005`, compte `qa-front-1009@axial-qa.fr` / `Qa-front-2026!`. **Ne jamais lancer `npm run build` pendant que `next dev` tourne** (écrase `.next`, page 500).
- [✓] Bilan Conversations : `docs/superpowers/specs/2026-09-10-bilan-conversations.md` (synthèse) + `-backend.md` + `-frontend.md` (commit 434355b, poussé).
- [✓] Mémoire persistante : `project_axial_chantiers_sept.md`.

## Décisions techniques prises
- Registre : vouvoiement pour tout texte d'app et contenu généré, tutoiement conservé dans les emails (voix de Miradie).
- Notes de redirection et contenu de veille = texte d'app → vouvoiement.
- `ReportsQuota` réduit à deux actions (les boutons Pro/Recharger n'étaient pas câblés, tarifs en dur retirés).
- Logos : officiels (usage « intégration » autorisé par Notion et Google), pas de dessins maison.
- Rail desktop et tiroir mobile séparés par media queries (pas d'`!important`).

## État courant du système
- Prod `main` = `434355b`. VPS : `/opt/axial-intelligence`, services `axial-backend`, `axial-worker`, `axial-frontend`. Tests serveur 150 verts.
- Compte QA prod `qa-front-1009c@axial-qa.fr` : 38 crédits, 1 conversation (id `2bef891c-…`).
- Mesure réelle d'un message libre (tier `report`) : 10 s de recherche + ~2 min 20 de génération ; le texte affiché a diminué puis s'est réécrit après le payload final (animation `AiMsg` relancée) ; pastille crédits non rafraîchie (40 affiché, 38 en base).
- Le wording (prompts, descriptions des types de rapports, textes EN) reste **en attente de Miradie** — ne pas le réécrire.

## Problèmes résolus
- Preview tool réutilisait un serveur étranger (`axial-sales-api` port 3000) → Next lancé à la main sur 3005.
- DB locale à `0007` → `alembic upgrade head` (local seulement).
- Rail qui fuyait en mobile (spécificité CSS) → bloc rail sous `min-width:768px`.
- `.icon-tile` sans règle de base → `.settings-row .icon-tile`.
- 500 sur id de conversation `c-…` (ancien bouton « Nouvelle analyse ») → 404 + bouton retiré.

## Prochaines étapes (retours de Miradie reçus le 10/09, à exécuter)
1. Snapshot (fait) puis spec + plan « Conversations v2 » et exécution SDD.
2. Mémoire de fil envoyée au modèle (fenêtre glissante + résumé), retours explicites (crédits insuffisants → pop-up achat/abonnement, contexte entreprise manquant, documents illisibles ou limite atteinte), mobile responsive **prioritaire**, animation d'attente par étapes, solde rafraîchi, auto-défilement, verrous (envoi pendant flux, changement d'agent), markdown complet, erreurs nommées + Réessayer, suggestions EN.
3. Gestion : renommer / supprimer / archiver / épingler, recherche dans le contenu, régénérer / éditer / stopper, coût par message et par conversation via la pastille.
4. Dette : routage auto réel (Axial route seul, agents spécifiques seulement si demandés), coût de recherche par message, idempotence, facturation partielle, reprise sur troncature en streaming, cache Notion, titres génériques unifiés, code mort (`axChat`, `axNewConversation`, `_convId`, `common.share`, `share.title`, `archived_at`, parsing SSE dupliqué).
5. Notification email à miradie.buranturu@axial-ia.fr sur toute erreur backend (bug, compte, action).
6. Tests de bout en bout : `stream_message` (persistance, facturation, déconnexion), 402, routage AUTO réel, citations/viz, export, `_attached_docs_context`, `grounding.assemble`, coût.
7. Questions de Miradie à traiter dans la réponse : prévisualisation `/agents/route`, GET vs POST, pourquoi `/agents` public, notion de projet, quand rafraîchir le RAG.

## Contexte à ne pas oublier
- Déploiement : `rsync -q --files-from=<liste> ./ hostinger:/opt/axial-intelligence/` ; tests serveur `PYTHONPATH=. doppler run --config prd -- .venv/bin/pytest -q` ; front `.env.local` = `https://app.axial-ia.fr/api` ; vérifier `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` = 0 ; tester une inscription neuve.
- SDD : scripts `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.3.0/skills/subagent-driven-development/scripts/` ; workspace `.superpowers/sdd/<plan>/` ; jamais deux implémenteurs en parallèle sur `App.jsx` ; toujours préciser le modèle.
- Le cwd se réinitialise souvent à `/Users/mirad` : toujours `cd /Users/mirad/axial-intelligence`.
- Règles : diff + OK de Miradie avant de déployer du contenu ; ne jamais écrire de mot de passe prod ; Qdrant port 6355 ; nginx `X-Accel-Buffering: no` déjà posé sur les routes SSE.
