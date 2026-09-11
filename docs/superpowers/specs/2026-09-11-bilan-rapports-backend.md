# Bilan factuel — backend « rapports » (11/09/2026)

Périmètre : `app/modules/analysis/` (le pipeline qui produit un rapport) et
`app/modules/reports/` (l'archive : persistance, PDF, rapports hérités,
notification), plus tout ce qu'ils appellent en aval — recherche web multi-
angles, RAG, base investisseurs, mémoire, PII, LLM, viz, billing, metrics.
Lecture seule, aucune modification. Objectif : décrire ce qui existe
réellement, pas ce qui devrait exister.

---

## 1. Modèle de données

### `reports` (`app/modules/reports/models.py:18-43`)

Créée par `alembic/versions/0003_billing_reports.py` (10/08/2026), complétée
par trois migrations ultérieures.

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID, indexé | pas de FK explicite vers `auth.users` |
| `analysis_type` | String(64), défaut `"synthese_executive"` | pas de contrainte CHECK en base — n'importe quelle chaîne est acceptée à l'écriture directe |
| `title` | String(300), NOT NULL | |
| `content` | Text, défaut `""` | markdown brut, y compris la section `## Sources` rédigée par le modèle |
| `sources` | JSON/JSONB, nullable | liste de citations `{title, url, domain, source, excerpt, reference}` — **ou un scalaire** sur d'anciens rapports restaurés (voir §4, `legacy.py`), ce que `service.export_pdf` gère explicitement (`service.py:60`) |
| `viz` | JSON/JSONB, nullable | liste sérialisée `Viz.dict()` (voir §4), ajoutée par `0021_viz.py` |
| `tokens_entree`, `tokens_sortie` | Integer, nullable | absents des rapports antérieurs au 25/08/2026 |
| `cout_micro_eur` | Integer, nullable | coût **modèle seul** |
| `modele` | String(64), nullable | ex. `claude-sonnet-5` |
| `cout_recherche_micro_eur` | Integer, nullable | coût des appels de recherche web (Exa/Tavily/Linkup), **mesuré** contrairement au module `intelligence` (conversations) qui ne passe jamais de `compteur` |
| `appels_recherche` | Integer, nullable | nombre total d'appels de recherche tous fournisseurs |
| `duree_secondes` | Integer, nullable | mesuré depuis le début de `run_analysis` |
| `created_at` | DateTime(tz) | |

**Aucune colonne `status`, `updated_at` ni `user_query`.** Une ligne `Report`
n'existe qu'une fois la génération **terminée avec succès** — il n'y a pas
d'état intermédiaire « en cours » persisté (voir §3, §5). Le contenu n'est
jamais modifié après création (pas de régénération, pas d'édition).

### `legacy_reports` (`app/modules/reports/legacy.py:25-36`, migration `0011_legacy_reports.py`)

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | String(320), indexé | clé de rattachement — pas de FK, l'ancien compte n'existe plus |
| `legacy_id` | Integer, nullable | identifiant sur l'ancienne plateforme |
| `title` | String(500) | plus long que `reports.title` (300) — tronqué à l'import (`legacy.py:129`) |
| `content` | Text | |
| `analysis_type` | String(64), nullable | |
| `legacy_created_at` | DateTime(tz), nullable | |
| `imported_at` | DateTime(tz), nullable | marque l'import fait, empêche un doublon |
| `imported_for` | UUID, nullable | utilisateur destinataire une fois importé |

### `viz_rendus` (`app/modules/viz/models.py:20-26`, migration `0021_viz.py`)

| Colonne | Type | Notes |
|---|---|---|
| `empreinte` | String(64) PK | SHA-256 du spec Vega-Lite compilé — sert aussi d'identifiant **public** d'image (`GET /viz/{empreinte}.svg`, pas d'auth) |
| `vl` | JSON/JSONB | spec Vega-Lite compilée, prête à rendre |
| `created_at` | DateTime(tz), `server_default=now()` | |

Cache/registre par empreinte : un même graphique (même spec, mêmes données)
n'est jamais recompilé ni redupliqué — testé (`test_viz_service.py:23-28`,
`test_preparer_est_idempotent_sur_le_meme_spec`).

### Migrations qui touchent ces tables

| Fichier | Contenu |
|---|---|
| `0003_billing_reports.py` | création de `reports` (id, user_id, analysis_type, title, content, sources, created_at) + `credit_balances` |
| `0011_legacy_reports.py` | création de `legacy_reports` |
| `0018_report_cost.py` | ajoute `tokens_entree`, `tokens_sortie`, `cout_micro_eur`, `modele`, `duree_secondes` sur `reports` |
| `0019_couts_chat_veille.py:29-30` | ajoute `cout_recherche_micro_eur` + `appels_recherche` sur `reports` **et** `watch_runs` (mais pas `messages`, cf. le bilan « conversations » §3.7) |
| `0021_viz.py` | table `viz_rendus` + colonne `viz` sur `reports` et `messages` |

Aucun index composite (`user_id, created_at`), aucune contrainte d'unicité
sur `reports`. `list_reports` (service.py:34-40) trie par `created_at desc`
sans index dédié au-delà de l'index simple sur `user_id`.

---

## 2. Surface API

### `app/modules/analysis/router.py`, préfixe `/analysis`

| Méthode | Route | Auth | Payload | Réponse | Ligne |
|---|---|---|---|---|---|
| GET | `/analysis/types` | publique | — | `{types:[{key,label}]}` (7 types, `ANALYSIS_LABELS`) | router.py:26-28 |
| POST | `/analysis/run` | user | `AnalysisRequest{query, analysis_type, title?, top_k?}` | `AnalysisResponse` (bloquant, peut prendre plusieurs minutes dans la requête HTTP) | router.py:31-52 |
| POST | `/analysis/premier-rapport` | user | — | `202 {lance: bool, raison?}` — lance en **thread daemon détaché**, répond immédiatement | router.py:55-83 |
| POST | `/analysis/stream` | user | `AnalysisRequest` | `StreamingResponse` SSE (`text/event-stream`), progression + `done` final | router.py:86-97 |

`/analysis/run` exécute `run_analysis` **synchrone dans le thread de la
requête** — pas le mécanisme dédié « survit à la fermeture du navigateur »
construit pour `/analysis/stream` (§5). `/analysis/premier-rapport` démarre
un `threading.Thread(daemon=True)` avec sa **propre session DB**
(`SessionLocal()`), exactement pour la même raison documentée en commentaire
(`router.py:74-76`) que celle qui a motivé le pattern du streaming (§5).

### `app/modules/reports/router.py`, préfixe `/reports`

| Méthode | Route | Auth | Payload | Réponse | Ligne |
|---|---|---|---|---|---|
| POST | `/reports` | user | `ReportIn{title, content, analysis_type?, sources?}` | `ReportDetail` — **création manuelle arbitraire**, sans passer par le pipeline d'analyse (pas de coût, pas de facturation) | router.py:39-46 |
| GET | `/reports` | user | — | `list[ReportOut]` (id, title, analysis_type, created_at) — **pas de pagination**, tri `created_at desc` | router.py:49-56 |
| GET | `/reports/{report_id}` | user | — | `ReportDetail` (+ content, sources, viz) | router.py:59-65 |
| GET | `/reports/{report_id}/pdf` | user | — | `StreamingResponse` PDF, `Content-Disposition: attachment` | router.py:68-77 |
| DELETE | `/reports/{report_id}` | user | — | `204` | router.py:80-84 |

`POST /reports` accepte un `content` et des `sources` arbitraires fournis
par le client, sans validation de cohérence avec un `analysis_type`
existant (`is_valid_type` n'est jamais appelé ici) ni avec un pipeline de
génération réel — un client authentifié peut créer un « rapport » vide de
tout coût et de toute preuve de génération.

**Aucune route** `PUT`/`PATCH` (renommage, édition), aucune route de
régénération, d'archivage ou de partage public. Confirmé par recherche
(`grep "@router\.\(put\|patch\)"` → aucun résultat dans `reports/router.py`
et `analysis/router.py`).

### `app/modules/viz/router.py`, préfixe `/viz`

| Méthode | Route | Auth | Réponse | Ligne |
|---|---|---|---|---|
| GET | `/viz/{empreinte}.svg` | **publique**, `Cache-Control: immutable, max-age=31536000` | SVG | router.py:31-33 |
| GET | `/viz/{empreinte}.png` | **publique**, mêmes en-têtes | PNG | router.py:35-37 |
| POST | `/viz/rendu` | user | `{empreinte, kind, statut, svg?, tableau?}` — compilation à la volée d'un bloc viz émis en streaming côté chat | router.py:39-49 |

Les images de graphique sont servies **sans authentification** — protégées
uniquement par l'imprévisibilité de l'empreinte SHA-256 (64 caractères hex),
« comme un lien de partage » (commentaire router.py:1-4). N'importe qui
connaissant une empreinte (visible dans un email de veille transmis, ou
dans l'URL d'une image copiée) peut la charger indéfiniment, sans contrôle
d'appartenance au rapport ou à l'utilisateur d'origine.

### `app/modules/investors/router.py`, préfixe `/investors`

| Méthode | Route | Auth | Réponse | Ligne |
|---|---|---|---|---|
| GET | `/investors/status` | publique | `{configured: bool}` | router.py:18-20 |
| GET | `/investors/referentials` | user | vocabulaires secteur/stade/zone | router.py:23-25 |
| GET | `/investors/mapping` | user | mapping classé pour le profil de l'utilisateur connecté (`limit=15` par défaut) | router.py:28-32 |

Cette route sert la liste courte **sans générer de rapport** (donc sans
coût de génération LLM et sans débit de crédits) — c'est le même moteur de
scoring que le type d'analyse `cartographie_investisseurs`, exposé en accès
direct pour l'aperçu côté interface.

### Billing — où `check_credits`/`consume_credits` sont appelés

| Chemin | Vérification (`check_credits`) | Débit (`consume_credits`) |
|---|---|---|
| `/analysis/run` | `precheck_credits` avant tout appel réseau (router.py:35) | `finalize()` après génération réussie (service.py:285) |
| `/analysis/stream` | `precheck_credits` en tout premier événement SSE (service.py:324) | `finalize()` dans le thread de génération, après succès (service.py:367) |
| `/analysis/premier-rapport` | **aucune** — `onboarding.offrir` appelle `finalize(..., is_admin=True)`, qui bypass `consume_credits` (service.py:106, billing/service.py:92-93) | rapport gratuit, jamais débité |
| `POST /reports` (création manuelle) | **aucune** | **aucune** — ce chemin ne passe jamais par `billing` |

Coûts canoniques (`app/modules/billing/catalog.py:11-21`) :

| Type | Crédits |
|---|---|
| `synthese_executive` | 40 |
| `etude_marche` | 40 |
| `cartographie_investisseurs` | 30 |
| `analyse_concurrentielle` | 25 |
| `veille_technologique` | 25 |
| `analyse_risques` | 25 |
| `analyse_reglementaire` | 25 |

Ces coûts sont fixes par type, indépendants du volume de sources réellement
trouvées, du nombre de tokens produits ou de la durée. `synthese_executive`
et `etude_marche` sont au même tarif (40) depuis une décision produit
explicite en commentaire (`catalog.py:17-18` : « la facturer moins cher
rendait le bouton "Étude de marché" sans objet »).

### Export PDF

`GET /reports/{id}/pdf` → `app/modules/reports/service.py:56-62` →
`app/modules/reports/pdf.py:render_pdf`. Détail complet au §4.

### Export Markdown

**N'existe pas.** Aucune route ne sert `content` en tant que fichier
`.md` téléchargeable — seul le PDF est un export dédié ; le Markdown brut
n'est accessible que via `GET /reports/{id}` (JSON, champ `content`), à
charge du frontend de le proposer en téléchargement s'il le souhaite.

### Feedback (« Votre avis »)

**Aucun endpoint de feedback structuré** (pas de table, pas de route
`POST /reports/{id}/feedback` ou équivalent). Le seul mécanisme est
la ligne de l'email de notification (`notification.py:31` : « dis-le-moi en
répondant à ce message ») — un feedback par réponse email, non capté par
l'application, hors périmètre de ce backend.

### Partage

**N'existe pas** pour les rapports eux-mêmes (pas de lien public, pas de
route `share`). Seules les **images de graphiques** sont publiques par
construction de leur URL (voir `/viz` ci-dessus) — mais le rapport complet
qui les contient reste protégé par authentification.

