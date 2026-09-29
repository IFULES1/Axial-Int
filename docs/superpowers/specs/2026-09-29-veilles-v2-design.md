# Veilles v2 — rendre les 4 étapes réelles (design, 29/09/2026)

Suite du bilan `2026-09-29-bilan-veilles.md`, §2 : deux des quatre étapes de
l'assistant de création sont décoratives et affichent des affirmations fausses.
Ce document décrit ce que devient chaque étape, et le mécanisme qui la rend
réelle à l'exécution.

Décision prise par Miradie le 29/09 : **les quatre formats de livrable
deviennent quatre comportements distincts**, avec un coût différencié.

---

## Principe directeur

Le pipeline des rapports possède déjà le mécanisme qui manque à la veille :
`prompts.sources_de(analysis_type)` renvoie un dictionnaire de booléens et
`run_analysis` n'appelle que les sources à `True`. La veille reprend cette
convention plutôt que d'en inventer une autre — même forme, même vocabulaire,
un lecteur qui connaît un module comprend l'autre.

Règle de bord : **aucune étape n'affiche une source ou un livrable dont le code
ne sait rien faire.** LinkedIn, les fils de communiqués et Google Drive sortent
de l'assistant — ils n'existent nulle part dans le dépôt.

---

## Étape 1 — Sujet & skill

Déjà réelle. Deux correctifs :

1. La liste des skills est servie par `GET /watches/skills` (route et helper
   `axWatchSkills` déjà écrits, jamais appelés) au lieu d'être recopiée en dur
   dans l'assistant. Ajouter un skill au backend le fera apparaître dans l'app.
2. Sous le choix du skill, un aperçu des flux qu'il va réellement lire —
   le composant `AgentFeedsLine` existe déjà sur la carte d'agent, il est
   réutilisé ici avant validation.

Rien à migrer.

## Étape 2 — Sources

### Modèle
Nouvelle colonne `watches.sources`, JSON, même forme que `sources_de` :

```json
{"rss": true, "web": true, "documents": false, "notion": false}
```

Défaut à la création : `{"rss": true, "web": true, "documents": false,
"notion": false}` — le comportement actuel, pour que les 5 agents existants
n'en changent pas. La migration écrit ce défaut sur les lignes existantes.

### Ce que l'étape affiche
Les quatre familles réelles, chacune cochable :

| Famille | Ce qui est appelé | Disponibilité |
|---|---|---|
| **Flux RSS** | `_feeds_for` + `rss.fetch_new_articles`, filtrés par les catégories du skill | toujours, avec le nombre de flux du skill affiché |
| **Recherche web** | `web_search.search_multi` (Exa, Tavily, Linkup) sur les 4 angles du skill | toujours |
| **Vos documents** | `analysis.service._retrieve_context(subject, user_id, top_k)` | grisé si l'utilisateur n'a aucun document indexé |
| **Votre espace Notion** | `integrations.notion_context.passages_pour(db, user_id, subject)` | grisé si Notion n'est pas connecté |

Décocher tout est refusé côté API : une veille sans source ne produit rien.

### Exécution
`run_watch` lit `watch.sources` et n'appelle que ce qui est à `True`. Les
passages « documents » et « Notion » rejoignent le pool avant le rerank, avec
la même numérotation `[n]` que les articles RSS et les résultats web — la
fonction `_format_sources` du moteur de veille est étendue pour les accepter,
elle range déjà RSS et web dans un pool commun.

Un run dont toutes les sources activées n'ont rien rendu est archivé avec
`had_changes=False` et une note explicite, **sans appel au modèle et sans
débit** — aujourd'hui il paie un rapport sur du vide.

### Écarté
Une sélection de flux **par agent** (table `watch_feeds`) : deux migrations,
et l'utilisateur doit arbitrer flux par flux dès la création. Le filtre par
catégorie de skill est un proxy suffisant tant qu'un compte a moins d'une
dizaine d'agents. À rouvrir si un utilisateur demande deux agents du même skill
sur des sources différentes.

## Étape 3 — Livrable

### Modèle
Nouvelle colonne `watches.format`, `String(20)`, parmi
`alerte | digest | mini_rapport | flux`. Défaut `digest` pour les lignes
existantes ; **`alerte` proposé par défaut aux nouveaux agents**.

### Les quatre comportements

| Format | Rapport complet | Email | Coût |
|---|---|---|---|
| **Alerte** | non — delta seul | seulement si `had_changes` | **2 crédits** |
| **Digest** | oui | à chaque run | 5 crédits |
| **Mini-rapport** | oui, consigne de volume plus longue | à chaque run, PDF joint | 5 crédits |
| **Flux continu** | oui | jamais — tout reste dans l'app | 5 crédits |

Trois interrupteurs suffisent, tous déjà présents dans `run_watch` sous forme
de conditions en dur : produire ou non `FULL_REPORT`, envoyer ou non l'email,
l'envoyer ou non quand `had_changes` est faux.

