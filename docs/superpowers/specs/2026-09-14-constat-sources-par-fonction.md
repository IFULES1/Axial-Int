# Constat — sources de données par fonction (14/09/2026)

État du code tel qu'il tourne en prod le 14/09. Base de discussion pour la
matrice cible (à arbitrer avec Miradie).

## Matrice actuelle

| Fonction | Web (Exa + Tavily + Linkup) | Rerank Cohere | Documents de l'utilisateur (RAG) | Base de connaissance Axial (kb) | Notion | Google Drive | Base investisseurs | Flux RSS |
|---|---|---|---|---|---|---|---|---|
| Conversations (3 agents) | oui (sauf message trivial), 6 résultats | oui | oui, 6 passages | oui, ~250 docs | oui si connecté | non | non | non |
| Étude de marché | oui, multi-angles, 40 sources | oui | oui | oui, ~250 docs | oui si connecté | non | non | non |
| Synthèse exécutive / étude personnalisée | oui, 40 | oui | oui | oui, ~250 docs | oui si connecté | non | non | non |
| Cartographie concurrentielle | oui, 30 | oui | oui | oui, ~250 docs | oui si connecté | non | non | non |
| Veille réglementaire | oui, 30 | oui | oui | oui, ~250 docs | oui si connecté | non | non | non |
| Analyse de risques | oui, 25 | oui | oui | oui, ~250 docs | oui si connecté | non | non | non |
| Veille technologique | oui, 25 | oui | oui | oui, ~250 docs | oui si connecté | non | non | non |
| Cartographie investisseurs | oui, 30 (angles secondaires) | oui | oui | oui, ~250 docs | oui si connecté | non | **oui, obligatoire, interrogée en premier** | non |
| Agents de veille | oui, multi-angles, 12 | oui | **non** | non | **non** | non | non | oui (catalogue par catégorie) |
| Livraison Notion / Drive | — | — | — | — | écriture | écriture | — | — |

## Ce que ça veut dire

- **Tous les types de rapport interrogent exactement les mêmes sources.** Seuls
  changent les angles de recherche (`key_angles` de la directive) et le prompt.
  La seule branche conditionnelle est la base investisseurs pour la
  cartographie investisseurs (`app/modules/analysis/service.py:530-556`).
- **Aucun filtre de domaine ni de fraîcheur** n'est passé aux fournisseurs
  web, quel que soit le type. Une veille réglementaire cherche comme une étude
  de marché. Exa et Tavily supportent nativement `include_domains` /
  `exclude_domains` / dates : le paramètre n'est simplement pas propagé
  (`app/shared/search/providers.py`, `orchestrator.py`).
- **Les agents de veille ignorent les documents, Notion et la base
  investisseurs.** Leur pool de sources (`watches/engine.py:_format_sources`)
  est une copie de `grounding.assemble` au lieu de le réutiliser.
- **La base de connaissance Axial (`knowledge_base` dans Qdrant) est bien
  alimentée** : 79 078 vecteurs, ~250 documents en 6 catégories
  (macro-institutionnel, sectoriel, réglementaire, marché-benchmarks,
  méthodologie, littérature stratégie), ingérés en août par
  `scripts/ingest_knowledge_base.py` depuis `data/knowledge_base/` (1,5 Go
  sur le serveur). Payload : `user_id="__kb__"`, `doc_id`, `title`,
  `filename`, `category`, `source`, `sector`. Elle est lue à chaque requête et
  répond (vérifié le 14/09). Ce qui manque : un écran admin pour y ajouter ou
  retirer des documents sans passer par le script, et une étiquette
  « base Axial » visible dans les citations. (Correction du constat initial,
  qui la disait vide.)
- **Google Drive n'est jamais une source**, seulement une destination.
- **Perplexity, Pappers et Serper** sont déclarés dans la configuration (et un
  tarif Serper existe) mais aucun code ne les appelle : fournisseurs fantômes.
- Caches Notion et investisseurs en mémoire de processus, valides seulement
  en mono-worker.

## Pipelines, fichier par fichier

- **Conversations** — `app/modules/intelligence/service.py:_rechercher` (930-974) :
  requête = titre du fil + question ; web (`web_search.search`, 6) et RAG
  (`rag.retrieve`, 6, collections `documents` + `knowledge_base`) en parallèle ;
  Notion ajouté (`notion_context.passages_pour`) ; fusion `grounding.assemble`
  (top 8, un seul rerank). Message < 25 caractères sans pièce jointe : aucune
  recherche. Documents joints au message : injectés en contexte prioritaire,
  hors rerank (3 max, 8 000 caractères chacun).
- **Rapports** — `app/modules/analysis/service.py:run_analysis` (446-576) :
  `top_k = min_sources` du type (`prompts.py:143-287`) ; angles
  (`angles_de_recherche`, 6 max, traduits si la question est en anglais) ;
  `search_multi` : `max(5, top_k // 2)` résultats par angle et par fournisseur,
  dédup par URL, un rerank final contre la question ; RAG sans plafond ; Notion ;
  fusion. Recherche élargie (`elargir=True`) = une passe d'angles
  supplémentaires générés par le modèle, une seule fois.
- **Cartographie investisseurs** — `app/modules/investors/service.py:map_for_profile`
  (309-385) : base Supabase distincte, lecture seule, 10 tables en cache 1 h ;
  résolution secteur / stade (onboarding, sinon LLM), score par société de
  gestion, élargissement taxonomique jusqu'à 3 niveaux ; aucune correspondance =
  rapport refusé sans débit ; citations investisseurs numérotées en tête.
- **Agents de veille** — `app/modules/watches/service.py:run_watch` (159-249) :
  flux RSS filtrés par catégories du skill (`skills.py`, catalogue
  `data/rss_feeds.csv`, 25 par flux, 60 max, seulement les articles nouveaux) ;
  web `search_multi` (12) ; mémoire roulante ~400 mots ; contexte entreprise ;
  12 sources max après rerank.
- **Documents / RAG** — `documents/service.py:ingest` (extraction, chunk,
  embedding Cohere `embed-multilingual-v3.0`, Qdrant) ; `rag/service.py:retrieve`
  interroge `documents` (filtré par utilisateur) et `knowledge_base` (globale).
- **Notion en lecture** — `integrations/notion_context.py` : 12 pages les plus
  récemment modifiées, 4 000 caractères par page, cache 10 min, sans filtre de
  pertinence côté Notion (c'est le rerank qui trie).

## Points d'extension

1. **Ajouter un fournisseur web** : classe dans `providers.py` (`name`,
   `available`, `search`), enregistrement dans `_REGISTRY`, ajout dans
   `search_providers` (config), tarif `tarif_recherche_*`.
2. **Choisir les sources par type de rapport** : n'existe pas. À créer : un
   champ `sources` dans `ANALYSIS_DIRECTIVES` (ex. `{"web": true, "rag": true,
   "notion": true, "investisseurs": false, "domaines": [...], "fraicheur_jours": n}`)
   lu par `run_analysis`.
3. **Filtres de domaine et de fraîcheur** : à ajouter aux adaptateurs Exa /
   Tavily / Linkup et à propager depuis `search` / `search_multi`.
4. **Base de connaissance** : `vector_store.upsert_chunks(..., collection=KB_COLLECTION)`
   est prêt ; il manque un pipeline d'ingestion admin (CCI, INPI, Pépites,
   textes réglementaires…).
5. **Veille** : réutiliser `grounding.assemble` pour brancher documents, Notion
   et base investisseurs.
6. **Nombre de sources et angles** : déjà paramétrables par type
   (`sources_for`, `key_angles`).
