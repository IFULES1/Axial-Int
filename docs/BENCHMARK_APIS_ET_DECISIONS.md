# Benchmark APIs IA & décisions — Axial Intelligence

> Document de référence pour le choix des briques IA. Prix **indicatifs** (début 2026,
> marché mouvant) — vérifier les tarifs live avant engagement. L'architecture, elle, ne
> dépend pas des centimes.

## 0. Usage réel qui guide le choix
- Analyses sourcées façon cabinet, en **français** (et anglais).
- Recherche web qui doit aller **plus large** que des sources imposées (pas de restriction stricte de domaines).
- Besoin de **trier/hiérarchiser** les infos remontées par plusieurs moteurs pour une **synthèse globale**.
- **RAG** sur documents utilisateurs → embeddings **FR+EN** de qualité.
- B2B européen, système de crédits → **coût par analyse maîtrisé**, stratégie 2 vitesses.
- 3 briques à optimiser séparément : **recherche web**, **embeddings (+rerank)**, **LLM de synthèse**.

---

## 1. Recherche web — DÉCISION : Exa + Tavily + Linkup (multi-moteurs)
Objectif : couverture large (chaque moteur a un index/approche différents) puis **agrégation + tri + synthèse**.

| API | Type | Perf | Prix indicatif | Rôle chez nous |
|---|---|---|---|---|
| **Exa** | recherche neurale/sémantique | ★★★★☆ | ~5$/1000 + contenu | trouver des sources de fond, requêtes conceptuelles |
| **Tavily** | recherche pour RAG/agents | ★★★★☆ | free 1k/mois puis très cheap | résultats propres, rapides, orientés synthèse |
| **Linkup** | answer + sources (EU) | ★★★☆☆ | compétitif | citations, couverture complémentaire |
| Gemini Grounding | answer engine | ★★★★★ | ~35$/1k ancrées | option chat libre (non retenu comme socle) |
| Perplexity Sonar | answer engine | ★★★★☆ | tokens + frais | écarté : boîte noire sur les sources |
| Brave / Serper | recherche pure | ★★★☆☆ | cheap | secours / complément low-cost |

**Décision** : brancher **Exa + Tavily + Linkup** en parallèle, normaliser les résultats, dédupliquer, **reranker** (voir §2), garder le top-K pour la synthèse.

---

## 2. Embeddings + Rerank — DÉCISION : Cohere (les deux)
**Un seul modèle d'embeddings en prod** (impossible de mélanger des espaces vectoriels ; re-indexer si on change).

| Modèle | Qualité FR+EN | Prix indicatif /1M | Note |
|---|---|---|---|
| **Cohere embed-multilingual-v3** ✅ | ★★★★★ | ~0,10$ | FR+EN excellents, int8/compression, **même vendeur que le rerank** |
| Voyage-3-lite (alternative) | ★★★★★ | ~0,02-0,06$ | meilleur q/p brut ; 2 vendeurs si combiné au rerank Cohere |
| OpenAI text-embedding-3-small (actuel) | ★★★★☆ | 0,02$ | bon défaut, à remplacer pour +qualité FR |
| BGE-m3 (open-source) | ★★★★☆ | 0$ API | auto-hébergeable (Qdrant déjà en place) |

**Rerank (le « tri »)** : **Cohere Rerank v3 multilingue** — score la pertinence requête↔document sur **tous** les résultats agrégés (Exa+Tavily+Linkup) → tri global avant synthèse. C'est LE mécanisme de tri demandé.