---

## 3. Le pipeline de génération (`app/modules/analysis/service.py`)

### 3.1 Types d'analyse

Sept types, définis dans `app/modules/analysis/prompts.py:143-287`
(`ANALYSIS_DIRECTIVES`) : `synthese_executive`, `analyse_concurrentielle`,
`veille_technologique`, `analyse_risques`, `analyse_reglementaire`,
`cartographie_investisseurs`, `etude_marche`. Chaque directive porte
`target_words`, `min_sources`, `objective`, `key_angles` (3-5 axes),
`special_instructions`.

Quatre alias legacy (`_ALIASES`, prompts.py:300-305) : `market_study`,
`competition`, `tech_watch`, `risk_analysis` → types canoniques. Ces mêmes
alias existent, dupliqués, dans `billing/catalog.py:24-29` — deux
dictionnaires indépendants à tenir synchronisés (pas de source unique).

`is_valid_type(analysis_type)` (prompts.py:429-430) teste l'appartenance du
type canonique à `ANALYSIS_DIRECTIVES` — un type totalement inconnu lève
`AppError 400 unknown_analysis_type` (service.py:79-81, testé
`test_analysis.py:24-27`).

`sources_for(analysis_type)` (prompts.py:418-426) renvoie `min_sources` (25
par défaut si type inconnu) — c'est ce nombre qui devient le `top_k` de
recherche si le client n'en fournit pas (`AnalysisRequest.top_k`, borné 0-60,
schemas.py:15).

`ANALYSIS_PROMPTS` (prompts.py:434, un dict `{type: template assemblé}`
calculé une fois à l'import) **n'est utilisé nulle part en production** —
recherche confirmée (`grep ANALYSIS_PROMPTS app tests` → uniquement
`prompts.py` lui-même et `tests/test_analysis.py:12,18,44`). Le code réel
(`run_analysis`, service.py:158) appelle `get_prompt_template(analysis_type)`
directement à chaque génération ; `ANALYSIS_PROMPTS` est un artefact de
compatibilité gardé pour les tests, jamais consulté par le pipeline.

### 3.2 Directive / template de prompt (`prompts.py`)

Master prompt assemblé (`get_master_prompt`, prompts.py:132-136) à partir de
sept blocs modulaires, concaténés dans cet ordre :
`CORE_IDENTITY` → `REASONING_METHOD` → `OUTPUT_STYLE` → `ACTIONABLE_KPIS` →
`ANTI_HALLUCINATION` → `CITATION_FORMAT` → `FINAL_PRINCIPLES`.

`OUTPUT_STYLE` (prompts.py:39-79), les 8 règles obligatoires :
1. Jamais d'emojis (export PDF en polices standard).
2. Hiérarchie de titres `#`/`##`/`###`.
3. Chaque section : 60-70 % narration, 30-40 % listes — jamais 100 % puces.
4. Phrases complètes, ton professionnel.
5. Tout chiffré passe par un tableau markdown OU un bloc `\`\`\`viz` JSON
   (règle de choix détaillée : comparaison/répartition/évolution/entonnoir/
   positionnement → viz plutôt que tableau ; jamais les deux pour la même
   donnée).
6. Section finale obligatoire « ## Sources » (jamais « Références
   Bibliographiques »).
