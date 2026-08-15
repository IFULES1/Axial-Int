# Snapshot — 2026-08-14 (soir) — Qdrant natif + chat fixes + VEILLE INTELLIGENTE

## Objectif de la session
Sortir Qdrant de l'embedded, corriger le chat en réel, puis **construire les agents de
veille intelligents** (Phase 2) : skills ciblés, mémoire cumulative, RSS+web, historique+email.

## Tâches complétées

### Infra & chat (début de session)
- [✓] **Qdrant natif** (binaire v1.19.0, PAS Docker) sur **port 6355**, 72 669 vecteurs migrés
  sans ré-embedding (`scripts/migrate_qdrant_to_server.py`). `QDRANT_URL=http://localhost:6355`.
  Relance : `./scripts/start_qdrant.sh`. Ancien embedded `data/qdrant/` conservé (backup).
- [✓] **Base de connaissance complète** : 241 docs / 79 078 points (fix encodage surrogates dans
  `extract.py`). ~8 PDF scannés restants → OCR (Phase 3).
- [✓] **Chat Workspace — 4 bugs corrigés** (via test à l'écran) :
  1. `content.map` crash (string vs array) → normalisation dans `AiMsg`.
  2. `/health/providers` obsolète → réécrit sur le vrai stack (`app/shared/health.py`).
  3. Pas de failover LLM → `llm_client.generate()` chaîne Gemini→Claude + retry court (Gemini 503 fréquents).
  4. **Bug racine « rien ne se passe »** : l'envoi depuis l'accueil vide était câblé sur
     `setActiveId(null)` (ignorait le texte) → séparé `onSendNew`/`onNewChat`.
  + Mocks conversations supprimés, indicateur « AXIAL analyse… », streaming 4→40, citations internes remontées.
- [✓] **Rerank combiné web+interne** (`_assemble_sources`) + traçabilité `[N]` ↔ source.
- [✓] **Tri disque** → disque externe `IFULES-X1` (Mac 5→14 Go libres).

### VEILLE INTELLIGENTE (cœur de la session — Phase 2 Agents)
- [✓] **Data model** (`app/modules/watches/models.py`) : `Watch` + colonnes `skill` + `rolling_state` ;
  nouvelles tables `WatchRun` (historique daté + snapshot mémoire) et `RssFeed`. Migration **`0007_veille`** appliquée.
- [✓] **Couche RSS** (`rss.py`, `feedparser`) : articles nouveaux depuis le dernier run, dédup par URL, fail-soft.
- [✓] **Skills de veille** (`skills.py`) : 4 expertises (concurrentielle, réglementaire, financement,
  produit_tech), chacune = prompt spécialisé + catégories RSS + template de requête web. Moteur générique.
- [✓] **Moteur cumulatif** (`engine.py`) : fusionne RSS+web (rerank), injecte l'**état roulant**, produit
  en UNE passe **delta + rapport complet + état roulant mis à jour**. Sortie par **délimiteurs**
  (`===DELTA===` etc., robuste vs JSON multi-lignes).
- [✓] **Service** (`run_watch` réécrit) : sources → génération cumulative → `WatchRun` + maj `rolling_state`
  + crédits + email digest (delta+rapport). Helpers `list_runs`, `_feeds_for`, `_prior_seen_urls` (dédup).
- [✓] **Router** : `skill` dans create, `/watches/skills`, `/watches/{id}/runs`, CRUD `/watches/feeds`.
- [✓] **Front Agents branché** (`App.jsx`) : `AgentsLibrary` (vrais `/watches`), `AgentWizard`
  (sujet + skill + cadence mappée → `axCreateWatch`), `AgentSession` (timeline des runs réels +
  détail delta/rapport + boutons Run-now / Pause). Bridge : `axListWatches/axCreateWatch/axWatchRuns/axRunWatch/axPause/axResume`.
- [✓] **VALIDÉ EN RÉEL** : mémoire cumulative prouvée (run#1 « nouveautés », run#2 « rien de neuf, déjà connu »),
  affichée dans l'UI. 45/45 tests backend verts.

## Décisions prises (avec l'utilisateur)
- Sortie veille = **delta + rapport complet**. Mémoire = **état roulant compact**. Skills = les 4 (choisi par Claude).
- Skill créé : **`reformuler-guillemets`** (~/.claude/skills/) — reformule le texte entre `" "` selon le contexte.
- Filigrane PDF rapports : spec dans `docs/SPEC_RAPPORTS_PDF.md` (asset PNG à déposer dans `app/assets/branding/`).

## État courant
- **Qdrant** 6355 (72 669 pts) · **Backend** 8090 · **Front** 3005 · tous UP.
- Compte test : `founder2@axialtest.com` / `password123` (crédits presque épuisés à force de tester — recharger si besoin).
- 2 agents de veille de test créés + feed TechCrunch. `feedparser` ajouté à `requirements.txt`.
- ⚠️ Docker occupe 6333/3000/8080 (ancien insight-map) — ne pas toucher.

## Prochaines étapes
1. **Lancer le worker** (`make worker`) pour les runs automatiques selon la cadence (daily/weekly).
2. **SMTP** dans Doppler (`smtp_host`…) pour l'envoi réel des emails de veille.
3. **UI gestion des feeds RSS** (aujourd'hui CRUD API only : `/watches/feeds`) + seed des feeds de l'utilisateur.
4. **Mode Reports** : brancher `/analysis/run` + `/reports` + export PDF (filigrane) au front (composants ReportsEmpty/Generating/Editor encore mockés).
5. Recharger les crédits de founder2 pour tester la création d'agent depuis le wizard.
6. Tests veille + déclencheurs événementiels (pistes) — plus tard.

## Contexte à ne pas oublier
- **Veille = cumulative** : `rolling_state` sur le `Watch`, snapshot par `WatchRun`. Dédup RSS via l'union des `WatchRun.new_article_urls`.
- Sortie LLM veille = **délimiteurs** (pas JSON) : `_parse` dans `engine.py`.
- Un run de veille débite les crédits (`watch.analysis_type`) — d'où l'épuisement en test.
- Snapshots clés : `snapshot_2026-08-14_14-45.md` (Qdrant+chat e2e), celui-ci (veille intelligente).