### Facturation
`catalog.CREDIT_COSTS` gagne `run_agent_veille_alerte: 2` à côté de
`run_agent_veille: 5`. `run_watch` choisit l'action selon le format, ce qui
garde une seule table de vérité pour les coûts et laisse l'historique de
crédits lisible (« Alerte de veille » vs « Veille »).

Le format `alerte` n'appelle le modèle qu'une fois, avec un prompt qui ne
demande que `HAD_CHANGES`, `DELTA` et `ROLLING_STATE` — la section
`FULL_REPORT` du gabarit `_OUTPUT_INSTRUCTION` est retirée, ce qui divise la
sortie par trois environ (1 300 caractères contre 5 000).

Effet attendu, sur les chiffres du bilan : les 510 crédits consommés à ce jour
seraient tombés autour de 240.

### Migration des agents existants
Les 5 agents passent en `digest` : leur comportement ne change pas. Un bandeau
dans la fiche d'agent propose le passage en Alerte avec l'économie chiffrée
d'après leur propre historique (« sur vos 30 derniers runs, 2 ont rapporté
quelque chose »).

## Étape 4 — Cadence

### Modèle
`watches.cadence` reste `daily | weekly | manual`. **`hourly` et `realtime`
disparaissent de l'assistant** — ils n'existaient que dans l'affichage et
étaient ramenés en silence à `daily`.

Nouvelle colonne `watches.heure_locale`, `SmallInteger`, défaut `7` : l'heure
de livraison souhaitée, en heure de Paris. Aujourd'hui `next_run_at = création
+ 24 h`, donc l'heure d'un run est celle de sa création — d'où des veilles qui
tombent à 10h49, 14h22 et 16h29. `_next_run` calcule désormais le prochain
passage à `heure_locale` le lendemain (ou le lundi suivant en hebdomadaire),
converti en UTC.

### Estimation de coût
Le bloc « ~210 crédits / mois » en dur est remplacé par un calcul :
`crédits_du_format × runs_par_mois(cadence)`, recalculé à chaque changement.
Quotidien + Alerte = 60 crédits/mois ; quotidien + Digest = 150 ; hebdo +
Digest = 22.

### Écarté pour l'instant
**« Dès qu'il se passe quelque chose »** : une passe RSS seule toutes les
heures, sans modèle ni crédit, qui ne déclenche un run complet que si un
article nouveau correspond au sujet. C'est la seule lecture honnête de « temps
réel », et c'est un vrai mécanisme (une demi-journée) : un `tick_rss` distinct
dans le worker, un seuil de correspondance, et une borne quotidienne pour que
l'utilisateur ne se réveille pas avec dix runs. À traiter comme un chantier à
part une fois Veilles v2 en production.

---

## Ce que ça touche

| Fichier | Nature |
|---|---|
| `alembic/versions/0026_veilles_v2.py` | 3 colonnes (`sources`, `format`, `heure_locale`) + valeurs par défaut sur l'existant |
| `app/modules/watches/models.py` | les 3 colonnes |
| `app/modules/watches/skills.py` | gabarit de sortie par format |
| `app/modules/watches/engine.py` | `_format_sources` étendue (documents, Notion) ; `_OUTPUT_INSTRUCTION` variable selon le format |
| `app/modules/watches/service.py` | `run_watch` lit `sources` et `format` ; `_next_run` gère `heure_locale` ; run sans source = pas de débit |
| `app/modules/watches/router.py` | `WatchIn`/`WatchOut` portent les 3 champs, validation « au moins une source » |
| `app/modules/billing/catalog.py` | `run_agent_veille_alerte: 2` |
| `frontend/app/_prototype/App.jsx` | `AgentWizard` : skills depuis l'API, sources réelles, 4 formats, cadences réelles + heure, estimation calculée |
| `tests/test_veilles_v2.py` | nouveau |

## Tests

Le bilan relève que `run_watch` n'a **aucun** test aujourd'hui. Cette spec ne
sera pas implémentée sans, parce que chaque format est une branche de cette
fonction :

- chaque format produit le bon couple (rapport complet oui/non, email oui/non)
- `alerte` sans nouveauté : pas d'email, 2 crédits débités
- `alerte` avec nouveauté : email envoyé, 2 crédits
- `digest` sans nouveauté : email envoyé quand même, 5 crédits
- `flux` : jamais d'email quel que soit `had_changes`
- toutes sources décochées → refus à la création (422)
- toutes sources activées sans résultat → run archivé, **aucun crédit débité**
- `sources` restreint à `{rss}` : aucun appel web
- `heure_locale` : `_next_run` tombe bien à l'heure demandée, changement d'heure
  d'été compris
- migration : les 5 agents existants ressortent en `digest`, sources
  `{rss, web}`, et leur comportement est identique au run précédent

## Ordre d'implémentation

1. Tests de `run_watch` sur le comportement **actuel** — filet avant de toucher
   à quoi que ce soit (c'est aussi le correctif #17 du bilan).
2. Migration + colonnes + lecture dans `run_watch`, comportement inchangé à
   valeurs par défaut.
3. Les quatre formats et leur facturation.
4. Les quatre sources et le run sans source non facturé.
5. Cadence, heure de livraison, estimation calculée.
6. Assistant refait sur ces bases.
