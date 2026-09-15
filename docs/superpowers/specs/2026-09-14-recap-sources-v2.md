# Sources v2 — récapitulatif (15/09/2026)

Spec : `2026-09-14-sources-v2.md`. Plan : `docs/superpowers/plans/2026-09-14-sources-v2.md`.
Exécution SDD du 14 au 15/09 : 8 tâches d'implémentation, une revue par tâche,
tours de correction, revue finale de la branche (voir §6).

## 1. Ce qui est branché

| Décision (14/09) | Livré | Où |
|---|---|---|
| Filtres de fraîcheur et de domaines selon la question et le type de rapport | `contraintes_pour(question, type)` : par type (réglementaire 365 j + domaines officiels, risques / techno 365 j, marché / concurrentiel / synthèse / investisseurs 730 j), par mots de la question (actualité 90 j, année 365 j, loi / règlement 365 j + officiels, « historique / depuis 20xx » = aucun filtre) ; propagé à Exa (`startPublishedDate`, `includeDomains`), Tavily (`time_range`, `include_domains`), Linkup (`fromDate`, `includeDomains`), Perplexity (`search_recency_filter`, `search_domain_filter`). Domaines inclus = privilégiés : relance sans eux si le pool est vide. | `app/shared/search/contraintes.py`, `providers.py`, `orchestrator.py` |
| Filtre de pertinence | Sources sous le score Cohere `SEUIL_PERTINENCE_RECHERCHE` (0,30) écartées, au moins 3 gardées ; jamais appliqué sans scores réels. `compteur["_ecartes"]`. | `rerank.py` |
| Recherche à niveaux, du plus performant au moins performant | `SEARCH_TIERS = "perplexity,exa\|tavily,linkup"` : le niveau 2 n'est interrogé que si le niveau 1 n'a pas fourni assez de sources pertinentes ; `compteur["_niveaux"]`. Perplexity ajouté comme moteur (`sonar`, résultats sourcés → `SearchResult`). | `orchestrator.py`, `providers.PerplexityProvider`, `config.search_tiers` |
| Pappers pour l'étude de marché et la cartographie concurrentielle | Noms de sociétés extraits (profil + modèle tier chat sur les extraits web, 8 max) → fiches Pappers (SIREN, forme, création, NAF, effectif, siège, dirigeants, derniers comptes) ajoutées au pool AVANT le rerank ; cache 24 h par SIREN ; citation « (registre : pappers.fr) ». | `app/shared/enrich/pappers.py`, `analysis/service.py` |
| Sources par type de rapport | Champ `sources` de chaque directive (`web`, `rag`, `notion`, `investisseurs`, `pappers`) lu par `run_analysis` ; prompts inchangés d'un octet. | `analysis/prompts.py` |
| Base investisseurs en conversation | `question_de_levee` (regex bornée FR/EN) → `map_for_profile` en parallèle du web (délai 8 s), citations investisseurs numérotées en tête, libellé « Base investisseurs Axial ». | `investors/service.py`, `intelligence/service.py` |
| Base de connaissance Axial | Table `kb_documents` (migration `0024_sources_v2`), rattrapage automatique des 148 documents existants au premier listage, routes admin (`/admin/kb`), écran « Base de connaissance Axial » en bas de Pilotage (dépôt de fichier, URL, catégorie, liste, suppression). Limite 20 Mo, nettoyage HTML sans dépendance, encodage respecté. **Invisible côté utilisateur** : les citations internes s'affichent « Document de référence ». | `app/modules/kb/`, `App.jsx` (`PilotageSurface`) |
| Drive comme source | `POST /integrations/google/importer` (export Docs / Sheets / Slides, binaire), bouton « Importer depuis Drive » dans Mémoire via Google Picker, scope `drive.file` inchangé. Affiché seulement si Google est configuré côté serveur ET si les deux variables navigateur existent. | `integrations/{service,router}.py`, `App.jsx`, `bridge.js` |
| Santé réelle des fournisseurs | `GET /health/providers?reel=1` (admin) : appel de test par fournisseur, 8 s max, latence et erreur masquée. | `app/shared/health.py`, `main.py` |
| Veilles | inchangées (décision). | — |

## 2. Clés et variables à poser (Miradie)