7. Ouverture par « ## Synthèse exécutive » (ou « ## Executive summary » en
   anglais), 5-8 phrases, sans puce ni tableau.
8. Vouvoiement obligatoire, jamais de tutoiement.

`ANTI_HALLUCINATION` (prompts.py:90-112), 7 règles : jamais d'URL/date/titre
inventés, absence de source = « trou de recherche » jamais convertie en
signal négatif sur le marché, toute estimation en volume doit nommer son
dénominateur.

`CITATION_FORMAT` (prompts.py:114-123) : citations inline `[N]` ou `[N][M]`,
section finale listant numéro/organisation/titre/année/URL.

`get_prompt_template(analysis_type)` (prompts.py:322-342) assemble la
directive du type + un slot `{context}` où viendront le profil entreprise et
les sources numérotées, plus la question de l'utilisateur en fin de prompt
(service.py:161).

### 3.3 Recherche multi-angles

`angles_de_recherche(analysis_type, query)` (prompts.py:388-415) transforme
les `key_angles` de la directive en requêtes de recherche distinctes : la
question de l'utilisateur ne couvre qu'une facette du rapport attendu. Un
bug de production daté du 24/08 est documenté en commentaire
(`prompts.py:392-395`, `test_troncature.py:101-113`) : un rapport a
sous-estimé un marché de 35-50 % faute d'avoir cherché la voie
d'homologation, alors que rien ne l'avait cherchée. Détection de langue
grossière (`_question_en_anglais`, prompts.py:355-357, comparaison de
compte de mots-outils FR/EN) pour traduire la tête de chaque angle
(`ANGLES_EN`, prompts.py:363-385, dictionnaire écrit à la main plutôt
qu'appelé à un modèle — « le jeu est fermé »). Maximum 6 angles retournés
(prompts.py:415).

`web_search.search_multi(angles, top_k, requete_de_rang, compteur)`
(`app/shared/search/orchestrator.py:82-133`) : si un seul angle, retombe sur
`search()` simple. Sinon, **chaque angle interroge chaque fournisseur actif**
(`taches = [(p, q) for p in providers for q in angles]`,
orchestrator.py:110), avec `par_angle = max(5, top_k // 2)` résultats
demandés par tâche (orchestrator.py:108) — jusqu'à 12 threads en parallèle
(orchestrator.py:113). Résultats fusionnés, dédupliqués par URL canonique
(`_dedupe`, orchestrator.py:22-30, préservant l'extrait le plus riche en cas
de collision), puis rerankés contre la question d'origine
(`rerank.rerank`, appelé avec `requete_de_rang or angles[0]`,
orchestrator.py:132).

Le paramètre `compteur` (dict fourni par l'appelant, rempli par
fournisseur/nombre d'appels) est **explicitement passé** par
`run_analysis` (service.py:98-100 : `appels_recherche` dict initialisé
ligne 78) — c'est ce qui rend le coût de recherche mesurable pour un
rapport, contrairement au module `intelligence` (conversations) qui
n'instrumente jamais ses appels (bilan « conversations » §3.7 et §7,
constat 5).

### 3.4 Contexte RAG, Notion, investisseurs

- **RAG** (`_retrieve_context`, service.py:54-65) : `top_k` documents,
  aucun plafond arbitraire côté retrieval (« un utilisateur avec des
  documents riches obtient tout son matériel pertinent », commentaire
  service.py:105-107) — c'est le reranker en aval qui arbitre. `try/except
  Exception` large, log + `("", [])` en cas d'échec Qdrant/embeddings.
- **Espace Notion** (service.py:144-150) : passages ajoutés au pool des
  passages RAG si `db_pour_notion` est fourni ; `try/except Exception`,
  jamais fatal.
- **Base investisseurs** (uniquement pour `cartographie_investisseurs`,
  service.py:118-141) : `investors.map_for_profile(profile)` grounde le
  rapport **en premier**, avant le web — « ce sont des données vérifiées,
  pas des résultats de recherche web » (prompts.py:250-251). Si aucune
  citation investisseur n'est produite (base indisponible, profil non
  mappable), le rapport n'est **pas généré du tout** : réponse dégradée
  immédiate, explicite, **sans consommer l'appel LLM** (service.py:131-141)
  — seul le type `cartographie_investisseurs` a ce court-circuit ; les
  six autres types continuent même sans aucune source.

`grounding.assemble` (`app/shared/grounding.py:19-75`) fusionne web + RAG/
Notion (+ investisseurs si présents, préfixés et numérotés avant, via
`start_at=len(investor_citations)+1`, service.py:152-157) en **un seul pool
numéroté**, dédupliqué par clé de contenu (`key`, pas seulement par URL —
un même document peut apparaître plusieurs fois avec des passages
distincts, grounding.py:52-54), classé par `rerank_indices`. Cette liste
finale devient à la fois le bloc `Sources (numérotées)` du prompt et la
liste `citations` persistée sur `Report.sources`.

### 3.5 Mémoire entreprise, PII

- `company_context = memory.build_context(...)` préfixé au prompt si
  présent (service.py:159-160).
- `guard_outbound` (PII, service.py:166) appliqué au prompt final juste
  avant l'appel LLM — même garde que pour les conversations, mode par
  défaut `shadow` (texte non modifié en pratique, cf. bilan « conversations »
  §2).

### 3.6 Appel LLM

`llm_client.generate(system=SYSTEM_PROMPT + consigne_miroir(), prompt,
tier="report", max_tokens=32000)` (service.py:182-183) — toujours
`tier="report"` par défaut pour `run_analysis` (paramètre `tier`, valeur par
défaut `"report"`, signature service.py:70), donc toujours Claude en
priorité, jamais le tier `chat`/Gemini utilisé par les conversations. Aucun
appelant du module `analysis` ne passe `tier="chat"` — recherche confirmée
(`grep 'tier=' app/modules/analysis/'` → uniquement la valeur par défaut).

`max_tokens=32000` (le double du plafond conversation `report`, 16000, cf.
bilan « conversations » §3.5) — cohérent avec des volumes cibles de
8000-10000 mots pour `synthese_executive`/`etude_marche`.

Reprise automatique sur troncature : `claude.generate` (bloquant, utilisé
ici) relance jusqu'à `MAX_REPRISES` fois en cas de `stop_reason ==
"max_tokens"` (`claude.py`, testé `test_troncature.py:48-81`). Comme
`run_analysis` n'appelle jamais `claude.stream`, ce chemin bénéficie
**toujours** de la reprise — contrairement au chat qui, en streaming, en
est privé.

**Dernier filet** malgré les reprises (service.py:207-220) : si le texte
reste tronqué (`result.stop_reason == "max_tokens"`), le contenu partiel
est retourné avec un avertissement ajouté en fin de texte, marqué
`degraded=True`, `status_note="truncated_generation"` — **non facturé, non
archivé** (`finalize`, service.py:278-279). Ce cas est directement issu
d'un incident de production documenté (`test_troncature.py:1-8` : « le
24/08, une étude de marché livrée à un client s'est arrêtée en plein mot
après 1740 mots… les 40 crédits avaient été débités » — corrigé depuis).

### 3.7 Chemins dégradés

| Cas | Comportement |
|---|---|
| Type d'analyse inconnu | `AppError 400 unknown_analysis_type` (service.py:79-81) |
| Cartographie investisseurs sans citation | dégradé immédiat, avant tout appel LLM, `status_note="investors_unavailable"` (service.py:131-141) |
| Aucun LLM disponible (`generation_available()` faux) | dégradé, `status_note="llm_unavailable"`, non facturé (service.py:169-176) |
| `generate()` lève une exception | dégradé, `status_note="generation_failed"` (service.py:184-191) |
| Réponse vide (thinking a consommé tout le budget) | dégradé, `status_note="empty_generation"`, log d'avertissement explicite (service.py:193-202) |
| Troncature persistante après reprises | dégradé, `status_note="truncated_generation"`, texte partiel conservé mais non archivé (service.py:204-220) |
| Web search échoue entièrement | **non dégradé** — `web_results = []`, le rapport continue avec RAG/Notion/investisseurs seuls (service.py:101-103) |

Tous les messages dégradés affirment explicitement au lecteur « aucun
crédit n'a été débité » — cohérent avec `finalize()` qui ne facture ni
n'archive un résultat `degraded=True` (service.py:278-279).

### 3.8 Coût / crédits par rapport

`mesure` (service.py:224-233), calculé uniquement sur un résultat réussi :

- `appels_recherche` = somme de `appels_recherche.values()` (ou `None` si
  vide) — vrai décompte, alimenté par `search_multi(compteur=...)`.
- `cout_recherche_micro_eur` = `couts.cout_recherche_micro_eur(appels_recherche)`
  — tarif par fournisseur (`billing/couts.py:58-73`, Exa 4600 µ€/appel,
  Tavily 7400, Linkup 4600, Serper 920 — « ordres de grandeur… à confirmer
  sur les grilles officielles », commentaire couts.py:11-13).
- `tokens_entree`/`tokens_sortie`/`modele` depuis le résultat LLM.
- `cout_micro_eur` = `couts.cout_micro_eur(modele, entree, sortie)` — tarifs
  par million de tokens, configurables par variable d'environnement
  (`TARIF_<MODELE>`), repli sur le tarif d'un modèle premium si modèle
  inconnu (« sous-estimer un coût est plus dangereux que le sur-estimer »,
  couts.py:26-27).
- `duree_secondes` = temps total depuis le début de `run_analysis`.

Contrairement au module `intelligence` (conversations), **le rapport mesure
et persiste réellement son coût de recherche web** — c'est la référence
explicitement citée par le bilan « conversations » (§3.7, constat 5) comme
ce que ce module fait et que les conversations ne font pas.

### 3.9 Facturation — ordre des opérations et un risque de découplage

`finalize()` (service.py:272-304), appelé seulement si `result.degraded`
est faux :
1. `billing.consume_credits(...)` — **débite et committe immédiatement**
   (billing/service.py:121-122, verrouillage `FOR UPDATE` de la ligne de
   solde).
2. `reports.create_report(...)` — **écrit et committe séparément**
   (reports/service.py:28-30).
3. `report.viz = viz_service.preparer_sans_faute(...)` puis `db.commit()` —
   tolérant, `try/except Exception` interne (viz/service.py:32-38).
4. `analytics.increment_usage(...)`.

Ces deux commits (1 et 2) sont **deux transactions distinctes, non
atomiques entre elles**. Si l'étape 2 (`create_report`) échoue après que
l'étape 1 a déjà committé — erreur DB, colonne manquante, connexion coupée
— les crédits ont été débités et aucun rapport n'existe pour l'utilisateur :
aucun mécanisme de compensation (remboursement automatique) n'existe dans
ce chemin. Aucune recherche de code n'a trouvé de `try/except` englobant
les deux appels dans `finalize()`, ni de test qui exerce ce scénario
(§6).

### 3.10 Statut / progression côté client

Il n'existe **pas de colonne `status`** sur `Report` — un rapport
« en cours » n'a **aucune trace persistée** tant que `finalize()` n'a pas
committé. La progression est communiquée **uniquement via les événements
SSE** de `/analysis/stream` (§3.11), jamais lue depuis la base : un client
qui recharge la page pendant une génération en cours ne peut récupérer
aucun état de progression — il ne voit rien tant que le rapport n'apparaît
pas dans `GET /reports`.

### 3.11 Streaming (`stream_analysis`, service.py:313-410)

Générateur SSE, séquence d'événements :
1. `{progress: 5, step: "start"}` immédiat.
2. `precheck_credits` — erreur `AppError` → événement `error` + `done: true`,
   génération jamais lancée (service.py:323-328).
3. `{progress: 20, step: "retrieve"}`, `{progress: 40, step: "generate"}`.
4. **La génération ET l'archivage tournent dans un `ThreadPoolExecutor(
   max_workers=1)`**, sur une session DB dédiée (`SessionLocal()` ouverte
   dans le thread, service.py:357-364) — corrige explicitement un bug
   daté du 25/08 (commentaire service.py:349-353) où l'archivage vivait
   *après* le dernier `yield` du générateur : fermer l'onglet pendant la
   rédaction faisait perdre un rapport déjà payé au fournisseur LLM.
5. Pendant l'attente, un battement de cœur toutes les `HEARTBEAT_SECONDS`
   (8 s, service.py:31) : `{progress: min(+3, 85), heartbeat: true,
   message: "Rédaction en cours… (Xmin Ys)"}` (service.py:379-387) — sert à
   garder la connexion ouverte face aux proxys qui coupent les connexions
   silencieuses.
6. À la fin du thread : la notification email (`notification.prevenir`)
   est envoyée **depuis le thread**, pas depuis le générateur principal —
   « c'est le seul endroit qui s'exécute que le navigateur soit encore là
   ou non » (service.py:369-374).
7. Événement final : `{progress: 100, step: "done", done: true, data:
   {...report_id, viz}}` si succès, ou `{degraded: true, message}` sans
   `report_id` si dégradé.

### 3.12 Persistance mi-flux, survie à la fermeture du navigateur

**Test dédié et vérifié** :
`test_troncature.py:150-199`,
`test_rapport_survit_a_la_fermeture_du_navigateur` — reproduit exactement le
bug du 25/08 (commentaire du test, lignes 151-156) : ferme le générateur
(`gen.close()`, ce que fait FastAPI à la déconnexion) après le premier
battement de cœur, puis vérifie que l'archivage (`finalize`, mocké) a bien
eu lieu malgré la fermeture. C'est un comportement **testé et garanti** pour
`/analysis/stream` — contrairement à `intelligence.stream_message` qui n'a
pas d'équivalent (bilan « conversations » §5, §6).

`/analysis/run` (chemin bloquant, non-stream) n'a **pas** ce mécanisme
dédié : la génération et l'archivage tournent directement dans le thread de
la requête HTTP, sans session séparée ni protection explicite contre une
déconnexion. Starlette exécute les endpoints `def` synchrones dans un
threadpool qui n'est en général pas annulé à la déconnexion du client, donc
le rapport devrait tout de même s'archiver dans la plupart des cas — mais
aucun test ne le vérifie pour ce chemin (§6), à la différence du chemin
`/stream` qui a été spécifiquement corrigé et verrouillé par un test après
l'incident du 25/08.

---

## 4. Post-traitement : citations, tableaux, viz, PDF

### 4.1 Citations

`citations` = la liste `cite` produite par `grounding.assemble`, persistée
telle quelle sur `Report.sources` (service.py:235, 288-290). Le modèle
rédige **lui-même** une section « ## Sources » en texte libre (règle 6 du
prompt, §3.2) — c'est un doublon volontaire : à l'export PDF, si des
`sources` structurées existent, la section texte du modèle est **repérée et
supprimée** (`pdf.py:141-156`, regex `_TITRE_SOURCES`) et remplacée par une
section générée depuis les données, avec ancres (`<a name="src-N"/>`) et
liens cliquables — testé
(`test_pdf_rapports.py:43-50`,
`test_la_section_sources_du_modele_est_remplacee_par_celle_des_donnees`).
Si aucune `sources` n'est fournie (ancien rapport sans citations
structurées), la section texte du modèle est **conservée telle quelle**
(`test_pdf_rapports.py:53-56`).

### 4.2 Découpage markdown → blocs (`app/modules/reports/blocs.py`)

Un seul analyseur, partagé entre le PDF et le pipeline viz — commentaire
explicite : « la logique "qu'est-ce qu'un tableau" ne doit pas exister deux
fois » (blocs.py:1-4). `decouper(markdown)` produit des `Bloc(genre, ...)` :
`h1`/`h2`/`h3`, `p`, `puces`, `tableau`, `hr`, `viz` (fences
` ```viz … ``` `), `graphique` (marque legacy « Graphique : Titre » suivie
d'un tableau à deux colonnes numériques d'unité unique, blocs.py:71-89,
compatibilité avec les rapports antérieurs au 10/09 — confirmée par
`test_analysis.py:64-68`,
`test_le_style_demande_un_bloc_viz_et_plus_la_marque_graphique`, qui
vérifie que le prompt actuel n'utilise plus cette marque).

`serie_numerique(cellules)` (blocs.py:127-144) n'accepte une conversion
graphique que si **toutes** les valeurs de la 2ᵉ colonne partagent la même
unité — « un graphique tracé sur des unités mélangées mentirait : mieux
vaut aucun graphique » (blocs.py:133-134), testé
(`test_pdf_rapports.py:73-76`,
`test_une_marque_graphique_sur_des_donnees_heterogenes_garde_le_tableau`).

### 4.3 Viz — extraction, validation, compilation (`app/modules/viz/`)

Contrat `VizSpec` (`viz/schema.py:34-49`) : 10 champs, `intent` (12
valeurs possibles : domination, classement, comparaison, répartition,
concentration, croissance, évolution, projection, rupture, entonnoir,
positionnement, pont), exactement une structure de données
(`series`/`points`/`steps`, validé par `_une_seule_structure`,
schema.py:53-58), `highlight` doit référencer un label existant de
`series`.

`pipeline.extraire_et_compiler(markdown)` (`viz/pipeline.py:60-79`) :
- `viz/registry.py` choisit et compile le rendu Vega-Lite selon
  `selector.choisir(spec)` (`viz/selector.py:56-60`), qui **peut contredire**
  le `kind` demandé par le modèle si incohérent avec la nature des données
  (ex. un `donut` à 11 parts redevient un classement en barres, testé
  `test_viz_core.py`).
- Un bloc invalide (JSON cassé, schema Pydantic refusé, spec qui ne
  compile pas en Vega-Lite) **ne lève jamais d'exception visible** : il
  devient un `Viz(statut="repli_tableau:<raison>")`, conservé avec ses
  données brutes plutôt que perdu — testé
  (`test_viz_pipeline.py:14-16, 18-21`).
- `render.py` : rendu **côté serveur sans navigateur** via `vl_convert`
  (`vl_convert.vegalite_to_svg`/`vegalite_to_png`), caché par
  `functools.lru_cache(maxsize=256)` en mémoire de process en plus du
  cache DB (`viz_rendus`).
- `theme.py` : palette de marque unique, police `Helvetica, Liberation
  Sans, DejaVu Sans, sans-serif` — commentaire explicite (theme.py:15-18) :
  « sur le VPS le rasteriseur PNG ne trouve pas "Helvetica" et, sans repli,
  il n'écrit AUCUN texte (constaté le 11/09) » — incident de production
  daté du jour même de ce bilan.

`viz_service.preparer(db, markdown)` (`viz/service.py:16-28`) est appelé une
seule fois, **à l'archivage** (`finalize`, service.py:297), stockant chaque
rendu Vega-Lite compilé dans `viz_rendus` par empreinte (déduplication
automatique — un même graphique compilé deux fois ne s'enregistre qu'une
fois, testé `test_viz_service.py:23-28`) puis la liste sérialisée sur
`Report.viz`. `preparer_sans_faute` (viz/service.py:32-38) absorbe toute
exception — « une erreur ici ne doit jamais empêcher la facturation ni
l'enregistrement du texte ».

### 4.4 Rendu PDF (`app/modules/reports/pdf.py`, ReportLab/Platypus)

`render_pdf(title, markdown, sources, vizs)` — A4, marges 2 cm
(pdf.py:91-92), styles `H1`/`H2`/`H3`/`Body`/`Cellule`/`Src` dérivés de
`getSampleStyleSheet()`.

- **Filigrane** : `app/assets/branding/watermark-axial.png`, chargé une
  fois (`functools.lru_cache(maxsize=1)`, pdf.py:23-42), opacité réduite à
  12 % via le canal alpha (`_WATERMARK_OPACITY = 0.12`) — absent
  gracieusement si le fichier ou Pillow n'est pas disponible
  (`_watermark_reader` retourne `None`, log d'avertissement).
- **Tableaux** : largeur totale = `A4[0] - 4cm`, colonnes de largeur égale
  (« lisible sans mesurer le texte », pdf.py:106-108), en-tête colorée
  `#ECEAFB`/`#7976F7`, `repeatRows=1` (l'en-tête se répète sur les pages
  suivantes).
