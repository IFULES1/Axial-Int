# Conversations v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire des Conversations une vraie conversation (mémoire de fil), donner à l'utilisateur les retours et les commandes qui manquent (crédits, contexte, documents, gestion, régénérer/éditer/stopper, coût), rendre l'app utilisable sur mobile, et solder la dette backend (routage réel, coûts, idempotence, facturation partielle, notifications d'erreur, code mort).

**Architecture:** Backend FastAPI (`app/modules/intelligence/`), une migration `0022_conversations_v2`, `llm_client` étendu avec un historique, SSE enrichi (étapes, avertissements, solde). Front Next.js monolithe `frontend/app/_prototype/App.jsx` + `bridge.js` + nouveau module `markdown.js`, CSS `globals.css`. Tests pytest (SQLite mémoire, LLM simulé) et tests Node pour le markdown.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Anthropic/Gemini SDK (stream), React 18 / Next 14, SSE.

**Spec:** `docs/superpowers/specs/2026-09-10-conversations-v2.md` — l'autorité ; chaque tâche cite ses sections.

## Global Constraints

- Registre : vouvoiement pour tout texte d'app et contenu généré ; les emails de Miradie tutoient ; l'email de notification d'erreur est technique et vouvoie.
- Zéro régression : `PYTHONPATH=. .venv/bin/pytest -q` vert, `.venv/bin/ruff check app tests` propre, `cd frontend && npm run build` → `✓ Compiled successfully`, `cd frontend && npm test` vert (à partir de la Task 6).
- i18n : toute chaîne visible via `t('clé')` (FR + EN) ou `libelle()` + `LABELS_EN` ; aucune chaîne française en dur dans le JSX.
- Aucune nouvelle dépendance npm ; côté Python, aucune nouvelle dépendance non déjà présente dans `requirements.txt`.
- Ne rien inventer : pas de données, pas de prix, pas d'URL. Les tarifs viennent de `axPlans()`.
- Le build Next ne détecte pas les identifiants indéfinis : après toute suppression, grep de chaque identifiant/clé/classe retiré.
- Ne jamais lancer `npm run build` pendant qu'un `next dev` tourne sur le même dossier.
- Migrations : une seule, `alembic/versions/0022_conversations_v2.py`, réversible (`downgrade` complet), `down_revision = "0021_viz"`.
- Jamais de push, jamais de déploiement depuis une tâche d'implémentation.
- Les implémenteurs ne lancent pas de sous-agents.

---

### Task 1 : Socle backend — migration, modèles, routage réel, coûts de recherche, dette simple

**Spec :** §0 (agents public, prévisualisation, projet), §5.1, §5.2, §5.6, §5.7, §5.9 (partiel), §9.

**Files:**
- Create: `alembic/versions/0022_conversations_v2.py`
- Modify: `app/modules/intelligence/models.py`, `app/modules/intelligence/personas.py`, `app/modules/intelligence/service.py`, `app/modules/intelligence/router.py`, `app/modules/intelligence/export.py`, `app/modules/integrations/notion_context.py`, `app/modules/metrics/service.py`, `app/shared/search/__init__.py` (ou le module qui expose `search(query, k, compteur=...)` — vérifier la signature utilisée par `analysis/service.py:78-100`)
- Test: `tests/test_conversations_v2.py` (nouveau), `tests/test_intelligence.py`, `tests/test_analysis.py`

