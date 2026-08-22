# Snapshot — 22/08/2026 (après-midi) — Intégration Notion opérationnelle

## Ce qui s'est passé
Chantier ④ (connexions aux outils du client) livré, puis **corrigé en profondeur** après un test réel de Miradie : Notion était connecté mais le modèle répondait sincèrement qu'il n'y avait pas accès.

## Le vrai problème et sa correction
1. **Notion n'était branché que sur les rapports**, pas sur les conversations — le test s'est fait dans le chat.
2. **Le connecteur MCP ne pouvait pas marcher** : `mcp.notion.com` exige **son propre flux OAuth** (spec MCP), distinct du jeton d'intégration délivré par `api.notion.com/v1/oauth/token`. L'API renvoyait `400 — Authentication error while communicating with MCP server`. **Décision : abandon du MCP au profit de l'API REST Notion**, qui accepte le jeton dont on dispose.
3. **La recherche Notion est du mot-clé sur les titres** : une question en langage naturel lui faisait remonter des pages sans rapport (« Process d'Onboarding » pour une question sur la stratégie produit), qui perdaient ensuite le reranking face au web → 0 citation Notion.
   **Correction** : on récupère **tout l'espace partagé** (12 pages max, les plus récemment modifiées d'abord) et c'est **notre reranker** qui juge la pertinence — même principe que « ne pas plafonner le RAG » décidé par Miradie le 20/08.

## Architecture retenue
- `app/modules/integrations/notion_context.py` : corpus de l'espace, chargé en parallèle, **caché 15 min par utilisateur** (sinon plusieurs secondes de latence à chaque message).
- Les pages Notion rejoignent le **même pool numéroté** que le web et les documents (`app/shared/grounding.py` accepte `source="notion"`) → rerankées, citées `[N]`, visibles dans le panneau latéral avec leur URL.
- Branché sur **les conversations ET les rapports**.
- Le prompt système gagne un bloc « ESPACE DE TRAVAIL » quand des pages Notion sont présentes : les traiter comme le matériau de l'utilisateur, jamais comme une source publique.
- **Livraison** conservée : `POST /integrations/notion/deliver` crée une page Notion (markdown → blocs).

## Validé en production
Question « D'après mon espace Notion, quelle est la stratégie produit d'Axial ? » → **8 citations dont 2 Notion** (« Axial — Prometheus », « Feuille de route de stage »), réponse en 17 s, contenu réellement tiré des pages. Jeton chiffré en base (Fernet), espace « Axial » correctement identifié.

## Décisions
- **Google Drive : masqué dans l'interface** (décision Miradie du 22/08) — backend prêt et testé, réactivable en deux lignes.
- **Gmail : hors de portée** — portée `gmail.readonly` restreinte chez Google (validation + audit de sécurité annuel payant).
- `state` OAuth **signé** (JWT 10 min) au lieu d'un dictionnaire en mémoire : survit aux redémarrages et à plusieurs processus web.

## Reste à faire
1. **Internationalisation des contenus produits** — chantier suivant, validé par Miradie.
2. Séquences email automatiques (commencer par J-3 fin d'essai, échéance 01/09).
3. Retour de Miradie sur le **fond** des rapports (chantier ⑤ ouvert).
4. Dettes connues : cf. `snapshot_2026-08-22_migration-et-bugs.md`.

## État technique
Prod : alembic **0015** · 63/63 tests · GitHub `main` = `ad7132a`.
Secrets Notion posés en prod : `INTEGRATIONS_SECRET_KEY`, `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`.