**Décision** : **Cohere** = embeddings (`embed-multilingual-v3`) **+** rerank (`rerank-v3`). Une clé, un vendeur, FR+EN.
*(Option : Voyage-3-lite pour l'embed si on veut le meilleur q/p, en gardant Cohere Rerank.)*

---

## 3. LLM de synthèse — DÉCISION : Gemini (q/p) + Claude Sonnet (rapports finaux)
Stratégie **2 vitesses**, alignée sur le système de crédits.

| Modèle | Qualité analyse FR | Prix indicatif (in/out /1M) | Rôle |
|---|---|---|---|
| **Gemini 2.x Flash** ✅ | ★★★★☆ | ~0,075$/0,30$ | **chat, brouillons, questions rapides** (cheap, rapide, gros contexte) |
| **Gemini 2.x Pro** ✅ | ★★★★☆ | moyen | analyses intermédiaires si besoin |
| **Claude Sonnet** ✅ | ★★★★★ | ~3$/15$ | **rapports finaux** (qualité cabinet) |
| Claude Opus | ★★★★★ | ~15$/75$ | premium exceptionnel uniquement |
| Mistral | ★★★★☆ | ~2$/6$ | écarté (préférence Gemini) — restait l'angle RGPD |
| DeepSeek | ★★★★☆ | très cheap | écarté (hébergement chinois, B2B EU) |

**Décision** : **Gemini** (Flash par défaut, Pro au besoin) pour le q/p, **Claude Sonnet** pour les rapports finaux payants.

---

## 4. Stack retenue (récap)
| Brique | Choix | Clé env |
|---|---|---|
| Recherche web | **Exa + Tavily + Linkup** (multi + agrégation) | `EXA_API_KEY`, `TAVILY_API_KEY`, `LINKUP_API_KEY` |
| Tri / rerank | **Cohere Rerank v3** | `COHERE_API_KEY` |
| Embeddings | **Cohere embed-multilingual-v3** (ou Voyage-3-lite) | `COHERE_API_KEY` (ou `VOYAGE_API_KEY`) |
| LLM chat/brouillon | **Gemini Flash** | `GEMINI_API_KEY` |
| LLM rapport final | **Claude Sonnet** | `ANTHROPIC_API_KEY` |

---

## 4bis. Prix LIVE (vérifiés août 2026) & coût par analyse

### Tarifs réels
| Brique | Modèle | Prix | Offre gratuite |
|---|---|---|---|
| Recherche | **Exa** | **7$/1000** recherches (0,007$), 10 résultats inclus (+1$/1k au-delà) ; Deep 12-15$/1k ; Contents 1$/1k | 20$ à l'inscription + **10$/mois** |
| Recherche | **Tavily** | basic = 1 crédit, advanced = 2 ; PAYG **0,008$/crédit** ; 30$/mois = 4000 cr ; Growth 500$ = 100k (0,005$) | **1000 crédits/mois** |
| Recherche | **Linkup** | **5$/1000** (0,005$) ; Deep 50$/1k ; Fetch 0,001-0,005$ | 20$ à l'inscription, **rechargé à 20$/mois** (~4000 rech.) |
| Rerank | **Cohere Rerank** | par recherche (1 req + ≤100 docs) : 0,001$ (v3.5), 0,002$ (Fast), 0,0025$ (Pro) | essai |
| Embeddings | **Cohere Embed 4** | **0,12$/1M** tokens (texte) | essai |
| LLM q/p | **Gemini 2.5 Flash** | **0,30$ / 2,50$** par 1M (in/out) ; Flash-Lite 0,10$/0,40$ | free tier |
| LLM final | **Claude Sonnet 5** | **2$ / 10$** par 1M (promo → 31/08), puis **3$/15$** | — |

> ⚠️ Gemini 2.5 retiré le **16/10/2026** → prévoir la génération suivante de Flash. Claude Sonnet repasse à 3$/15$ au **01/09**.
> Batch API = -50% (Gemini & Claude) ; cache input = -90% (Gemini) / -90% (Claude cache hit) → leviers d'optimisation.

### Coût estimé d'UNE analyse
Hypothèse : 3 moteurs (1 rech. chacun) + 1 rerank + contexte ~12k tokens in / ~3k out.
| Poste | Coût |
|---|---|
| Recherche (Exa+Tavily+Linkup) | ~0,02-0,03$ |
| Rerank Cohere | ~0,001-0,0025$ |
| Embeddings (par requête) | négligeable |
| **LLM Gemini Flash** (brouillon/chat) | ~0,011$ (12k×0,30 + 3k×2,50 /1M) |
| **LLM Claude Sonnet** (rapport final) | ~0,054$ (promo) → 0,081$ (tarif plein) |
| **TOTAL brouillon (Gemini)** | **≈ 0,04-0,05$ / analyse** |
| **TOTAL rapport final (Claude)** | **≈ 0,08-0,11$ / analyse** |

**Lecture** : le **LLM de sortie double le coût** (Flash ~0,045$ vs Sonnet ~0,11$) → la **stratégie 2 vitesses** est justifiée chiffres à l'appui. La **recherche (~0,03$)** pèse car on interroge 3 moteurs : en prod, réserver les 3 aux **analyses profondes** et n'en garder 1-2 pour le chat rapide (config `SEARCH_PROVIDERS`).

**Calibrage crédits** : avec un coût réel de ~0,05-0,11$/analyse, une marge saine se cale facilement (ex. 1 rapport = X crédits où 1 crédit ≈ 0,01-0,02$ facturé). Vérifier les prix avant de figer la grille.

Sources : [Exa](https://exa.ai/docs/reference/pricing) · [Tavily](https://coldiq.com/blog/tavily-pricing) · [Linkup](https://docs.linkup.so/pages/documentation/platform/pricing) · [Cohere](https://www.aipricing.guru/cohere-pricing/) · [Gemini](https://ai.google.dev/gemini-api/docs/pricing) · [Claude](https://pecollective.com/tools/anthropic-api-pricing/)

---

## 5. Comment mettre en place (implémentation)

Le socle est déjà prêt : `app/shared/llm_client/` est **provider-agnostique** (Protocols). On étend le même patron.

### 5.1 Couche recherche (nouveau : `app/shared/search/`)
- `base.py` : `SearchProvider` (Protocol) + `SearchResult` (title, url, snippet, content, domain, score, published_at).
- `exa.py`, `tavily.py`, `linkup.py` : 3 adaptateurs qui normalisent vers `SearchResult`.
- `orchestrator.py` :
  1. **fan-out** parallèle de la requête aux providers activés (`SEARCH_PROVIDERS`),
  2. **dédup** (par URL canonique + similarité de titre),
  3. **rerank Cohere** sur l'union des résultats → score de pertinence unique,
  4. renvoie le **top-K** (ex. 8-12) comme contexte de synthèse.
- Config : `SEARCH_PROVIDERS=exa,tavily,linkup`, `SEARCH_TOPK=10`, `RERANK_PROVIDER=cohere`.

### 5.2 Embeddings provider-agnostiques (`app/modules/rag/embeddings.py`)
- Aujourd'hui : OpenAI en dur. À rendre configurable : `EMBEDDING_PROVIDER=cohere|voyage|openai`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`.
- Adaptateurs `cohere_embed()`, (opt.) `voyage_embed()`.
- **Migration Qdrant** : la dimension de la collection doit matcher le modèle. Changer d'embed = **re-indexer tout le corpus** (nouvelle collection `documents_v2` avec la bonne dim, ré-embed, bascule). Script `scripts/reindex_embeddings.py`.

### 5.3 LLM 2 vitesses (`app/shared/llm_client/`)
- Ajouter adaptateurs `gemini.py` (Google GenAI SDK) et garder `claude.py`.
- Config : `LLM_CHAT_MODEL=gemini-2.x-flash`, `LLM_REPORT_MODEL=claude-sonnet-...`.
- `analysis/service.py` : choisir le modèle selon l'action — chat/brouillon → Gemini ; rapport final (payant) → Claude Sonnet. Le prompt système + templates restent identiques.

### 5.4 Nouveau flux d'une analyse
```
requête utilisateur
  → search.orchestrator (Exa + Tavily + Linkup en //)
  → dédup + Cohere Rerank → top-K sources
  → (+ RAG interne : Cohere embed → Qdrant)
  → construire le contexte cité
  → LLM synthèse : Gemini (brouillon/chat) | Claude Sonnet (rapport final)
  → rapport sourcé (APA) + garde PII (déjà en place)
```

### 5.5 Variables .env à ajouter
```
# Recherche web
EXA_API_KEY=
TAVILY_API_KEY=
LINKUP_API_KEY=
SEARCH_PROVIDERS=exa,tavily,linkup
SEARCH_TOPK=10
# Rerank + embeddings
COHERE_API_KEY=
RERANK_PROVIDER=cohere
EMBEDDING_PROVIDER=cohere
EMBEDDING_MODEL=embed-multilingual-v3.0
EMBEDDING_DIM=1024
# LLM
GEMINI_API_KEY=
LLM_CHAT_MODEL=gemini-2.5-flash
LLM_REPORT_MODEL=claude-sonnet-5
ANTHROPIC_API_KEY=
```

### 5.6 Ordre de mise en œuvre conseillé
1. Fournir les clés (Exa, Tavily, Linkup, Cohere, Gemini, Anthropic).
2. Implémenter `search/` (3 adaptateurs + orchestrator + rerank Cohere) — testable seul.
3. Basculer `embeddings` sur Cohere + script de ré-indexation Qdrant.
4. Ajouter l'adaptateur Gemini + logique 2 vitesses dans `analysis`.
5. Test e2e : une analyse → sources multi-moteurs triées → rapport Gemini/Claude.
6. Brancher au front (chat + rapports) — la plomberie front est prête.

### 5.7 À noter
- **Coût par analyse** piloté surtout par le LLM de sortie (Flash ≈ centimes vs Opus ≈ dizaines de centimes) → d'où le 2 vitesses.
- Embeddings/rerank = postes mineurs ; optimiser la **qualité FR/EN**, pas le prix.
- Chaque provider de recherche a des quotas/latences différents ; l'orchestrateur doit **dégrader proprement** si l'un tombe (patron déjà utilisé côté LLM).
- Prix à **re-vérifier en live** avant de fixer la grille de crédits.

---

## Historique des décisions
- 2026-08-13 : recherche = Exa+Tavily+Linkup (multi, large) ; tri = Cohere Rerank ; embeddings = Cohere (1 seul modèle) ; LLM = Gemini (q/p) + Claude Sonnet (final) ; Gemini préféré à Mistral.