**Interfaces produites (utilisées par les tâches suivantes) :**
- `messages` : colonnes `statut: str = "complet"` (`complet|partiel|degrade`), `cle_idempotence: str | None` (unique), `cout_recherche_micro_eur: int | None`, `appels_recherche: int | None`.
- `conversations` : `resume: str | None`, `pinned_at`, `archived_at` (DateTime tz, nullable), `default_agent` défaut `"auto"`.
- `personas.DEFAULT_AGENT == personas.AUTO`.
- `service.TITRES_GENERIQUES` (seule source, `export.py` l'importe ; `_TITRES_PAR_DEFAUT` supprimé, valeurs `"nouvelle analyse"`/`"new analysis"` ajoutées à `TITRES_GENERIQUES`).

- [ ] **Step 1 : migration + modèles** — colonnes ci-dessus ; `downgrade` retire tout ; `PYTHONPATH=. .venv/bin/alembic upgrade head` sur la base locale (`.env`) puis `alembic current` = `0022_conversations_v2`.
- [ ] **Step 2 : routage réel** — dans `_prepare_turn`, remplacer le court-circuit `free_chat → AXIAL_CONSEIL` par `agent_key, redirect_note = personas.route(content, requested=requested)` pour tous les cas ; `free_chat` reste vrai quand `requested == AUTO` (il conditionne seulement le system prompt sans « AXIAL Recommande » et l'heuristique de tier) ; `DEFAULT_AGENT = AUTO` ; `conv.default_agent` défaut `auto`. Tests : `test_auto_route_macro_vers_market_scanner`, `test_auto_route_concurrence_vers_competitor_radar`, `test_auto_generique_vers_conseiller` **en appelant `_prepare_turn`** sur SQLite mémoire avec `llm_client` monkeypatché (s'inspirer de `tests/test_registre.py:155-197`).
- [ ] **Step 3 : `/agents` authentifié, `/agents/route` supprimé** — `RouteIn` supprimé ; test : `client.get("/intelligence/agents")` → 401/403 sans jeton ; `"/intelligence/agents/route" not in openapi paths`.
- [ ] **Step 4 : coût de recherche** — `_prepare_turn` passe un compteur à `web_search.search(...)` exactement comme `analysis/service.py:78-100` ; `_finalize_turn` persiste `appels_recherche` et `cout_recherche_micro_eur` (même calcul que `analysis`) ; `metrics/service.py:179-180` lit la colonne pour `messages`. Test : un tour avec recherche simulée (2 appels) persiste `appels_recherche == 2` et un coût > 0 ; `couts_totaux` inclut ce coût pour le poste `conversations`.
- [ ] **Step 5 : dette simple** — `export.py` importe `TITRES_GENERIQUES` ; cache Notion : TTL 600 s + purge au-delà de 200 entrées, commentaire « un seul worker uvicorn en prod » ; `message_count` recalculé par une fonction `_recompter(db, conv)` (utilisée par Task 3). Tests : `test_export_utilise_les_titres_generiques_du_service`, `test_cache_notion_borne`.
- [ ] **Step 6 : vérifications + commit** — pytest, ruff ; commit « Conversations v2 : socle backend (migration 0022, routage réel, coûts de recherche, dette) ».

---

### Task 2 : Pipeline de message — mémoire de fil, flux enrichi, statuts, idempotence, coût exposé

**Spec :** §1, §2 (côté backend), §3 (événements), §5.3, §5.4, §5.5, §5.8 (messages), §4 (Stop, coût).

**Files:**
- Modify: `app/shared/llm_client/__init__.py`, `app/shared/llm_client/claude.py`, `app/shared/llm_client/gemini.py`, `app/modules/intelligence/service.py`, `app/modules/intelligence/router.py`
- Test: `tests/test_conversations_v2.py`, `tests/test_troncature.py`

**Interfaces :**
- `llm_client.generate(..., history: list[dict] | None = None)` et `stream_text(..., history=None)` ; `history` = `[{"role": "user"|"assistant", "content": str}]`, transmis à Claude (`messages = history + [user prompt]`) et Gemini (`contents` avec `role: "user"|"model"`).
- `claude.stream` et `gemini.stream` deviennent des générateurs qui, après le dernier chunk, exposent `stop_reason` via un attribut de retour (`return stop_reason` capturé par `stream_text` avec `yield from`) ; `stream_text` renvoie `stop_reason` de la même façon.
- SSE : événements `{"step":"etape","etape":"recherche"|"sources"|"redaction","detail":{...}}`, `{"step":"avertissement","code":"contexte_absent"}`, `{"step":"sources",...}` (inchangé), `{"step":"delta",...}`, `{"step":"done","done":true,"data":{...,"balance":<int|null>,"statut":"complet|partiel|degrade"}}`.
- `MessageOut` : `+ statut, tokens_entree, tokens_sortie, credits: int` (2 si `complet`, sinon 0), `cout_micro_eur` **uniquement si `user.is_admin`** (sinon `None`).
- `GET /intelligence/conversations/{id}/cout` → `{credits, tokens_entree, tokens_sortie, cout_micro_eur (admin) , messages}`.
- `POST …/messages/stream` et `…/messages` acceptent l'en-tête `X-Idempotency-Key` ; `MessageIn` inchangé.
- `GET …/messages?limit=50&before=<message_id>` → les `limit` messages antérieurs à `before` (ou les derniers), ordre chronologique ; réponse enveloppée `{items, has_more}`.

- [ ] **Step 1 : historique** — `_prepare_turn` construit `history` = 8 derniers messages de la conversation (hors le message utilisateur courant), contenu tronqué à 1 500 caractères, blocs ```viz retirés (regex), préfixe `> ℹ️` retiré ; si `conv.resume`, le prompt commence par « Résumé de la conversation jusqu'ici :\n{resume}\n\n ». `_Turn` porte `history`. Les appels `generate`/`stream_text` reçoivent `history`. Tests : `test_historique_8_derniers_messages_envoyes`, `test_resume_injecte_au_dela_de_8`, `test_viz_retire_de_l_historique`.
- [ ] **Step 2 : résumé roulant** — après `_finalize_turn`, si `conv.message_count > 8`, `_mettre_a_jour_resume(db, conv)` appelle `llm_client.generate(tier="chat", max_tokens=900)` avec les messages 0..N-8 + ancien résumé → `conv.resume` (≤ 600 mots) ; toute exception est absorbée (log). Appelé en fin de flux, après l'événement `done` (l'utilisateur n'attend pas). Test avec LLM simulé.
- [ ] **Step 3 : étapes et avertissements** — `stream_message` émet `etape: recherche` avant la recherche, `etape: sources` avec `{"nombre": len(citations)}`, `etape: redaction` avant le premier chunk ; `avertissement: contexte_absent` si `company_context` vide. Pour cela `_prepare_turn` est découpé : `_preparer_contexte` (rapide, avant recherche) et `_rechercher` (lent), ou `stream_message` reçoit un callback `on_etape`. Test : ordre des événements sur un tour simulé.
- [ ] **Step 4 : statut partiel + Stop** — `stream_message` reçoit `request` ; dans la boucle des chunks, toutes les 10 itérations `await`-free : `if request_deconnecte(): break` (pour un générateur synchrone, passer une fonction `est_deconnecte` fournie par le routeur via `request.is_disconnected()` exécuté dans `anyio.from_thread` — si trop complexe, utiliser `StreamingResponse` avec un générateur **async** et `await request.is_disconnected()`). Sur coupure ou erreur après le premier chunk : `statut="partiel"`, texte conservé + note « (réponse interrompue) », **non facturé**. Sur réponse dégradée : `statut="degrade"`. `_finalize_turn` reçoit `statut`. Test : `test_flux_interrompu_est_partiel_et_non_facture`, `test_flux_survit_a_la_deconnexion_du_client` (le message partiel est bien archivé).
- [ ] **Step 5 : reprise sur troncature en flux** — si `stop_reason == "max_tokens"` : relancer `stream_text` avec `history + [assistant partiel]` et le prompt « Continue exactement où tu t'es arrêté, sans répéter. », jusqu'à 2 fois, en continuant à émettre des `delta`. Test avec un flux simulé qui renvoie `max_tokens` une fois.
- [ ] **Step 6 : idempotence** — si `X-Idempotency-Key` présent et qu'un message assistant de cette conversation porte cette clé, renvoyer ce message (flux : un seul événement `done` avec `data`), sans débit ; sinon stocker la clé sur le message assistant. Contrainte unique en base. Test : deux envois avec la même clé → un seul débit, un seul couple de messages.
- [ ] **Step 7 : taille, solde, coût, pagination** — `MessageIn.content` max 6 000 caractères → 413 `message_trop_long` ; `done.data.balance` = solde après débit (`billing.get_balance` ou équivalent existant) ; `MessageOut` enrichi ; `GET …/cout` ; `GET …/messages` paginé. Tests correspondants.
- [ ] **Step 8 : vérifications + commit** — pytest, ruff ; commit « Conversations v2 : mémoire de fil, flux par étapes, statuts et idempotence, coût exposé ».

---

### Task 3 : Gestion des conversations et des dossiers (backend)

**Spec :** §0 (projet), §4 (renommer, supprimer, archiver, épingler, dossiers, chercher, régénérer, éditer), §5.9.

**Files:**
- Modify: `app/modules/intelligence/router.py`, `app/modules/intelligence/service.py`, `app/modules/documents/router.py`, `app/modules/documents/service.py`
- Test: `tests/test_conversations_v2.py`

**Interfaces :**
- `PATCH /intelligence/conversations/{id}` body `{title?, pinned?, archived?, project_id?}` → `ConversationOut` (+ `pinned_at`, `archived_at`, `project_id`, `resume` absent).
- `DELETE /intelligence/conversations/{id}` → 204.
- `PATCH /intelligence/projects/{id}` `{name?, archived?}` ; `DELETE /intelligence/projects/{id}` (refusé 409 si des conversations non archivées y restent).
- `GET /intelligence/projects/{id}/conversations?inclure_archivees=false&limit=100`.
- `GET /intelligence/conversations/search?q=` → `[{conversation_id, title, project_id, extrait, message_id, created_at}]` (ILIKE sur `messages.content` et `conversations.title`, 20 max, `q` ≥ 3 caractères sinon 400).
- `POST /intelligence/conversations/{id}/messages/{message_id}/regenerer` → SSE identique à `messages/stream` : supprime le message assistant `message_id` (doit être le dernier), relance avec le message utilisateur précédent.
- `POST /intelligence/conversations/{id}/messages/{message_id}/editer` body `{content}` → SSE : supprime `message_id` (rôle user) et tout ce qui suit, puis déroule un tour normal avec `content`.
- `POST /documents/{id}/reindexer` → relance l'indexation ; `DocumentOut` expose déjà `chunk_count`.
- `message_count` recalculé après suppression/édition (`_recompter` de Task 1).

- [ ] **Step 1** : endpoints PATCH/DELETE conversations + projets, avec tests (propriété : un autre utilisateur → 404).
- [ ] **Step 2** : recherche, avec test (extrait de ±80 caractères autour du terme).
- [ ] **Step 3** : régénérer et éditer (factoriser avec `stream_message` : une fonction `_derouler_tour(...)` partagée), tests : nombre de messages après régénération inchangé, après édition = index + 2.
- [ ] **Step 4** : réindexation document, test avec l'indexation simulée.
- [ ] **Step 5** : pytest, ruff, commit « Conversations v2 : gestion des conversations et dossiers, recherche, régénérer, éditer ».

---

### Task 4 : Notification d'erreur backend par email

**Spec :** §5.10.

**Files:**
- Create: `app/shared/notifier.py`
- Modify: `app/errors.py`, `app/config.py`, `app/modules/intelligence/service.py` (appels `notifier_erreur` sur génération échouée / flux coupé), `.env.example`
- Test: `tests/test_notifier.py`

- [ ] **Step 1** : `notifier_erreur(*, titre, route, methode, user_email, exc, action)` — construit le corps (compte, route, horodatage UTC, traceback tronqué à 4 000 caractères, action suggérée), déduplique par `sha1(route+type(exc).__name__)` sur 3 600 s (dict en mémoire), envoie via `app.modules.emailing.envoi.envoyer` à `settings.erreurs_notif_destinataire` (défaut `miradie.buranturu@axial-ia.fr`) si `settings.erreurs_notif_actives` (défaut `True`, `False` en tests via fixture). Jamais d'exception propagée.
- [ ] **Step 2** : brancher dans `errors.py` (gestionnaire `Exception`) avec l'utilisateur courant si disponible (lire le jeton sans lever) ; brancher dans `service.py` sur `Agent stream failed` et `generate failed`.
- [ ] **Step 3** : tests : envoi simulé appelé une fois pour deux erreurs identiques dans l'heure, deux fois pour deux routes différentes, zéro fois si désactivé, et le gestionnaire renvoie toujours 500 JSON.
- [ ] **Step 4** : pytest, ruff, commit « Erreurs backend : notification email dédupliquée ».

---

### Task 5 : Front — bridge, erreurs nommées, garde-fous et retours à l'utilisateur

**Spec :** §2, §5.11 (bridge), §8.

**Files:**
- Modify: `frontend/app/_prototype/bridge.js`, `frontend/app/_prototype/App.jsx`, `frontend/app/globals.css`

**Interfaces :**
- `bridge.js` : `lireFluxSSE(res, onEvent)` partagé par `axStreamChatIn` et `axStreamAnalysis` ; `axStreamChatIn(cid, text, onEvent, {signal, idempotencyKey})` ; nouvelles fonctions `axRenommerConversation`, `axSupprimerConversation`, `axEpinglerConversation`, `axArchiverConversation`, `axDeplacerConversation`, `axProjets`, `axCreerProjet`, `axRenommerProjet`, `axArchiverProjet`, `axRechercherConversations`, `axRegenerer(cid, msgId, onEvent, opts)`, `axEditerMessage(cid, msgId, content, onEvent, opts)`, `axCoutConversation`, `axMessagesPage(cid, {limit, before})`, `axReindexerDocument` ; suppression de `axChat`, `axNewConversation`, `_convId`, `ensureConversation` (remplacé par `axProjetParDefaut()` qui crée « Général » si besoin).
- `decrireErreur(e, t)` → `{titre, detail, action: 'credits'|'reconnexion'|'reessayer'|null}` dans App.jsx.

- [ ] **Step 1** : bridge : factorisation SSE, en-tête `X-Idempotency-Key` (`crypto.randomUUID()`), `AbortSignal`, nouvelles fonctions, suppression du code mort (grep).
- [ ] **Step 2** : garde de crédits avant envoi (`axBal < 2`) → composant `ModaleCredits` (titre « Plus de crédits disponibles », boutons « Acheter des crédits » → route `credits`, « Voir les abonnements » → route `credits`, « Fermer ») ; même modale sur 402 ; solde mis à jour depuis `done.data.balance`.
- [ ] **Step 3** : bandeau « profil entreprise vide » au-dessus du composer (état `profil` déjà chargé pour les suggestions) avec lien vers Mémoire/Profil ; masqué dès que `company_name` existe.
- [ ] **Step 4** : documents : bouton d'import désactivé à 3 documents en attente + infobulle ; erreur d'import affichée (texte de l'API) ; badge « non lisible » si `chunk_count === 0` avec bouton « Réindexer ».
- [ ] **Step 5** : `maxLength` 6 000 + compteur à partir de 5 000 ; session expirée pendant un envoi → `axClearToken()` + route `login` + message « Votre session a expiré, reconnectez-vous » ; suggestions de repli FR/EN via `t()`.
- [ ] **Step 6** : `decrireErreur` + rendu des erreurs dans le fil comme carte (titre, détail, bouton d'action) — plus jamais `'⚠️ ' + e.message` ; bandeau « Réponse partielle » quand `statut !== 'complet'`.
- [ ] **Step 7** : build, grep, commit « Conversations v2 : bridge factorisé, erreurs nommées, garde-fous et retours ».

---

### Task 6 : Markdown complet (module + tests Node)

**Spec :** §7.

**Files:**
- Create: `frontend/app/_prototype/markdown.js`, `frontend/tests/markdown.test.mjs`
- Modify: `frontend/app/_prototype/App.jsx` (`MarkdownView` consomme le module), `frontend/package.json` (`"test": "node --test tests/"`), `frontend/app/globals.css`

- [ ] **Step 1** : `parserMarkdown(texte) → blocs[]` pur (sans React) : titres, paragraphes, listes puces/numérotées (un niveau d'imbrication), blocs de code (langue), citations `>`, séparateurs, tableaux ; inline : gras, italique, code, liens, citations `[N]`, blocs ```viz conservés comme bloc `viz`.
- [ ] **Step 2** : tests Node (≥ 15 cas, dont liste numérotée, lien, code inline, bloc de code, tableau, viz, texte brut sans markdown).
- [ ] **Step 3** : `MarkdownView` rend les blocs (liens `target=_blank rel=noopener`, bloc de code avec `BoutonCopier`) ; comportement identique pour les tableaux et viz existants.
- [ ] **Step 4** : `npm test`, build, commit « Conversations v2 : markdown complet, testé ».

---

### Task 7 : Front — affichage du flux, Stop, verrous, agent, coût

**Spec :** §3, §4 (Stop, coût, verrous), §0 (badge agent).

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`, `frontend/app/globals.css`

- [ ] **Step 1** : suppression de l'animation locale (`streamingSpeed`, `shown`) ; le contenu affiché ne se réinitialise jamais ; le payload final complète (viz, citations, statut, coût).
- [ ] **Step 2** : bandeau d'étapes (`etape` events) : « Recherche web… », « N sources lues », « Rédaction… » + compteur de secondes ; disparaît au premier `delta`.
- [ ] **Step 3** : auto-défilement sur la longueur du contenu si l'utilisateur est en bas, sinon bouton « ↓ » ; skeleton pendant `axMessages` ; « Charger les messages précédents » (pagination).
- [ ] **Step 4** : Stop (AbortController, bouton remplace Envoyer pendant le flux), composer verrouillé pendant le flux du fil courant ; changement d'agent dans un fil existant → note système « Agent changé : … » (message local `role: 'system'`) ; badge de l'agent qui a répondu sur chaque réponse, y compris en mode auto.
- [ ] **Step 5** : pastille coût sous chaque réponse (« 2 crédits · 3,1 k tokens », € pour admin) et total dans l'en-tête (`axCoutConversation`).
- [ ] **Step 6** : build, grep, commit « Conversations v2 : flux lisible, Stop, verrous, coût visible ».

---

### Task 8 : Front — gestion des conversations et dossiers

**Spec :** §4 (gestion, recherche, régénérer, éditer), §0 (dossiers).

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`, `frontend/app/globals.css`

- [ ] **Step 1** : `ConvListPanel` : sections « Épinglées », dossiers (projets) repliables, « Archivées » (repliée), menu ⋯ par conversation (Renommer inline, Épingler, Archiver, Déplacer vers…, Supprimer avec confirmation) ; « Nouveau dossier », menu ⋯ par dossier (Renommer, Archiver).
- [ ] **Step 2** : recherche : ≥ 3 caractères → `axRechercherConversations` (debounce 300 ms) avec extraits ; sinon filtre local sur le titre.
- [ ] **Step 3** : Régénérer (sous la dernière réponse) et Éditer (crayon sur une bulle utilisateur → textarea inline → renvoi) via les endpoints SSE ; les messages suivants disparaissent localement puis se reconstruisent.
- [ ] **Step 4** : build, grep, commit « Conversations v2 : dossiers, épingles, archives, recherche, régénérer et éditer ».

---

### Task 9 : Mobile responsive (priorité)

**Spec :** §6.

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`, `frontend/app/globals.css`

- [ ] **Step 1** : conversations : sous 768 px, `.conv-list-panel` en tiroir (attribut `data-convlist-mobile`, bouton « Conversations » dans la topbar, voile, fermeture au choix d'un fil) ; `.app-body` une colonne ; composer collé en bas ; bulles 100 % ; tableaux/viz dans `overflow-x:auto` ; panneau de citation plein écran.
- [ ] **Step 2** : passe générale à 375 px sur chaque `subRoute` (rapports, agents, mémoire, crédits, documentation, paramètres, pilotage) : aucun débordement horizontal (`document.documentElement.scrollWidth <= innerWidth`), grilles en une colonne, tableaux scrollables, topbar sans débordement, modales à 92 vw.
- [ ] **Step 3** : vérification : lister dans le rapport, pour chaque surface, `scrollWidth`/`innerWidth` mesurés dans le navigateur (le contrôleur fournit l'URL locale) ou, à défaut, la lecture des règles CSS.
- [ ] **Step 4** : build, commit « Front : mobile responsive (tiroir des conversations, passe générale) ».

---

### Task 10 : Déploiement et parcours réel

- [ ] Rsync backend + front, `alembic upgrade head` sur le VPS (vérifier `alembic current` = `0022_conversations_v2` et les colonnes), tests serveur, restarts, `npm run build`, bundle vérifié, restart front.
- [ ] Parcours réel : inscription neuve ; conversation à 3 tours dont « développe le point 2 » ; Stop ; régénérer ; éditer ; renommer / épingler / archiver / supprimer ; dossier ; recherche ; solde qui bouge ; modale crédits (compte à 0 crédit via l'admin) ; mobile 375 px sur toutes les surfaces ; email de notification d'erreur (provoquer une 500 contrôlée sur un endpoint de test ou via un id malformé volontairement non géré, puis retirer).
- [ ] Snapshot mémoire + push.
