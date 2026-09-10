# Bilan factuel — backend « conversations » (10/09/2026)

Périmètre : `app/modules/intelligence/` (models, router, service, personas,
export) et tout ce que le pipeline de message appelle en aval — documents,
mémoire, RAG, recherche web, LLM, viz, PII, billing, metrics. Lecture seule,
aucune modification. Objectif : décrire ce qui existe réellement, pas ce qui
devrait exister.

---

## 1. Modèle de données

Fichier : `app/modules/intelligence/models.py`. Trois tables, alignées sur la
hiérarchie `Project → Conversation → Message`, créées par
`alembic/versions/0002_intelligence.py` (10/08/2026) et complétées par deux
migrations ultérieures.

### `projects` (models.py:22-34)

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID, indexé | pas de FK vers `auth.users` (Supabase gère l'auth séparément) |
| `name` | String(200) | |
| `description` | Text, nullable | |
| `created_at` | DateTime(tz) | |
| `archived_at` | DateTime(tz), nullable | **colonne présente mais jamais écrite** — voir §4 |

Relation : `conversations` en cascade `all, delete-orphan` (models.py:32-34) —
supprimer un projet supprimerait ses conversations et messages en cascade,
mais rien dans le code n'appelle jamais cette suppression (§4).

### `conversations` (models.py:37-54)

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | UUID, FK `projects.id` ON DELETE CASCADE, indexé | |
| `user_id` | UUID, indexé | dupliqué depuis `project.user_id` (dénormalisé, jamais vérifié en cohérence) |
| `title` | String(300), défaut `"Nouvelle conversation"` | |
| `default_agent` | String(64), défaut `"market_scanner"` | |
| `message_count` | Integer, défaut 0 | incrémenté de 2 à chaque tour (user+assistant), jamais recalculé depuis `messages` |
| `created_at` | DateTime(tz) | |
| `last_message_at` | DateTime(tz), nullable | |

### `messages` (models.py:57-79)

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `conversation_id` | UUID, FK CASCADE, indexé | |
| `role` | String(16) | `"user"` \| `"assistant"` — pas de contrainte CHECK en base |
| `agent` | String(64), nullable | persona qui a répondu (ou qui a posé la question, cf §3) |
| `content` | Text, défaut `""` | |
| `citations` | JSON/JSONB, nullable | liste de dicts `{title, url, domain, source, excerpt, reference}` |
| `viz` | JSON/JSONB, nullable | blocs de visualisation pré-compilés (ajouté par `0021_viz.py`) |
| `tokens_entree`, `tokens_sortie` | Integer, nullable | absents pour les messages antérieurs au 25/08/2026 (commentaire ligne 71-72) |
| `cout_micro_eur` | Integer, nullable | coût du **modèle seul** — le coût de recherche web n'est jamais mesuré pour un message (voir §3 et §7) |
| `modele` | String(64), nullable | ex. `claude-sonnet-5`, `gemini-flash-latest` |
| `created_at` | DateTime(tz) | |

Pas de colonne `updated_at` sur `Message` — un message n'est jamais modifié
après création (pas d'édition côté serveur).

### Migrations qui touchent ces tables

| Fichier | Contenu |
|---|---|
| `0002_intelligence.py` | création des 3 tables + index `user_id`/`project_id`/`conversation_id` |
| `0019_couts_chat_veille.py:17-34` | ajoute `tokens_entree`, `tokens_sortie`, `cout_micro_eur`, `modele` sur `messages` **et** `watch_runs` ; ajoute `cout_recherche_micro_eur` + `appels_recherche` sur **`reports`** et **`watch_runs`** uniquement — **pas sur `messages`** |
| `0021_viz.py:20-31` | table `viz_rendus` (cache par empreinte SHA-256) + colonne `viz` sur `reports` et `messages` |

Aucune contrainte d'unicité, aucun index composite (`conversation_id, created_at`)
au-delà de l'index simple sur `conversation_id` — le tri par date (§4) dépend
d'un scan trié côté Postgres sans index dédié.

---

## 2. Surface API

Fichier : `app/modules/intelligence/router.py`, préfixe `/intelligence`. Tous
les endpoints métier exigent `get_current_user` (JWT Supabase/local) sauf
`GET /intelligence/agents`.

| Méthode | Route | Auth | Payload | Réponse | Ligne |
|---|---|---|---|---|---|
| GET | `/intelligence/agents` | publique | — | `{agents:[{key,name,framework}]}` | router.py:73-78 |
| POST | `/intelligence/agents/route` | user | `RouteIn{query, agent?}` | `{agent, name, redirect_note}` — **ne persiste rien**, sert juste à prévisualiser le routage côté frontend | router.py:81-85 |
| POST | `/intelligence/projects` | user | `ProjectIn{name, description?}` | `ProjectOut` | router.py:90-94 |
| GET | `/intelligence/projects` | user | — | `list[ProjectOut]`, tri `created_at desc`, **pas de pagination** | router.py:97-103 |
| POST | `/intelligence/projects/{project_id}/conversations` | user | `ConversationIn{title?, default_agent?}` | `ConversationOut` | router.py:108-115 |
| GET | `/intelligence/projects/{project_id}/conversations` | user | — | `list[ConversationOut]`, tri `created_at desc`, **pas de pagination** | router.py:118-126 |
| POST | `/intelligence/conversations/{conversation_id}/messages/stream` | user | `MessageIn{content, agent?, document_ids?}` | `StreamingResponse` SSE (`text/event-stream`) | router.py:131-144 |
| GET | `/intelligence/conversations/{conversation_id}/messages` | user | — | `list[MessageOut]`, tri `created_at asc`, **pas de pagination** (tout l'historique à chaque appel) | router.py:152-155 |
| POST | `/intelligence/conversations/{conversation_id}/messages` | user | `MessageIn` | `MessageOut` (bloquant, non-stream) | router.py:158-165 |
| GET | `/intelligence/conversations/{conversation_id}/export?format=md\|pdf` | user | — | fichier téléchargeable (`Content-Disposition: attachment`) | router.py:168-205 |

Pas de route `DELETE`, `PUT` ni `PATCH` dans ce fichier — confirmé par
recherche (`grep "@router\.\(delete\|put\|patch\)"` → aucun résultat).
Aucun endpoint de suppression/renommage/archivage de conversation ou de
projet n'existe côté serveur (détail au §4).

### Modules appelés par le pipeline de message (hors intelligence/)

| Module | Rôle | Résilience si indisponible |
|---|---|---|
| `app/modules/documents/service.py:get_document` | contenu des pièces jointes du message (`document_ids`, max 3, 8000 car. chacune) | `try/except` large : un document illisible est simplement ignoré (service.py:154-158) |
| `app/modules/memory/service.py:build_context` | contexte entreprise (profil) injecté dans le prompt | retourne `""` si pas de profil, jamais d'exception propagée |
| `app/modules/rag/service.py:retrieve` | passages internes (Qdrant, collections `documents` + `knowledge_base`) | `try/except Exception` dans `_retrieve_context` (service.py:111-118), log + `("", [])` |
| `app/shared/search/orchestrator.py:search` | recherche web (Exa/Tavily/Linkup) | chaque provider échoue silencieusement (`search/providers.py`), orchestrateur retourne `[]` si tout échoue |
| `app/modules/integrations/notion_context.py:passages_pour` | pages Notion de l'utilisateur (si connecté) | `try/except Exception` (service.py:266-267), n'interrompt jamais le tour |
| `app/modules/pii/client.py:guard_outbound` | anonymisation du prompt avant envoi au LLM (mode `off`/`shadow`/`enforce`, défaut `shadow` — donc envoi de texte **non modifié** en pratique, cf config.py:126) | best-effort, Presidio indisponible → repli regex seul |
| `app/modules/billing/service.py:check_credits` / `consume_credits` | vérification puis débit de crédits | lève `AppError 402` **avant** l'appel LLM si le solde est insuffisant (non-admin) |
| `app/modules/viz/service.py:preparer_sans_faute` | extraction/compilation des blocs `\`\`\`viz` de la réponse | `try/except Exception` explicite, ne bloque jamais l'archivage (service.py:33-40) |
| `app/shared/llm_client/__init__.py:generate` / `stream_text` | génération (Claude/Gemini, bascule automatique) | voir §3 |

---

## 3. Pipeline de message (`app/modules/intelligence/service.py`)

### 3.1 Routage des personas (`personas.py`)

Trois personas dans le registre (`personas.py:152-158`) :
`market_scanner` (PESTEL), `competitor_radar` (Porter), `conseiller` (Axial
Conseil, généraliste). `DEFAULT_AGENT = "market_scanner"` (personas.py:158),
`AUTO = "auto"` (personas.py:162) désigne le mode « conversation libre ».

- Si `requested == AUTO` (ou absent) → routage par score de mots-clés
  (`_score`, personas.py:173-175) : le persona au score le plus haut répond ;
  score nul partout → `conseiller` par défaut. **Jamais** de note de
  redirection dans ce mode (personas.py:198-201).
- Si `requested` est un persona explicite → le choix est **toujours respecté**
  (jamais forcé), mais si la question correspond visiblement à l'autre
  spécialiste (`scores[other] >= 2` et supérieur au score du persona demandé),
  une `redirect_note` textuelle est renvoyée et préfixée à la réponse
  (`service.py:349-350`, `> ℹ️ {note}`).

`service.py:_prepare_turn` (196-335) réintroduit une distinction : si
`requested == AUTO`, c'est en réalité **toujours** `conseiller` qui répond
(`free_chat = True` → `agent_key = AXIAL_CONSEIL.key` directement,
service.py:204-206) — la fonction `personas.route` n'est appelée que pour les
choix explicites (service.py:208). Autrement dit, le routage multi-agents
« intelligent » de `personas.route` (personas.py:178-201) sur `AUTO` n'est
**jamais atteint** par le chemin `AUTO` du chat : il n'est exercé que par
`POST /intelligence/agents/route` (endpoint de prévisualisation, §2) et par
les tests (`test_intelligence.py:37-41`). Dans le produit réel, la
« conversation libre » ne route jamais vers Market Scanner ou Competitor
Radar — c'est toujours Axial Conseil qui répond, avec un prompt sans le bloc
« AXIAL Recommande » (service.py:290-296).

### 3.2 Historique — **aucun envoyé au LLM**

Le prompt envoyé au modèle est construit uniquement à partir du **message
courant** : contexte entreprise + documents joints + sources (web/RAG/Notion)
+ la question (service.py:272-277). L'appel LLM (`claude.py:49-52`,
`gemini.py:31-34`) envoie `messages=[{"role":"user","content":prompt}]` —
un seul message, jamais un tableau reconstruit depuis `messages` de la
conversation. Il n'existe **aucune fonction de troncature d'historique**
(`app/modules/*/troncature*` n'existe pas — recherche infructueuse) car il
n'y a pas d'historique à tronquer : chaque tour est stateless du point de vue
du modèle, seul le contexte entreprise (mémoire) et les documents joints
apportent de la continuité. Une conversation à 20 messages n'a donc, pour le
LLM, pas plus de mémoire qu'un message isolé — sauf ce qui est explicitement
réinjecté (profil, docs joints).

### 3.3 Construction du contexte (`_prepare_turn`, service.py:196-335)

Ordre des opérations :
1. Résolution de la conversation + du persona (§3.1).
2. Vérification des crédits (`billing.check_credits`, non-admin) — **avant**
   tout appel réseau coûteux (service.py:214-220).
3. Persistance immédiate du message utilisateur (service.py:223-225) —
   indépendante du succès de la génération.
4. Titre auto si première question et titre générique (§4).
5. `company_context = memory.build_context(...)`.
6. `attached_context = _attached_docs_context(...)` (documents joints, max 3,
   8000 caractères chacun).
7. Heuristique « trivial » : message libre, <25 caractères, pas de pièce
   jointe → **aucune recherche RAG ni web** (service.py:238-243) — réponse
   immédiate.
8. Sinon, RAG et recherche web lancées **en parallèle** via
   `ThreadPoolExecutor(max_workers=2)` (service.py:246-256) ; chaque échec est
   absorbé (log + liste vide), jamais fatal.
9. Passages Notion ajoutés au pool si l'utilisateur a connecté son espace
   (service.py:260-267).
10. `grounding.assemble` (app/shared/grounding.py:19-75) fusionne web + RAG +
    Notion en **un seul pool numéroté**, dédupliqué par clé de contenu, classé
    par un reranker (`web_search.rerank_indices`) — c'est cette liste finale
    qui devient à la fois le bloc `Sources (classées par pertinence)` du
    prompt et la liste `citations` persistée sur le message assistant.
11. `guard_outbound` (PII) appliqué au prompt final avant envoi.

### 3.4 Assemblage du system prompt

- Conversation libre (`free_chat`) : `persona.system_prompt` (Axial Conseil)
  + `VIZ_INSTRUCTION` + `REGISTRE_INSTRUCTION` — **sans**
  `AXIAL_SHARED_RULES` ni `AXIAL_RECOMMENDE_INSTRUCTION`
  (service.py:294-296, personas.py:79-81).
- Agent spécialisé explicite : `persona.full_system_prompt()` = system +
  `AXIAL_SHARED_RULES` + `AXIAL_RECOMMENDE_INSTRUCTION` + `VIZ_INSTRUCTION`
  + `REGISTRE_INSTRUCTION` (personas.py:79-81).
- Si contexte entreprise présent : instruction supplémentaire forçant une
  phrase d'ouverture ancrée sur l'entreprise (service.py:298-310).
- Miroir de langue : `lg.consigne_miroir()` toujours ajouté
  (`app/shared/langue.py`, service.py:317-319) — la langue de la réponse suit
  celle de la question, indépendamment du réglage d'interface.
- Si des sources Notion figurent dans le pool : instruction dédiée
  « ESPACE DE TRAVAIL » (service.py:323-329).
- `VIZ_INSTRUCTION` (personas.py:30-42) : consigne conditionnelle, un seul
  bloc `\`\`\`viz` JSON au format `{version, intent, title, subtitle, unit,
  series, sources}`, uniquement si la réponse compare/classe/répartit des
  chiffres.

### 3.5 Choix du tier / modèle (`llm_client`)

- `tier="report"` (Claude d'abord, `claude-sonnet-5`, `max_tokens=16000`) si
  conversation libre **et** `_wants_long_answer` (>220 caractères ou mots-clés
  d'analyse — `service.py:131-142`).
- `tier="chat"` sinon (Gemini d'abord, `gemini-flash-latest`,
  `max_tokens=8000`) — c'est le cas pour **tous** les agents spécialisés,
  quelle que soit la longueur/complexité de la question (personas explicites
  → toujours tier `chat`, service.py:313).
- Bascule automatique **avant le premier token** seulement
  (`llm_client/__init__.py:84-122`) : si le flux a déjà commencé et que le
  provider tombe en cours de réponse, pas de bascule vers l'autre — l'erreur
  remonte et le texte déjà écrit est conservé avec un message d'interruption
  (service.py:461-463).
- Reprise automatique sur troncature (`claude.py:92-110`, jusqu'à 3 reprises)
  — ce mécanisme existe côté `claude.generate` (appel bloquant), **pas** côté
  `claude.stream` (streaming, `claude.py:149-176`) : une réponse tronquée en
  flux SSE n'est jamais reprise automatiquement, contrairement au chemin
  bloquant `post_message`.

### 3.6 Citations et viz

- `citations` = la liste `cite` produite par `grounding.assemble`, persistée
  telle quelle sur `Message.citations` (service.py:360-362).
- `viz` = extraction/compilation post-génération via
  `viz_service.preparer_sans_faute(db, answer)` (service.py:357-359),
  **jamais** en cas de réponse dégradée (`degraded=True` → `viz=None`).

### 3.7 Coût / crédits par message

- Coût de facturation : **fixe**, `agent_message` = 2 crédits
  (`billing/catalog.py:22`), indépendant du modèle utilisé, du nombre de
  tokens, ou de l'usage de recherche web. Débité uniquement si la réponse
  n'est pas dégradée (`service.py:376-382`).
- Coût *mesuré* (`cout_micro_eur`, pour le tableau de bord) : calculé
  uniquement sur les tokens du modèle (`couts.cout_micro_eur`,
  `service.py:366-367`) — **le coût des appels de recherche web
  (Exa/Tavily/Linkup) n'est jamais mesuré pour un message** : `_prepare_turn`
  appelle `web_search.search(content, 6)` sans le paramètre `compteur`
  (service.py:250, comparer à `analysis/service.py:78-100` qui, lui, passe
  `compteur=appels_recherche` et persiste `appels_recherche` /
  `cout_recherche_micro_eur` sur `reports`). La colonne
  `cout_recherche_micro_eur` existe sur `reports` et `watch_runs`
  (`0019_couts_chat_veille.py`) mais **n'a jamais été ajoutée à `messages`** —
  il n'y a même pas de colonne pour la stocker.
- Facturation liée à la génération : `analytics.increment_usage` appelé en
  parallèle du débit (service.py:377-382).

### 3.8 Chemins dégradés / erreurs

| Cas | Comportement |
|---|---|
| Aucun LLM disponible (`generation_available()` faux) | `blocked_answer` fixe, `degraded=True`, **persisté et non facturé** (service.py:283-288, 392-394) |
| `generate()` lève une exception (bloquant) | message d'erreur générique, `degraded=True`, non facturé (service.py:400-403) |
| `stream_text()` échoue avant le 1er chunk | message d'erreur générique, `degraded=True` (service.py:452-459) |
| `stream_text()` échoue après ≥1 chunk | le texte déjà produit est conservé + note d'interruption ajoutée, **archivé et facturé comme une réponse normale** (`degraded` reste `False` implicitement — service.py:461-465, 482) : incohérence avec le cas « échec avant 1er chunk » |
| Réponse vide en flux (0 token produit, pas d'exception) | détecté explicitement (`answer.strip()` vide), message dédié, `degraded=True`, non facturé (service.py:466-480) — corrige un bug de production daté du 03/09/2026 (commentaire) |
| Crédits insuffisants (non-admin) | `AppError 402 insufficient_credits`, **avant** tout appel LLM (service.py:214-220) |
| Projet/conversation inexistant ou d'un autre utilisateur | `AppError 404 not_found` (service.py:50-54, 83-93) |
| `conversation_id` non-UUID (id provisoire client) | `AppError 404`, pas de 500 (service.py:84-89, testé par `test_intelligence.py:70-79`) |

---

## 4. Titre, suppression, renommage, archivage, pagination, multi-projet

- **Titre automatique** : `titre_depuis(question, longueur=80)`
  (service.py:186-193) — première question, espaces normalisés, coupé sur un
  mot avec `…`. Appliqué **une seule fois**, à la première question, et
  seulement si le titre courant est dans `TITRES_GENERIQUES = {"", "workspace",
  "nouvelle conversation", "conversation", "new conversation"}`
  (service.py:183, 229-230). Pas de renommage automatique ultérieur (message
  2, 3…) : le titre reste figé après la première question. Corrige un
  problème documenté en commentaire (« 14 conversations sur 19 portaient ce
  nom », service.py:227-228).
- **Renommage manuel** : **aucun endpoint** ne permet de modifier `title`
  après création (pas de `PATCH`/`PUT` sur `/conversations/{id}`). Le champ
  `title` de `ConversationIn` n'est utilisable qu'à la création
  (router.py:34-36, 109-115).
- **Suppression** : **aucun endpoint** `DELETE` pour conversation, message ou
  projet. La cascade SQLAlchemy (`cascade="all, delete-orphan"`,
  models.py:32-34, 52-54) existe au niveau ORM mais n'est déclenchée par
  aucun code applicatif.
- **Archivage** : la colonne `Project.archived_at` existe et
  `list_projects` filtre déjà `Project.archived_at.is_(None)`
  (service.py:41-47) — mais **aucune fonction n'écrit jamais cette colonne** :
  impossible d'archiver un projet via l'API actuelle. Fonctionnalité à moitié
  câblée (lecture prête, écriture absente).
- **Pagination** : absente partout. `list_projects`, `list_conversations`,
  `list_messages` renvoient l'intégralité du résultat trié, sans `limit`,
  `offset`, ni curseur (service.py:41-47, 73-80, 96-103 ; router.py n'expose
  aucun paramètre de pagination). Une conversation à plusieurs centaines de
  messages est rechargée en entier à chaque `GET
  /conversations/{id}/messages`.
- **Multi-projet** : le modèle de données le permet pleinement
  (`Project 1—N Conversation`), et l'API l'expose (`POST/GET
  /intelligence/projects`). Mais rien côté serveur ne crée un « projet par
  défaut » pour un nouvel utilisateur — cette responsabilité, si elle existe,
  est entièrement côté frontend (non auditée ici, hors périmètre backend). Le
  backend reste agnostique : un utilisateur sans projet ne peut créer aucune
  conversation (`create_conversation` exige un `project_id` valide,
  service.py:59-70).

---

## 5. Persistance mi-flux, idempotence, 401 en cours de conversation

- **Déconnexion client pendant le streaming** : `stream_message` est un
  générateur Python ; FastAPI ferme la connexion mais le générateur
  **continue de s'exécuter côté serveur** jusqu'à son prochain `yield` ou sa
  fin — c'est le comportement standard de `StreamingResponse` avec un
  générateur synchrone tant que rien n'appelle explicitement `gen.close()` de
  façon précoce. `_finalize_turn` (appelé en toute fin, service.py:482-483)
  s'exécute donc même si le client a fermé l'onglet **à condition que le
  générateur aille jusqu'au bout** — ce qui est le cas ici puisque aucune
  vérification de déconnexion n'interrompt la boucle `for chunk in
  llm_client.stream_text(...)` (service.py:446-451). Un test analogue existe
  pour le module `analysis` (`tests/test_troncature.py:150-199`,
  `test_rapport_survit_a_la_fermeture_du_navigateur`) mais **aucun test
  équivalent n'existe pour `intelligence.stream_message`** (voir §6).
- **Idempotence** : aucune. Chaque appel à `POST
  .../messages` ou `.../messages/stream` crée un nouveau `Message` avec un
  nouvel `uuid.uuid4()` (service.py:223-224, et le message assistant
  service.py:360-361) — pas de clé d'idempotence côté client acceptée, pas de
  déduplication. Un double-clic ou un retry réseau côté frontend crée deux
  messages utilisateur et débite les crédits deux fois.
- **401 en cours de conversation** : `get_current_user` (auth/security.py:87-91)
  décode le JWT à chaque requête ; `decode_token` distingue
  `token_expired` (401) de `token_invalid` (401) (auth/security.py:65-68).
  Le serveur ne fait **aucun rafraîchissement de token** — c'est un principe
  affirmé et testé : `test_le_client_supabase_ne_rafraichit_jamais_de_session_cote_serveur`
  (tests/test_audit_sessions.py:15-21) vérifie explicitement que le client
  Supabase serveur a `auto_refresh_token=False` et `persist_session=False`,
  pour éviter qu'un minuteur de rafraîchissement tourne côté serveur et
  invalide le refresh token du navigateur. Concrètement : un token expiré
  pendant une conversation en cours produit un 401 sur la requête suivante
  (`POST .../messages` ou `.../messages/stream`), sans aucune tentative de
  reprise côté serveur — la charge du refresh + retry incombe entièrement au
  frontend, non audité ici.

---

## 6. Tests

Fichiers concernés : `tests/test_intelligence.py` (79 lignes),
`tests/test_registre.py` (partiellement), `tests/test_troncature.py`
(partiellement, un test dédié au chat), `tests/test_audit_sessions.py`
(partiellement).

### Ce qui est couvert

| Test | Fichier:ligne | Couvre |
|---|---|---|
| `test_macro_query_routes_to_market_scanner` | test_intelligence.py:10-13 | scoring de `personas.route` |
| `test_competitive_query_routes_to_competitor_radar` | test_intelligence.py:16-18 | idem |
| `test_non_overlap_redirect_note` | test_intelligence.py:21-29 | note de redirection sur choix explicite |
| `test_axial_recommande_in_system_prompt` | test_intelligence.py:32-34 | présence du bloc dans `full_system_prompt` |
| `test_generic_query_falls_to_conseil` | test_intelligence.py:37-40 | repli généraliste (mais teste `personas.route` directement — **jamais le chemin réel `AUTO` de `_prepare_turn`**, cf §3.1) |
| `test_explicit_choice_is_respected` | test_intelligence.py:44-47 | non-destructivité du choix explicite |
| `test_free_chat_tier_heuristic` | test_intelligence.py:50-57 | `_wants_long_answer` |
| `test_intelligence_routes_mounted` | test_intelligence.py:60-67 | routes montées + auth publique/protégée (vérifie juste les codes 200/401/403, pas les payloads) |
| `test_un_id_de_conversation_non_uuid_vaut_introuvable` | test_intelligence.py:70-79 | garde-fou 404 sur id non-UUID |
| `test_titre_depuis_la_question`, `test_titre_long_coupe_sur_un_mot`, `test_les_titres_generiques_sont_reconnus` | test_audit_sessions.py:62-79 | génération de titre |
| `test_conversation_libre_recoit_registre_instruction` | test_registre.py:155-197 | assemble réellement `_prepare_turn` sur SQLite en mémoire, vérifie l'injection de `REGISTRE_INSTRUCTION` sur le chemin libre — **seul test qui exécute `_prepare_turn` de bout en bout avec une vraie base**, mais reste sur le chemin `trivial` (message court, pas de RAG/web/Notion) |
| `test_reponse_de_chat_vide_non_facturee` | test_troncature.py:227-276 | non-facturation d'une réponse de flux vide |
| `test_le_client_supabase_ne_rafraichit_jamais_de_session_cote_serveur`, `test_les_autres_parametres_ne_sont_pas_masques`, `test_la_cle_api_est_masquee_dans_les_journaux` | test_audit_sessions.py | garde-fous auth/logs, pas spécifiques aux conversations mais exercés par ce pipeline |

### Ce qui n'est PAS couvert (absence vérifiée par recherche, aucun test trouvé)

- Aucun test de `post_message` ou `stream_message` de bout en bout avec
  persistance réelle (création de `Message`, incrément de `message_count`,
  `last_message_at`) — les seuls tests qui touchent `service.py` mockent soit
  `_prepare_turn`/`_finalize_turn`, soit n'appellent que `_prepare_turn` seul.
- Aucun test de facturation réelle du message (2 crédits débités, blocage à
  402 si insuffisant) sur le chemin conversation — `check_credits`/
  `consume_credits` ne sont testés que côté `billing` en isolation (non
  vérifié spécifiquement ici, hors périmètre de la recherche mais absent des
  fichiers listés).
- Aucun test du routage réel `AUTO` tel qu'exécuté par `_prepare_turn` (qui
  court-circuite `personas.route`, §3.1) — les tests de routage testent
  `personas.route` directement, ce qui **ne détecterait pas** une régression
  si `_prepare_turn` cessait d'appeler `AXIAL_CONSEIL` en mode libre.
- Aucun test de citations/`viz` persistés sur un message réel.
- Aucun test de pagination (normal : la fonctionnalité n'existe pas).
- Aucun test de suppression/renommage/archivage de conversation (normal :
  aucun endpoint n'existe).
- Aucun test de la survie d'un flux `stream_message` à une déconnexion
  client (contrairement au module `analysis`, cf §5, qui a
  `test_rapport_survit_a_la_fermeture_du_navigateur`).
- Aucun test d'idempotence / double-soumission.
- Aucun test du comportement 401 en cours de conversation.
- Aucun test sur `export.py` (Markdown/PDF) — ni sur la génération du titre
  de secours dans l'export (`_titre_utile`, export.py:19-28), qui duplique la
  logique de titre par défaut avec une liste différente de
  `TITRES_GENERIQUES` (`_TITRES_PAR_DEFAUT` inclut `"nouvelle analyse"` /
  `"new analysis"`, absents de `TITRES_GENERIQUES` — voir §7).
- Aucun test de `_attached_docs_context` (troncature à 3 documents / 8000
  caractères) sur le chemin conversation.
- Aucun test de `grounding.assemble` appliqué depuis le pipeline conversation
  (le module `grounding.py` lui-même n'a pas de fichier de test dédié
  trouvé).
- Aucun test du calcul de coût (`cout_micro_eur`) pour un message réel, ni de
  l'absence de mesure du coût de recherche web sur les messages (§3.7).

---

## 7. Observabilité

### Logs

Logger dédié `logging.getLogger("axial.intelligence")` (service.py:23), et
loggers voisins `axial.llm`, `axial.search.orchestrator`, `axial.rag`,
`axial.pii`, `axial.viz`, `axial.integrations.notion`. Niveaux `warning` sur
tout échec absorbé (RAG, recherche web, Notion, génération), `info` sur les
statistiques de dédoublonnage de recherche et les reprises Claude. Aucun log
structuré (JSON) dédié « conversation » — les logs sont des `str` formatés
libres, pas de corrélation systématique par `conversation_id` dans chaque
ligne (le `conversation_id` n'apparaît explicitement dans aucun message de
log de `service.py`).

### Métriques (`app/modules/metrics/`)

- `service.couts_totaux` (metrics/service.py:163-207) agrège le coût par
  poste (`rapports`, `conversations` → table `messages`, `veilles`) sur une
  fenêtre glissante. Pour le poste `conversations`, le coût de recherche est
  **codé en dur à `0`** (metrics/service.py:179-180 :
  `'0' if table == 'messages' else 'cout_recherche_micro_eur'`) — cohérent
  avec l'absence de colonne constatée au §1/§3.7, mais signifie que le coût
  affiché à l'admin pour les conversations est **structurellement
  sous-estimé** dès qu'un fournisseur de recherche web est appelé (ce qui est
  le cas sur la majorité des messages non triviaux).
- `service.activite` (metrics/service.py:107-129) compte les utilisateurs
  actifs via `actifs_question` : `DISTINCT c.user_id` sur `conversations`
  jointes à `messages` où `role='user'` dans la fenêtre — c'est la seule
  requête de ce fichier qui touche vraiment les conversations pour une
  métrique produit (pas seulement financière).
- `service.export` (metrics/service.py:233-262) inclut `questions` (nombre de
  messages `role='user'` par utilisateur) dans l'extrait `utilisateurs`.

### Vue admin du coût d'une conversation

- **Agrégé** : `GET /metrics/tableau` (metrics/router.py:19-26, réservé
  `is_admin`) expose `couts_totaux.postes.conversations` (coût modèle
  agrégé, recherche toujours à 0) et `activite.actifs_question`.
- **Par utilisateur** : `GET /metrics/comptes` (metrics/router.py:43-47)
  expose `questions` (nombre) mais **pas de coût par utilisateur** pour les
  conversations — la requête `_REQUETES["utilisateurs"]`
  (metrics/service.py:234-262) ne fait aucune agrégation de
  `messages.cout_micro_eur`.
- **Par conversation individuelle** : **aucun endpoint n'expose le coût
  d'une conversation précise** — ni son total, ni le détail par message. Le
  seul accès au coût par message serait une lecture directe de
  `messages.cout_micro_eur` (aucune route ne l'expose ; `MessageOut`,
  router.py:56-63, ne renvoie ni `cout_micro_eur`, ni `tokens_entree/sortie`,
  ni `modele` au client — ces champs sont écrits en base mais jamais
  lus par aucune API).
- **Export brut** (`GET /metrics/export`, token dédié) : agrège
  `couts_totaux` sur 10 ans (metrics/service.py:316) mais ne détaille pas non
  plus par conversation.

---

## Constats bruts

Liste factuelle, sans recommandation — chaque ligne est vérifiable au
fichier:ligne cité.

1. **Aucune mémoire conversationnelle envoyée au LLM.** Chaque appel modèle
   ne contient que le message courant + contexte entreprise + documents
   joints + sources — jamais les tours précédents de la même conversation
   (`claude.py:49-52`, `gemini.py:31-34`, absence de tout module
   `troncature*`). Une conversation de 30 messages n'a, du point de vue du
   modèle, pas plus de contexte qu'un message isolé.

2. **Le routage multi-agents « intelligent » n'est jamais exercé par le
   produit réel.** `personas.route` sait choisir entre Market Scanner,
   Competitor Radar et Axial Conseil selon le contenu de la question
   (personas.py:178-201), mais `_prepare_turn` court-circuite cette logique
   dès que `requested == AUTO` et force `AXIAL_CONSEIL` sans appeler `route`
   (service.py:204-206). Le code de routage n'est atteint en production que
   par l'endpoint de prévisualisation `/agents/route`, qui ne persiste rien.

3. **Aucun endpoint de suppression, renommage ou archivage** pour
   conversation ou projet (`router.py`, aucune route `DELETE/PUT/PATCH`
   trouvée). La colonne `Project.archived_at` existe et est déjà filtrée en
   lecture (`service.py:44`) mais n'est jamais écrite — fonctionnalité
   à moitié câblée.

4. **Aucune pagination** sur `list_projects`, `list_conversations`,
   `list_messages` (service.py:41-47, 73-80, 96-103) — tout l'historique
   d'une conversation est rechargé à chaque `GET
   /conversations/{id}/messages`, sans limite.

5. **Le coût de recherche web n'est jamais mesuré ni stocké pour un
   message.** `_prepare_turn` appelle `web_search.search(content, 6)` sans
   passer de `compteur` (service.py:250), contrairement au module
   `analysis` qui, lui, instrumente ses appels de recherche
   (`analysis/service.py:78-100`). Il n'existe même pas de colonne
   `cout_recherche_micro_eur` sur `messages` (absente de
   `0019_couts_chat_veille.py`, qui l'ajoute pourtant à `reports` et
   `watch_runs`). Conséquence directe : `metrics/service.py:179-180` fixe ce
   coût à `0` en dur pour le poste `conversations` — le tableau de bord admin
   sous-estime structurellement le coût réel des conversations.

6. **Aucune API n'expose le coût ou les tokens d'un message**, alors que ces
   champs sont écrits en base (`Message.cout_micro_eur`, `tokens_entree`,
   `tokens_sortie`, `modele`). `MessageOut` (router.py:56-63) ne les renvoie
   pas, et aucun endpoint `/metrics/*` ne détaille le coût par conversation
   ou par message — seul un agrégat par fenêtre temporelle existe.

7. **Facturation forfaitaire déconnectée du coût réel.** `agent_message`
   coûte toujours 2 crédits (`billing/catalog.py:22`), qu'il s'agisse d'une
   réponse triviale sans recherche (tier chat, Gemini, quelques centaines de
   tokens) ou d'une analyse longue avec recherche web multi-fournisseurs et
   tier `report` (Claude, jusqu'à 16000 tokens de sortie). Le rapport
   coût/prix n'est donc pas mesurable par message, seulement en moyenne
   globale et de façon incomplète (constat 5).

8. **Incohérence de facturation sur le streaming interrompu en cours de
   réponse.** Si le flux échoue **avant** le premier chunk, la réponse est
   marquée dégradée et non facturée (service.py:452-459). Si le flux échoue
   **après** au moins un chunk, le texte partiel est conservé, une note
   d'interruption est ajoutée, et le message est facturé comme une réponse
   complète et normale (service.py:461-465, 482) — pas de statut « partiel »
   distinct côté facturation ou côté `Message` (pas de champ `degraded`/
   `partial` persisté sur la table).

9. **Reprise automatique sur troncature absente en streaming.**
   `claude.generate` (bloquant, utilisé par `post_message`) relance
   automatiquement jusqu'à 3 fois si le modèle s'arrête sur `max_tokens`
   (claude.py:92-110), mais `claude.stream` (utilisé par `stream_message`,
   claude.py:149-176) n'a pas cette logique — un message tronqué en flux SSE
   reste tronqué, sans que rien ne le signale à l'utilisateur autrement que
   par la coupure brute du texte.

10. **Double définition, potentiellement divergente, des « titres
    génériques ».** `service.TITRES_GENERIQUES` (service.py:183) et
    `export._TITRES_PAR_DEFAUT` (export.py:15-16) sont deux listes
    indépendantes qui se recouvrent partiellement mais pas totalement
    (`_TITRES_PAR_DEFAUT` inclut `"nouvelle analyse"`/`"new analysis"`,
    absents de `TITRES_GENERIQUES`) — une modification de l'une sans l'autre
    romprait silencieusement la cohérence entre le titre affiché dans l'app
    et celui utilisé à l'export.

11. **Aucun test d'intégration bout-en-bout de `post_message`/
    `stream_message`** avec une vraie session DB (le seul test qui exécute
    `_prepare_turn` réellement, `test_registre.py:155-197`, reste sur le
    chemin `trivial`, sans RAG/web/Notion, et n'appelle jamais
    `_finalize_turn` ni ne vérifie la persistance du message assistant).

12. **Idempotence absente.** Chaque requête `POST .../messages` crée un
    nouveau message et débite des crédits, sans clé d'idempotence acceptée
    côté client (service.py:223-224, 360-361) — un retry réseau ou un
    double-clic frontend duplique le message et la facturation.

13. **Cache Notion en mémoire de process, non borné dans le temps de vie.**
    `_cache: dict[str, tuple[float, list]]` (notion_context.py:68) est un
    dictionnaire global par utilisateur, jamais purgé (seulement écrasé par
    entrée), qui ne survit pas à un redémarrage et n'est pas partagé entre
    workers multiples — un déploiement multi-process verra des TTL de cache
    Notion incohérents entre requêtes.

14. **`message_count` dénormalisé, jamais recalculé.** Incrémenté de 2 à
    chaque tour réussi (service.py:370) sans jamais être vérifié contre un
    `COUNT(*)` réel sur `messages` — une divergence (ex. suppression
    manuelle en base, migration partielle) ne serait jamais détectée ni
    corrigée automatiquement.

15. **`user_id` dupliqué entre `Project` et `Conversation`** sans contrainte
    de cohérence en base (models.py:26, 44) — rien n'empêche, en théorie,
    qu'une conversation ait un `user_id` différent de celui de son projet
    parent (non exploité par le code actuel, qui filtre par
    `conv.user_id` directement, mais la redondance elle-même n'est pas
    protégée par une contrainte SQL).

16. **`GET /intelligence/agents/route` ne fait rien persister** et n'est
    utilisé, dans le code serveur, par aucun autre module que le frontend
    (endpoint de prévisualisation pure) — sa seule fonction vérifiable côté
    backend est de dupliquer la logique de `personas.route` déjà exercée
    différemment par `_prepare_turn` (constat 2).