- **Graphiques** : image PNG (`vers_png`, échelle 2×) insérée via
  `KeepTogether` (image + ligne de source, insécables sur une coupure de
  page, pdf.py:129-139) ; `vizs` préparés à l'archivage réutilisés en
  priorité (`par_index`), sinon compilés à la volée pour un rapport
  d'avant la V1 (pdf.py:125-127, « rapport d'avant la V1 »).
- **Citations** : liens internes `#src-N` vers les ancres de la section
  Sources, uniquement si `sources` est fourni (`liens = bool(sources)`,
  pdf.py:143) — un `[N]` inerte est préféré à un lien mort.
- **Section Sources générée** (pdf.py:187-203) : une ligne par citation,
  ancre `<a name="src-N"/>`, titre/domaine/URL si présents ; mention
  « espace Notion » ou « document interne » si pas d'URL.

Le module `blocs.tableau_de_repli` / `viz_pipeline.tableau_de_repli` assure
qu'un graphique non rendu (spec invalide, Vega-Lite refusé) **retombe
toujours** sur un tableau de ses données brutes plutôt que de disparaître
silencieusement du PDF (pdf.py:176-180).

### 4.5 Le type « cartographie_investisseurs »

Grounding adossé à la base investisseurs propriétaire (`app/modules/
investors/service.py`), pas au web. Deux structures scorées séparément :
fonds (regroupés par société de gestion, pas par véhicule — « une société
gère 5 à 20 véhicules ») et réseaux d'angels/crowdequity (score non
comparable, pas de taxonomie sectorielle structurée). Score = pertinence
secteur/stade pondérée par spécificité (`_score`, investors/service.py:83-
91) — **n'exprime aucune probabilité d'investissement**, ce que la
directive du prompt impose de dire explicitement au lecteur
(prompts.py:253-254).