| Variable | Où | Effet si absente |
|---|---|---|
| `PERPLEXITY_API_KEY` | Doppler `prd` | Perplexity ignoré, cascade sans lui |
| `PAPPERS_API_KEY` | Doppler `prd` | pas de fiches Pappers |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Doppler `prd` | tuile Drive et import Drive masqués |
| `NEXT_PUBLIC_GOOGLE_API_KEY`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | `frontend/.env.local` (rebuild du front) | bouton « Importer depuis Drive » masqué |
| `SEARCH_TIERS` (facultatif) | Doppler | défaut `perplexity,exa\|tavily,linkup` |
| `SEUIL_PERTINENCE_RECHERCHE` (facultatif) | Doppler | défaut 0,30 |

Google Cloud : créer un client OAuth « application web » (URI de redirection
`https://app.axial-ia.fr/api/integrations/google/callback`), activer l'API
Google Drive et l'API Google Picker, créer une clé d'API restreinte au domaine
`app.axial-ia.fr` pour le Picker. Tarifs codés « à confirmer » :
`TARIF_RECHERCHE_PERPLEXITY_MICRO_EUR` (5 000), `TARIF_RECHERCHE_PAPPERS_MICRO_EUR`
(20 000, par fiche).

## 3. Base de connaissance, état au 15/09

148 documents, 43 188 vecteurs, après retrait de 128 documents hors sujet
(fichiers dans `data/knowledge_base/00_retires/`) et ajout de 35 documents
(baromètres France Digitale / EY, France Invest, EY capital-risque, French
Tech, CNIL, AI Act, AMF, INPI, INSEE, Banque de France, Galion, Bpifrance,
CCI Paris, Pépite France). Décision en attente : retrait des livres du
commerce de la catégorie « littérature stratégie ».

## 4. Ce qui n'a pas été vérifié en conditions réelles

- Perplexity et Pappers : schémas de réponse déduits de la documentation,
  aucune clé disponible ; à contrôler dès les clés posées via
  `GET /health/providers?reel=1` puis un rapport de test.
- Google Picker : non exercé sans identifiants Google.
- Exa, Tavily, Linkup : paramètres validés contre les vraies API le 14/09.

## 5. Reliquats et décisions prises en cours d'exécution

- Le bloc investisseurs n'apparaît qu'au message qui parle de levée, pas aux
  messages de suivi du même fil (choix conservateur, à revoir si gênant).
- Coût des appels modèle de `map_for_profile` en conversation non compté.
- `Passage.origine` de la spec remplacé par le champ existant `Passage.source`.
- Le script `scripts/ingest_knowledge_base.py` reste l'outil des lots en masse.

## 6. Revue finale et déploiement (15/09)

Revue finale de branche : DÉPLOYABLE, aucun bloquant, trois points
importants — deux corrigés avant déploiement (listage KB robuste à un Qdrant
lent ou absent, délai client Qdrant 10 s, titre borné à 500 caractères), un
reporté : le coût du rerank Cohere n'est pas compté alors que la cascade
peut reranker deux fois (à ajouter aux tarifs de recherche).

Déploiement : migration `0024_sources_v2` appliquée avant redémarrage,
262 tests Sources v2 verts sur le serveur, front rebâti avec parité
`BUILD_ID` = bundle = `/version` (1789461912), aucune erreur au journal.

Incident pendant le déploiement, corrigé : la suite de tests lancée sur le
serveur lisait le `QDRANT_URL` de Doppler et a écrit 127 points de test dans
la base de connaissance de prod ; retirés (43 188 points, état exact
d'avant), et `tests/conftest.py` force désormais Qdrant en mémoire pour tout
test. Deux points orphelins de l'ancienne collection `documents` retirés au
passage.

Parcours réel (compte QA, prod) : question « préparer notre levée de fonds en
seed : quels fonds VC cibler et quelles obligations réglementaires… » →
réponse en 2 crédits / 9,8 k tokens, sources [1]-[12] = base investisseurs
Axial en tête, [13]-[18] web, [19]-[20] guide France Digitale de la base de
connaissance rendu comme un document ordinaire. Écran admin de la base vérifié
en local (ajout par URL, échec nommé, suppression).

Non vérifié en prod (compte admin nécessaire) : `GET /health/providers?reel=1`
et l'écran Pilotage > Base de connaissance — à ouvrir par Miradie ; le premier
listage remplit `kb_documents` à partir des 148 documents existants.
