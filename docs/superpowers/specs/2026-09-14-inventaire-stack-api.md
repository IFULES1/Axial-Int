# Inventaire de la stack API et revue de consommation (14/09/2026)

## Fournisseurs

| Fournisseur | Rôle | Fonctions | Modèle / paramètres | Repli | Variable |
|---|---|---|---|---|---|
| Google Gemini | LLM tier `chat` | conversations, jugement de couverture, résumés de fil, angles élargis, veilles | `gemini-flash-latest`, 1 retry rapide sur 429 / 5xx | Claude | `GEMINI_API_KEY` |
| Anthropic Claude | LLM tier `report` | rapports (32 000 tokens, reprise sur troncature ×3) | `claude-sonnet-5` | Gemini | `ANTHROPIC_API_KEY` |
| Exa, Tavily, Linkup | recherche web, en éventail | conversations, rapports, veilles | timeout 20 s, échec individuel = liste vide, sans retry | les deux autres | `EXA_API_KEY`, `TAVILY_API_KEY`, `LINKUP_API_KEY` |
| Cohere | rerank + embeddings | toutes les fonctions à sources ; ingestion de documents | `rerank-v3.5`, `embed-multilingual-v3.0` (backoff ×6) | ordre heuristique | `COHERE_API_KEY` |
| Qdrant | vecteurs | documents, base de connaissance | | | `QDRANT_URL` |
| Supabase | auth + base principale ; base investisseurs (projet distinct) | tout ; cartographie investisseurs | | | `SUPABASE_*`, `INVESTOR_DB_*` |
| Stripe | paiement, abonnements | crédits, packs | dégrade en 503 | | `STRIPE_*` |
| Resend | emails transactionnels, séquences, notifications | tout l'emailing | | aucun | `RESEND_API_KEY` |
| Notion, Google | OAuth : lecture Notion, livraison Notion / Drive | contexte, export | | | `NOTION_*`, `GOOGLE_*` (absent) |
| Presidio | garde-fou PII | conversations | mode shadow, timeout 2 s | best-effort | `PRESIDIO_URL` |
| Pappers, Serper, Perplexity | déclarés, **jamais appelés** | — | | | non configurés |

`GET /health/providers` dit seulement si une clé est présente : ce n'est pas
un contrôle de santé réel.

## Consommation des 30 derniers jours (base de prod, 15/08 → 14/09)

| Fonction | Volume | Coût modèle | Coût recherche | Appels recherche |
|---|---|---|---|---|
| Études de marché | 12 terminées (+1 sources insuffisantes) | 5,25 € | 0,75 € | 135 |
| Cartographies concurrentielles | 2 | 0,30 € | 0,08 € | 15 |
| Cartographies investisseurs | 2 | 0,28 € | 0,10 € | 18 |
| Synthèses / risques / réglementaire | 6 terminées sans coût (restaurées), 1 sources insuffisantes, 1 annulée | 0 | 0 | 0 |
| Conversations | 43 réponses (566 tokens en moyenne) | 0,15 € | 0,05 € | — |
| Agents de veille | 63 exécutions, 305 crédits | non mesuré par run dans ces colonnes | | |
| **Total mesuré** | | **≈ 6 €** | **≈ 1 €** | 168 |

Un rapport coûte en moyenne 0,45 € de modèle et 0,06 € de recherche
(≈ 11 appels fournisseurs). Les tarifs de recherche codés dans `config.py`
(`TARIF_RECHERCHE_*`) sont marqués « à confirmer ».

Crédits sur 30 jours : 653 débités (305 veilles, 300 rapports, 48 messages) ;
1 460 accordés (400 achetés en packs, 260 essais, 210 migration, 200 geste
admin, 200 recharge admin, 150 tests QA, 60 rattrapage).

## Pannes observées sur 10 jours (journal prod)

- Gemini : 7 indisponibilités (`503`), bascule sur Claude ou retry réussi.
- Exa : 7 échecs (`503`), les deux autres fournisseurs ont couvert.
- Aucune 500 applicative, aucun rapport en échec pour cause fournisseur.
- Depuis le 14/09, chaque échec fournisseur envoie un email (dédup 1 h par
  fournisseur et type d'erreur) : `app/shared/notifier.py:notifier_fournisseur`,
  branché dans `search/providers.py`, `search/rerank.py`,
  `llm_client/__init__.py` (bascule = « repli actif », chaîne entière =
  « ÉCHEC »).

## Recharge et décisions

Le code ne voit pas les soldes des fournisseurs : ils se lisent sur leurs
tableaux de bord (Anthropic, Google AI Studio, Exa, Tavily, Linkup, Cohere,
Resend). À la consommation actuelle (≈ 7 € par mois de modèle + recherche
pour 16 rapports et 43 réponses), aucune recharge n'est urgente ; les échecs
Exa et Gemini du journal sont des `503` côté fournisseur, pas des quotas
épuisés. Points à trancher : garder trois fournisseurs de recherche (Exa seul
couvre l'essentiel, Tavily et Linkup doublonnent) ; passer Gemini en modèle
épinglé plutôt que `flash-latest` ; retirer Pappers / Serper / Perplexity de
la configuration ; confirmer les tarifs de recherche ; faire de
`/health/providers` un vrai contrôle (appel de test par fournisseur).