Élargissement taxonomique (`_broaden`, investors/service.py:238-274) si le
secteur demandé n'a aucun investisseur tagué : parent → secteurs voisins →
appel LLM parmi les secteurs réellement peuplés en dernier recours. Un
« avertissement méthodologique » est injecté en tête du contexte
(`format_context`, investors/service.py:355-357) si un élargissement a eu
lieu, et la directive exige de l'annoncer dès l'introduction du rapport
(prompts.py:259-262).

**Cache en mémoire de process** (`investors/client.py:38-40`, `_cache`/
`_cache_at`/`_lock`, TTL 3600 s) : même limite structurelle que le cache
Notion documenté dans le bilan « conversations » (constat 13) — non
partagé entre workers, non purgé, réinitialisé à chaque redémarrage.
`GET /investors/mapping` sert le même moteur sans passer par
`run_analysis` — un utilisateur peut consulter la liste courte sans jamais
générer (ni payer) le rapport narratif complet.

### 4.6 Type « custom »

**N'existe pas.** Les sept types sont fermés (`ANALYSIS_DIRECTIVES`), il
n'y a pas de mécanisme de directive personnalisée par l'utilisateur. Seule
échappatoire : `POST /reports` (création manuelle, §2) qui contourne
entièrement le pipeline de génération et permet d'enregistrer n'importe
quel `title`/`content`/`analysis_type` (y compris une chaîne inventée, non
validée par `is_valid_type`) sans jamais produire de rapport « généré ».

