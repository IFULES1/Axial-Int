# Snapshot — 2026-08-13 (LE CŒUR fonctionne : recherche + LLM en réel)

## Doppler
- Toutes les clés migrées dans **Doppler** (projet `axial`, config `dev`). Lancer via `doppler run -- …`.
- `scripts/check_keys.py` : **7/7 clés valides** (Gemini, Cohere embed+rerank, Tavily, Exa, Linkup, Anthropic).

## Couche recherche + LLM implémentée et TESTÉE EN RÉEL
### Recherche multi-moteurs (`app/shared/search/`)
- `base.py` (SearchResult + Protocol), `providers.py` (Exa/Tavily/Linkup, fail-soft, normalisés),
  `rerank.py` (Cohere Rerank v3.5, fail-soft), `orchestrator.py` (fan-out parallèle → dédup URL canonique → rerank → top-K), `__init__.py` (search/format_sources).
- TESTÉ : requête FR → 3 moteurs fusionnés → 6 sources rerankées (francefintech.org, journaldunet…) scores 0.81-0.92.

### LLM 2 vitesses (`app/shared/llm_client/`)
- `gemini.py` (generate REST v1beta), `claude.py` (+ generate module-level), `__init__.py` :
  **`generate(system, prompt, tier)`** — tier="report"→Claude Sonnet, "chat"→Gemini. + `generation_available()`.
- **Modèle Gemini = `gemini-flash-latest`** (les `gemini-2.5-*` font 404 pour cette clé ; `-latest` = immunisé contre les retraits).

### `analysis.run_analysis` rebranché
- Nouveau flux : **search multi-moteurs (contexte externe) + RAG interne (best-effort) → prompt → PII guard → llm_client.generate(tier)**.
- Fini Perplexity + l'enrich séparé (remplacés par le 2 vitesses). Sources = résultats web (title/url/domain/provider/score).
- Param `tier` ajouté (défaut "report").

## TESTÉ bout-en-bout (doppler run)
Requête « taille marché fintech B2B France 2025 » → **degraded=False, provider=gemini, 6 sources** →
rapport structuré, chiffré, cité (France FinTech 2025, Finance Innovation 2025, +36%, 755M€…). **Le produit marche.**

## Config ajoutée (`app/config.py`)
exa/tavily/linkup/cohere/gemini keys, `search_providers=exa,tavily,linkup`, `search_topk`, `rerank_model=rerank-v3.5`,
`embedding_provider=cohere`, `embedding_model_cohere=embed-multilingual-v3.0`, `embedding_dim_cohere=1024`,
`llm_chat_model=gemini-flash-latest`, `llm_report_model=claude-sonnet-5`, `search_provider_list` (property).

## RESTE À FAIRE
1. **Embeddings → Cohere** : `rag/embeddings.py` encore sur OpenAI (RAG interne skippé faute d'OPENAI_API_KEY).
   Basculer sur Cohere embed (input_type search_query/document, dim 1024). Corpus vide → pas de ré-index.
   `vector_store.EMBEDDING_DIM` à rendre dynamique (1024 pour Cohere).
2. **Front** : brancher le chat (Workspace) + Rapports sur le vrai backend (la plomberie front est prête ; le chat est encore mock).
   - Chat/agents → tier="chat" (Gemini). Rapports → tier="report" (Claude).
3. Vérifier tier="report" (Claude) e2e (routage simple, Claude déjà validé).
4. Ajouter les nouvelles clés à Doppler **prd** aussi (plus tard, pour la prod).

## Lancement (rappel)
- Backend : `doppler run -- .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090 --reload` (Postgres brew requis).
- Front : `cd frontend && doppler run -- npm run dev -- -p 3005`.
- Test cœur : `doppler run -- .venv/bin/python -c "from app.modules.analysis import service; ..."`.
- Doc décisions : `docs/BENCHMARK_APIS_ET_DECISIONS.md`.

## Snapshots
…, wiring2 (front crédits/identité), coeur (recherche+LLM réels — LE cœur marche).