---

## 5. Cycle de vie : liste, pagination, suppression, renommage, archivage, rapports hérités, régénération

- **Liste** : `GET /reports` retourne l'intégralité des rapports de
  l'utilisateur, triés `created_at desc`, **sans pagination**
  (`service.list_reports`, reports/service.py:34-40 ; router.py:49-56
  n'expose aucun paramètre `limit`/`offset`) — même constat que pour les
  conversations dans le bilan précédent.
- **Suppression** : `DELETE /reports/{id}` **existe** (contrairement au
  module `intelligence`, qui n'a aucun endpoint de suppression) —
  `service.delete_report` vérifie l'appartenance (`get_report`, lève
  `AppError 404` sinon) puis `db.delete` + `db.commit` (reports/service.py:
  50-53). Suppression définitive, pas de corbeille ni de `deleted_at`.
- **Renommage** : **aucun endpoint**. `ReportIn.title` n'est utilisable
  qu'à la création manuelle (`POST /reports`) ; aucun `PATCH`/`PUT` sur
  `/reports/{id}`.
- **Archivage** : **aucune colonne, aucun endpoint**. Contrairement à
  `Project.archived_at` (module `intelligence`), `Report` n'a même pas de
  colonne prévue pour ça.
- **Régénération** : **aucun endpoint**. Un rapport dégradé n'est jamais
  persisté (§3.7) — il n'y a donc rien à « régénérer » depuis l'archive ;
  relancer signifie soumettre une nouvelle requête `/analysis/run` ou
  `/analysis/stream`, qui débite à nouveau les crédits en cas de succès.
- **Rapports hérités** (`app/modules/reports/legacy.py`) : import
  **déclenché à chaque connexion** (`register`, `login`, `reset-password`
  — `auth/router.py:26, 32, 82`, fonction `_restore_legacy`), pas
  seulement à l'inscription. Idempotent par construction
  (`imported_at.is_(None)` dans la requête de sélection, legacy.py:117-
  120) mais **relance une requête SQL sur `legacy_reports` à chaque
  login**, même pour un compte n'ayant jamais eu de rapport hérité — coût
  systématique et permanent (une requête `SELECT` filtrée par email, sans
  cache), jamais désactivé une fois qu'un compte est confirmé sans
  rapport en attente.
  - Les rapports importés sont marqués (`imported_at`, `imported_for`) et
    copiés dans `reports` avec `sources=None` (aucune citation structurée
    n'est reconstituée depuis l'ancienne plateforme, legacy.py:132) — ce
    qui explique le traitement défensif de `export_pdf`
    (`sources = report.sources if isinstance(report.sources, list) else
    None`, reports/service.py:60).
  - Un bonus de 30 crédits (`RETURN_BONUS_CREDITS`, legacy.py:77) est
    accordé une fois à un utilisateur reconnu comme « ancien » —
    reconnaissance élargie au-delà des rapports : une adresse simplement
    **contactée par la campagne de migration email** (`EmailSend`,
    legacy.py:66-71) compte aussi comme « connue », même sans rapport à
    restaurer — commentaire explicite : « sur 42 destinataires, 25
    n'avaient rien produit et seraient restés dans le silence complet »
    (legacy.py:63-65).
  - `onboarding.rattraper` (`analysis/onboarding.py:112-148`) exclut
    explicitement les comptes dont **tous** les rapports sont des imports
    hérités (sous-requête `NOT EXISTS` comparant `reports.title` tronqué à
    `legacy_reports.title`, onboarding.py:132-137) — un compte avec
    uniquement des rapports restaurés reste éligible au premier rapport
    offert, un compte ayant produit au moins un vrai rapport ne l'est
    plus.
- **Premier rapport offert** (`analysis/onboarding.py`) : déclenché par
  `POST /analysis/premier-rapport`, gratuit (`is_admin=True` au moment de
  `finalize`), une seule fois par compte via une entrée `credit_events`
  delta `0` marquée **avant** la génération (onboarding.py:87-91,
  commentaire explicite : « deux appels simultanés ne doivent pas produire
  deux rapports offerts »). **Absence de contrainte d'unicité** en base sur
  `(user_id, action)` dans `credit_events` (`billing/models.py:62-74`) —
  la protection contre le double-appel simultané repose entièrement sur la
  vérification applicative (`deja_offert`, un `SELECT ... LIMIT 1`) sans
  verrou ni contrainte SQL : une vraie concurrence exacte (deux requêtes
  HTTP arrivant dans la même fenêtre, avant qu'aucune n'ait committé sa
  marque) pourrait produire deux rapports offerts. Le routeur
  (`router.py:69-70`) fait de plus une vérification préalable
  (`onboarding.deja_offert`) **avant même de lancer le thread**, doublant
  ce contrôle non atomique.

---

## 6. Tests

Fichiers concernés : `tests/test_analysis.py` (81 lignes),
`tests/test_billing_reports.py` (50 lignes), `tests/test_pdf_rapports.py`
(114 lignes), `tests/test_troncature.py` (partiellement, 290 lignes),
`tests/test_viz_core.py` (104 lignes), `tests/test_viz_pipeline.py`
(43 lignes), `tests/test_viz_service.py` (43 lignes).

### Ce qui est couvert

| Test | Fichier:ligne | Couvre |
|---|---|---|
| `test_all_types_have_context_slot` | test_analysis.py:17-21 | chaque type a bien `{context}`, `is_valid_type` |
| `test_unknown_type_raises` | test_analysis.py:24-27 | 400 sur type inconnu |
| `test_degrades_when_llm_unavailable` | test_analysis.py:30-40 | dégradation quand aucun LLM disponible |
| `test_default_template_fallback` | test_analysis.py:43-44 | repli sur `synthese_executive` |
| `test_analysis_routes_mounted` | test_analysis.py:47-54 | routes montées, auth publique/protégée |
| `test_le_style_exige_une_synthese_executive_en_tete`, `test_le_style_demande_un_bloc_viz_et_plus_la_marque_graphique` | test_analysis.py:57-68 | présence des règles dans `OUTPUT_STYLE` |
| `test_reprise_apres_troncature`, `test_abandon_apres_trois_reprises` | test_troncature.py:48-81 | reprise Claude sur `max_tokens`, plafond de reprises |
| `test_rapport_tronque_non_facture` | test_troncature.py:84-92 | `finalize()` sur un résultat dégradé ne facture ni n'archive |
| `test_angles_couvrent_le_reglementaire`, `test_angles_sans_type_connu`, `test_angles_suivent_la_langue_de_la_question` | test_troncature.py:101-133 | `angles_de_recherche` |
| `test_rapport_survit_a_la_fermeture_du_navigateur` | test_troncature.py:150-199 | archivage malgré `gen.close()` côté serveur — **le seul test de survie mi-flux de tout le backend rapports/conversations** |
| `test_premier_rapport_offert_une_seule_fois` | test_troncature.py:202-209 | `question_pour` (construction depuis le profil) |
| `test_cost_canonical_and_aliases`, `test_plans_present`, `test_free_beta_grant_matches_catalog` | test_billing_reports.py:11-31 | coûts canoniques et alias, cohérence grant/plan |
| `test_pdf_is_generated` | test_billing_reports.py:34-36 | PDF valide généré |
| `test_billing_reports_routes_mounted` | test_billing_reports.py:39-50 | routes `/reports*` montées, auth publique/protégée |
| `test_les_citations_deviennent_des_liens_internes`, etc. | test_pdf_rapports.py:6-40 | citations → liens `#src-N`, tableaux cellule par cellule |
| `test_la_section_sources_du_modele_est_remplacee_par_celle_des_donnees`, `test_sans_sources_fournies_la_section_du_modele_est_conservee` | test_pdf_rapports.py:43-56 | dédoublonnage Sources modèle vs Sources générées |
| `test_un_tableau_marque_graphique_est_trace_et_le_tableau_disparait`, etc. | test_pdf_rapports.py:60-115 | marque legacy « Graphique : », blocs viz → image PDF, repli tableau si spec invalide |
| Tout `test_viz_core.py`, `test_viz_pipeline.py`, `test_viz_service.py` | — | schéma `VizSpec`, sélection de `kind`, compilation Vega-Lite/PNG/SVG, extraction depuis markdown, idempotence par empreinte |

### Ce qui n'est PAS couvert (absence vérifiée par recherche, aucun test trouvé)

- Aucun test d'intégration bout-en-bout de `run_analysis`/`finalize` avec
  une vraie session DB (persistance réelle du `Report`, du `viz`, débit
  réel des crédits) — tous les tests qui touchent `service.py` mockent
  `run_analysis` ou `finalize`, ou n'exercent que `angles_de_recherche`/
  `get_prompt_template` en isolation pure.
- Aucun test du chemin `finalize()` en cas d'échec de `create_report`
  **après** que `consume_credits` a déjà committé (§3.9) — le scénario
  « crédits débités, aucun rapport archivé » n'est vérifié nulle part.
- Aucun test de `POST /reports` (création manuelle arbitraire, §2) — ni de
  son absence de validation de `analysis_type`.
- Aucun test de `DELETE /reports/{id}` au-delà du montage de route
  (`test_billing_reports_routes_mounted` vérifie seulement que le chemin
  existe dans l'OpenAPI, pas le comportement métier).
- Aucun test de la course entre les deux vérifications `deja_offert`
  (router + `onboarding.offrir`) sur `/analysis/premier-rapport` en
  concurrence réelle (§5).
- Aucun test de `legacy.restore_for`/`grant_return_bonus` end-to-end (avec
  une vraie table `legacy_reports` peuplée) — le comportement n'est vérifié
  qu'indirectement via `question_pour`, qui ne touche pas la restauration
  elle-même.
- Aucun test de `investors.map_for_profile`/`search`/`_broaden` (le module
  `investors` n'a aucun fichier de test dédié trouvé — recherche
  `test_investor*` infructueuse).
- Aucun test de `/viz/{empreinte}.svg`/`.png` (accès public, en-têtes de
  cache) au niveau routeur — seuls `render.py`/`pipeline.py`/`service.py`
  sont testés en isolation.
- Aucun test du calcul de coût de recherche web bout-en-bout
  (`cout_recherche_micro_eur` réellement persisté sur un `Report`) — seul
  le tarif unitaire est implicite dans `billing/couts.py`, non exercé par
  un test dédié trouvé.
- Aucun test de `/analysis/run` (chemin bloquant non-stream) au-delà du
  montage de route et de l'auth — pas de test de persistance, ni de
  comportement en cas de déconnexion client sur ce chemin (§3.12).
- Aucun test de pagination (normal : la fonctionnalité n'existe pas).
- Aucun test de renommage/archivage de rapport (normal : aucun endpoint
  n'existe).
- Aucun test de feedback (normal : aucun mécanisme structuré n'existe).
- Aucun test des alias legacy dupliqués `analysis.prompts._ALIASES` vs
  `billing.catalog._ALIASES` pour vérifier qu'ils restent synchronisés.

---

## 7. Observabilité

### Logs

Logger dédié `logging.getLogger("axial.analysis")` (service.py:28), et
loggers voisins `axial.reports.pdf`, `axial.reports.legacy`,
`axial.reports.notification`, `axial.viz`, `axial.viz.render`,
`axial.investors`, `axial.analysis.onboarding`, `axial.analysis.router`.
Niveaux `warning` sur tout échec absorbé (RAG, recherche web, Notion,
génération, notification email, restauration legacy, bonus retour),
`info` sur les statistiques de dédoublonnage de recherche et les blocs viz
en repli (`viz/service.py:26-27`). Comme pour les conversations, aucun log
structuré (JSON) dédié « rapport » — pas de `report_id` corrélé
systématiquement dans chaque ligne de log de `analysis/service.py` (le
`report_id` n'existe d'ailleurs pas encore au moment où la plupart des logs
d'échec sont émis, puisque le rapport n'est créé qu'après génération
réussie).

### Métriques (`app/modules/metrics/service.py`)

- `couts(db, jours)` (metrics/service.py:33-56) : agrégat direct sur
  `reports` — nombre total, nombre mesurés (`count(cout_micro_eur)`),
  coût total/moyen/max en euros, durée moyenne, tokens entrée/sortie
  cumulés. `non_mesures = rapports - rapports_mesures` calculé
  explicitement (les rapports antérieurs au 25/08 sans coût mesuré ne sont
  **pas** comptés à zéro dans la moyenne — « les inclure à zéro ferait
  croire à une marge parfaite », commentaire metrics/service.py:7-8).
- `par_type(db, jours)` (metrics/service.py:59-90) : coût réel moyen
  confronté au prix affiché (`cost_for`), par `analysis_type` — calcule
  une marge € et % **uniquement** si au moins un rapport de ce type a un
  coût mesuré (`mesure = mesures > 0`), sinon `None` explicite plutôt
  qu'une fausse marge à 100 %.
- `_poste(db, "reports", jours)` (metrics/service.py:167-195), agrégé dans
  `couts_totaux` : contrairement au poste `conversations` (coût de
  recherche codé en dur à `0`, bilan « conversations » constat 5), le
  poste `rapports` lit réellement `cout_recherche_micro_eur` — avec un
  filet explicite si la colonne n'existe pas encore en base (ordre de
  déploiement migration/code inversé, `try/except` + `db.rollback()`,
  metrics/service.py:185-195).
- `activite(db, jours)` (metrics/service.py:111-133) compte
  `actifs_rapport` (utilisateurs distincts ayant produit un rapport dans
  la fenêtre) séparément de `actifs_question` (conversations) ; `actifs`
  = le max des deux.
- `delai_premier_rapport(db)` (metrics/service.py:136-164) : délai moyen
  entre inscription et premier **vrai** rapport (exclut explicitement les
  rapports restaurés de l'ancienne plateforme via la même jointure
  anti-legacy que `onboarding.rattraper`, §5).

### Vue admin du coût d'un rapport

- **Agrégé** : `GET /metrics/tableau` (`metrics/router.py:18-24`, réservé
  `is_admin`) expose `couts` (agrégat global rapports) et `par_type`
  (marge par type d'analyse) — **avec** le coût de recherche, contrairement
  au poste conversations.
- **Par rapport individuel** : **aucun endpoint n'expose le coût d'un
  rapport précis**. `ReportOut`/`ReportDetail` (`reports/router.py:26-36`)
  ne renvoient ni `cout_micro_eur`, ni `tokens_entree/sortie`, ni `modele`,
  ni `cout_recherche_micro_eur`, ni `appels_recherche`, ni
  `duree_secondes` au client — ces champs sont écrits en base
  (contrairement aux conversations, ils sont même **mieux mesurés** ici,
  §3.8) mais ne sont lus par aucune route. Le même écart entre « mesuré »
  et « exposé » que documenté pour les conversations (bilan précédent,
  constat 6) existe ici, alors même que l'instrumentation sous-jacente
  est plus complète.
- **Export brut** (`GET /metrics/export`) : agrège `couts_totaux` sur 10
  ans mais ne détaille pas non plus par rapport individuel.

---

## Constats bruts

Liste factuelle, sans recommandation — chaque ligne est vérifiable au
fichier:ligne cité.

1. **Aucun état « en cours » persisté pour un rapport.** `Report` n'a pas
   de colonne `status` (`reports/models.py:18-43`) : un rapport n'existe en
   base qu'une fois `finalize()` committé avec succès. Toute la
   progression communiquée pendant la génération transite uniquement par
   les événements SSE de `/analysis/stream` (service.py:321-410) — un
   client qui recharge la page pendant une génération en cours perd tout
   état de progression et ne verra le rapport apparaître que dans
   `GET /reports`, sans savoir qu'une génération est active.

2. **Facturation et archivage sont deux transactions distinctes, non
   atomiques.** `finalize()` (service.py:272-304) committe d'abord le
   débit de crédits (`billing.consume_credits`, billing/service.py:121-
   122), puis committe séparément la création du `Report`
   (`reports.create_report`, reports/service.py:28-30). Si la seconde
   étape échoue après que la première a réussi, l'utilisateur est facturé
   sans qu'aucun rapport n'existe, et aucun mécanisme de remboursement
   automatique n'est déclenché. Aucun test n'exerce ce scénario (§6).

3. **`POST /reports` permet de créer un « rapport » arbitraire sans passer
   par le pipeline de génération** (`reports/router.py:39-46`) : ni
   `is_valid_type` ni aucune validation de cohérence entre `content` et
   `analysis_type` ; aucun coût, aucun débit de crédits, aucune preuve
   qu'une génération a réellement eu lieu. Ce chemin de création coexiste
   avec le pipeline `analysis` sans lien entre les deux.

4. **Les images de graphiques sont servies sans authentification, à
   n'importe qui connaissant l'empreinte SHA-256** (`viz/router.py:31-37`,
   `Cache-Control: immutable, max-age=31536000`). La protection est
   uniquement l'imprévisibilité de l'empreinte, jamais vérifiée contre
   l'appartenance de l'utilisateur au rapport source — assumé
   explicitement en commentaire (« comme un lien de partage »,
   `viz/router.py:1-4`) mais un rapport entier partagé involontairement
   (capture d'écran d'URL, email transféré) expose ses graphiques
   indéfiniment.

5. **Course non protégée par contrainte SQL sur le premier rapport
   offert.** La protection contre un double-appel simultané de
   `/analysis/premier-rapport` repose entièrement sur une lecture
   applicative (`onboarding.deja_offert`, un `SELECT ... LIMIT 1`) répétée
   à deux endroits (routeur avant de lancer le thread, puis à nouveau dans
   `offrir()` avant de marquer l'événement) — sans verrou ni contrainte
   d'unicité `(user_id, action)` sur `credit_events`
   (`billing/models.py:62-74`). Une vraie concurrence exacte pourrait
   produire deux rapports gratuits pour le même compte.

6. **`ANALYSIS_PROMPTS` (prompts.py:434) est un artefact mort en
   production.** Le dictionnaire pré-calculé n'est consulté par aucun code
   applicatif — `run_analysis` appelle toujours `get_prompt_template`
   directement (service.py:158) — et n'est référencé que par
   `tests/test_analysis.py:12,18,44`.

7. **Deux dictionnaires d'alias legacy indépendants, à synchroniser
   manuellement.** `analysis/prompts.py:300-305` (`_ALIASES`) et
   `billing/catalog.py:24-29` (`_ALIASES`) contiennent la même
   correspondance (`market_study`, `competition`, `tech_watch`,
   `risk_analysis`) mais sont deux objets Python distincts, sans source
   commune — une modification de l'un sans l'autre romprait silencieusement
   soit le routage du prompt, soit le coût facturé, pour un même alias.

8. **`legacy.restore_for` interroge `legacy_reports` à chaque connexion**,
   même pour un compte qui n'a jamais eu de rapport hérité et le restera
   toujours (`auth/router.py:26, 32, 82`, appelé sur `register`, `login`
   **et** `reset-password`) — une requête `SELECT` filtrée par email à
   chaque authentification, jamais mise en cache ni désactivée une fois le
   compte confirmé sans rapport en attente.

9. **Le coût de recherche web est mesuré pour les rapports, contrairement
   aux conversations** (`analysis/service.py:98-100` passe `compteur`,
   contre l'absence documentée dans le bilan « conversations » §3.7) — mais
   **cette mesure n'est exposée par aucune API** au client final :
   `ReportDetail` (reports/router.py:33-36) ne renvoie ni `cout_micro_eur`,
   ni `cout_recherche_micro_eur`, ni `tokens`, ni `modele`. Seul l'agrégat
   admin (`/metrics/tableau`) en bénéficie ; aucun endpoint ne détaille le
   coût d'un rapport individuel, pour l'utilisateur ou pour l'admin.

10. **Cache investisseurs en mémoire de process, même limite structurelle
    que le cache Notion documenté pour les conversations.**
    `investors/client.py:38-40` (`_cache`/`_cache_at`/`_lock`, TTL 3600 s)
    n'est pas partagé entre workers multiples, ne survit pas à un
    redémarrage, et se recharge intégralement (10k lignes, dix tables)
    dès la première requête après expiration ou redémarrage — un
    déploiement multi-process verra des TTL de cache investisseurs
    incohérents entre requêtes, exactement comme documenté pour Notion.

11. **`sources` sur `Report` peut être un scalaire non-liste sur d'anciens
    rapports restaurés**, ce que `export_pdf` gère explicitement
    (`isinstance(report.sources, list)`, reports/service.py:60) — sans
    validation stricte du schéma JSON en base (`JSON`/`JSONB` brut, aucune
    contrainte CHECK), n'importe quelle valeur JSON reste théoriquement
    acceptable pour cette colonne à l'écriture directe.

12. **`/analysis/run` (chemin bloquant) n'a pas le mécanisme dédié de
    survie à la déconnexion construit pour `/analysis/stream`** — pas de
    session DB séparée dans un thread indépendant, pas de test équivalent
    à `test_rapport_survit_a_la_fermeture_du_navigateur`
    (test_troncature.py:150-199). Le comportement réel en cas de
    déconnexion sur ce chemin dépend du comportement par défaut de
    Starlette pour les endpoints synchrones, jamais vérifié explicitement
    pour ce module.

13. **Aucun mécanisme de feedback structuré sur un rapport.** La seule
    voie de retour est la réponse à l'email de notification
    (`notification.py:31`, « dis-le-moi en répondant à ce message ») — pas
    de table, pas de route, aucune donnée de satisfaction capturée par
    l'application elle-même.

14. **Aucun endpoint de renommage ni d'archivage de rapport**, alors que
    la suppression (`DELETE /reports/{id}`) existe — asymétrie inverse de
    celle du module `intelligence` (bilan « conversations » constat 3 :
    aucune suppression, colonne d'archivage à moitié câblée). Ici, aucune
    colonne d'archivage n'existe du tout sur `Report`.
