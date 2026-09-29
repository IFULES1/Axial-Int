# Bilan « Veilles » — synthèse (29/09/2026)

Même méthode que les bilans Conversations (`2026-09-10-bilan-conversations.md`)
et Rapports (`2026-09-11-bilan-rapports.md`) : lecture du code backend
(`app/modules/watches/*`, `worker/main.py`) et frontend (`App.jsx`
6490-7150), chiffres de production lus en base le 29/09, et journal du worker
sur 60 jours.

---

## 1. Comment ça marche aujourd'hui

### Le parcours utilisateur
1. Menu « Agents » → bibliothèque de cartes, plus trois boutons :
   « Historique » (tous les runs), « Sources RSS » (catalogue + flux perso),
   « Créer un agent ».
2. Assistant en 4 étapes : *sujet & skill* → *sources* → *livrable* →
   *cadence*. Seules les étapes 1 et 4 sont réellement transmises au backend.
3. À la création, les flux RSS du catalogue correspondant au skill sont
   attachés automatiquement au compte (`amorcer_flux`) : un agent n'est
   jamais aveugle au premier run.
4. Carte d'agent : skill, cadence, date du dernier run, ligne repliable
   « Sources : N flux » avec une pastille de santé par flux (vert / rouge /
   gris).
5. Fiche d'agent : « Lancer maintenant », « Pause / Reprendre », une timeline
   des runs à gauche, et à droite le détail du run sélectionné — *Nouveautés
   (delta)* puis *Rapport complet*.
6. Si une adresse a été saisie, chaque run part aussi par email (HTML, avec
   les graphiques en images hébergées).

### L'architecture d'un run (`watches/service.py::run_watch`)
| Étape | Détail |
|---|---|
| Crédits | `check_credits` AVANT tout appel ; si insuffisant → run sauté, reprogrammé, **aucune trace côté utilisateur** |
| Sources RSS | flux actifs des catégories du skill, entrées **plus récentes que le dernier run** et jamais vues (`_prior_seen_urls` sur tout l'historique) |
| Sources web | 4 requêtes : le gabarit du skill + 3 angles (`search_multi`), 12 résultats, rerank Cohere sur le sujet |
| Mémoire | `rolling_state` du run précédent injecté dans le prompt — c'est ce qui rend la veille cumulative au lieu d'amnésique |
| Modèle | tier `report` (Claude Sonnet), `max_tokens=6000` ; reprise automatique sur troncature héritée de `claude.generate` (jusqu'à 3 relances) |
| Sortie | un seul appel produit 4 sections délimitées : `HAD_CHANGES`, `DELTA`, `FULL_REPORT`, `ROLLING_STATE` |
| Archivage | `watch_runs` : delta, rapport complet, mémoire, sources, URLs RSS consommées, tokens, coût modèle, coût recherche |
| Facturation | `consume_credits` **après** l'archivage : 5 crédits, quel que soit le résultat |
| Email | envoyé si destinataire + préférence `findings` — **même quand il n'y a rien de neuf** |
| Reprogrammation | `next_run_at = now + 1 jour` (ou 1 semaine) ; `manual` = jamais programmé |
| Worker | tick toutes les 60 s (`run_due_watches`), + récap hebdo le lundi 6 h UTC |

### Données de production (29/09)
| Mesure | Valeur |
|---|---|
| Agents en base | **5**, répartis sur **4 comptes** — sur 31 comptes au total (13 %, contre 81 % qui ont au moins un rapport) |
| Dont comptes externes réels | **1** (`g.desrocques@venturix.bzh`, éolien offshore) ; les 3 autres sont Miradie ×2, France Digitale, QA |
| Cadences | 4 quotidiennes, 1 hebdomadaire |
| Runs exécutés | **104** (33 en août, 71 en septembre ; 75 sur les 30 derniers jours) |
| Runs « avec du nouveau » | **34 / 104 = 33 %** — donc **67 % des runs ne rapportent rien** |
| Par agent | éolien 10/12 (83 %), concurrentielle 13/36 (36 %), financement 8/25 (32 %), **marché 2/30 (7 %)** |
| Coût réel mesuré (87 runs) | 0,075 € de modèle + 0,069 € de recherche = **0,144 € par run** |
| Coût cumulé de la veille | **12,52 €** pour 104 runs |
| Crédits consommés | **510** (102 événements) — **premier poste de consommation de l'app**, devant les messages d'agent (128) et tous les rapports réunis |
| Tokens | 6 765 en entrée / 4 066 en sortie en moyenne ; l'entrée est passée de 5 433 (août) à 7 065 (septembre), **+30 % en un mois** |
| Volume produit | delta 1 295 caractères, rapport complet 3 709 (max 5 706), 11 à 12 sources citées |
| Flux RSS | 33 flux, **tous vérifiés OK, aucun en erreur** ; 14 articles neufs par run en moyenne |
| Mais | **39 runs sur 104 (37 %) n'ont consommé aucun article RSS** — la veille reposait alors sur la seule recherche web |
| Mémoire roulante | 2 792 caractères en moyenne, jusqu'à **4 207** — la consigne demande « ~400 mots max » (≈ 2 800) |
| Sorties au-delà du plafond | 8 runs à ≥ 5 800 tokens (plafond demandé 6 000, max observé 7 513) — c'est la **reprise automatique sur troncature** du client Claude qui a fonctionné, pas un bug |

### Incidents réels trouvés en production
- **Un agent est mort en silence il y a trois semaines.** `a3f0d323`
  (France Digitale, skill financement) : solde à 0 crédit, dernier run réel le
  **08/09**, toujours affiché « actif » dans l'app. Le journal du worker montre
  le message `skipped: insufficient credits` à chaque passage depuis au moins
  le 22/09 (7 occurrences conservées). Personne n'a été prévenu.
- **Le seul utilisateur externe va subir la même chose demain.**
  `g.desrocques@venturix.bzh` a **6 crédits** ; un run en coûte 5. Son agent —
  le plus productif de tous, 83 % de runs avec du nouveau — s'éteindra
  silencieusement au run suivant.
- **3 agents sur 5 portent un nom faux.** Ils s'appellent tous « Veille
  concurrentielle » alors que leurs skills sont *financement*, *concurrentielle*
  et *marché*. Le nom par défaut a été corrigé depuis (`nomParDefautVeille`),
  mais **aucune route ne permet de renommer** : ces trois-là resteront mal
  nommés.

### L'arithmétique de l'offre ne tient pas
Un agent **quotidien** consomme 5 × 30 = **150 crédits par mois**.
Le plan **Pro** (50 €) en donne **120**, et sa page d'offre promet
« **2 agents de veille** » — soit 300 crédits pour une dotation de 120.
Le plan Premium (90 €, 250 crédits) promet « jusqu'à 10 agents ».
Aucune limite de nombre d'agents n'est d'ailleurs appliquée dans le code.

À l'unité, la veille est pourtant la ligne la plus rentable de l'app :
0,144 € de coût réel contre 5 crédits, soit ≈ 2,08 € au tarif Pro — **93 % de
marge**. Le problème n'est pas le prix du run, c'est la cadence proposée par
défaut au regard de la dotation.

---

## 2. Ce que l'assistant de création raconte et qui n'existe pas

C'est le point le plus grave de ce bilan : **deux des quatre étapes de
l'assistant sont décoratives**, et elles affichent des affirmations fausses à
un utilisateur qui paie.

| Écran | Ce qui est affiché | Ce qui se passe |
|---|---|---|
| Étape 2 « Sources » | « Web public — **142 sources sectorielles, 28 régulateurs** », « Communiqués de presse — Wires : Reuters, PR Newswire, AFP », « LinkedIn — Publications + mouvements », « Google Drive — **Connecté · 1 248 documents** » | Aucune case n'est lue, rien n'est envoyé au backend. Les vraies sources sont les flux RSS du catalogue, choisis par le skill. Il n'y a ni LinkedIn, ni fil de communiqués, ni Drive. |
| Étape 3 « Livrable » | Digest quotidien / Alerte signalée / Mini-rapport / Flux continu | Jamais transmis. La sortie est toujours la même : delta + rapport complet + email. |
| Étape 4 « Cadence » | Toutes les heures / Quotidien / Hebdomadaire / **Temps réel** | « Toutes les heures » et « Temps réel » sont **silencieusement ramenés à quotidien**. La cadence `manual`, qui existe côté backend, n'est jamais proposée. |
| Étape 4 | « Estimation : **~210 crédits / mois** à cette cadence » | Valeur en dur, identique quelle que soit la cadence. Le vrai chiffre est 150 en quotidien, ≈ 22 en hebdomadaire. |

---

## 3. Ce que l'utilisateur ne peut pas faire
- **Renommer ou modifier un agent** : ni le nom, ni le sujet, ni le skill, ni
  la cadence, ni le destinataire. Aucune route `PATCH`/`PUT` n'existe.
- **Supprimer un agent depuis l'app** : la route `DELETE` et le helper
  `axDeleteWatch` existent, aucun bouton ne les appelle. Seule la pause permet
  d'arrêter la facturation.
- **Savoir pourquoi son agent ne produit plus** (crédits épuisés, échec de
  génération) : la carte affiche « actif » et une vieille date.
- **Voir les sources d'un run** : le champ `sources` est renvoyé par l'API et
  jamais affiché ; seules les références `[n]` du texte subsistent.
- **Voir ce qu'un run a coûté** : tokens et coûts sont en base depuis le 25/08,
  jamais exposés.
- **Exporter une veille** : ni PDF, ni Notion, ni Markdown — alors que les
  rapports ont les trois. L'email est la seule sortie.
- **Chercher dans l'historique**, ou remonter au-delà des 20 derniers runs
  (30 pour l'activité globale) : limites fixes, pas de pagination.
- **Choisir ses sources par agent** : les flux sont attachés au *compte*, pas à
  l'agent, et filtrés ensuite par la catégorie du skill.
- **Arrêter un run en cours**, ou savoir qu'il tourne : « Lancer maintenant »
  est une requête HTTP bloquante de 1 à 3 minutes, l'UI n'affiche que
  « Analyse… » et avale toutes les erreurs, y compris « crédits insuffisants ».

---

## 4. Irritants classés

### A. Bloquants pour la valeur
1. **Extinction silencieuse faute de crédits.** Déjà arrivé à 2 agents sur 5,
   dont le seul client externe. Rien dans l'app, rien par email, statut
   toujours « actif ».
2. **L'assistant décrit un produit qui n'existe pas** (§2) : sources
   fictives, livrables fictifs, cadences fantômes, estimation de coût fausse.
3. **67 % des runs ne rapportent rien mais coûtent 5 crédits et envoient un
   email.** Sur l'agent « marché », c'est 93 % des runs. L'utilisateur paie
   30 fois par mois pour apprendre 2 fois qu'il s'est passé quelque chose.
4. **La cadence par défaut (quotidienne) dépasse la dotation du plan Pro**
   (150 crédits contre 120), et l'offre promet 2 agents.
5. **Trois agents sur cinq portent un nom qui ne correspond pas à leur skill**,
   sans aucun moyen de les renommer.

### B. Frictions quotidiennes
6. Impossible de supprimer, modifier ou renommer un agent depuis l'app.
7. Sources et coût d'un run invisibles alors qu'ils sont en base.
8. Aucun export d'une veille.
9. « Lancer maintenant » sans progression, sans annulation, sans message
   d'erreur.
10. Un run sur trois ne lit aucun article RSS — sans que rien ne le signale,
    alors que c'est la différence entre une veille et une recherche web.
11. La préférence de notification annonce « Email immédiat dès qu'un agent
    publie une trouvaille **à confiance haute** » : il n'existe ni notion de
    confiance, ni immédiateté. C'est un email par run.

### C. Dette invisible mais coûteuse
12. **`run_watch` n'a aucun test.** Le chemin qui dépense des crédits, envoie
    des emails et reprogramme n'est couvert nulle part ; `run_due_watches` et
    `_reschedule` non plus. Les flux RSS, eux, ont plus de vingt tests.
13. **Débit et archivage non atomiques** : `db.add(WatchRun)` puis
    `consume_credits`, et le chemin d'échec ne fait aucun rollback explicite
    avant le commit de reprogrammation. Même faiblesse que celle corrigée pour
    les rapports et les conversations — non vérifiée ici faute de test.
14. ~~Aucune reprise sur troncature.~~ **Retiré le 29/09 après vérification :
    faux.** La veille appelle `llm_client.generate(tier="report")`, qui route
    vers `claude.generate`, lequel relance jusqu'à 3 fois sur
    `stop_reason == "max_tokens"` — exactement comme les rapports. Les 7 513
    tokens de sortie observés au-delà du plafond de 6 000 sont la **preuve**
    que la reprise tourne. Le « 5 rapports finissent sans ponctuation » venait
    d'une heuristique trop grossière : un rapport qui se termine par une puce
    finit sur une lettre.
15. **La mémoire roulante n'est pas bornée** : jusqu'à 4 207 caractères pour
    une consigne de ~2 800, et le coût d'entrée a grimpé de 30 % en un mois.
16. **`_prior_seen_urls` relit toutes les URLs de tous les runs passés** à
    chaque exécution, sans fenêtre ni purge.
17. **`analysis_type` est une colonne morte** : acceptée par l'API, stockée,
    renvoyée, jamais lue par aucun chemin de veille.
18. **La liste des skills est recopiée en dur dans l'assistant** ; la route
    `/watches/skills` et le helper `axWatchSkills` ne sont jamais appelés —
    ajouter un skill au backend ne le fait pas apparaître dans l'app.
19. **`amorcer_flux` saute toute catégorie déjà couverte** : un seul flux
    « tech » suffit à priver l'utilisateur de tous les autres flux tech du
    catalogue. D'où une couverture très inégale (12, 9, 7 et 5 flux selon le
    compte).
20. **Le catalogue RSS (`data/rss_feeds.csv`) est gitignoré** : non versionné,
    donc absent des revues et non reproductible ailleurs qu'en prod.
21. **`email_recipients` accepte n'importe quelle adresse** : on peut faire
    envoyer une veille quotidienne à un tiers qui n'a rien demandé.
22. Clés i18n orphelines : `agents.confidence`, `agents.last_finding`,
    `agents.sources`, `agents.wizard.trigger` ; le statut `idle` n'est jamais
    atteignable (`status` ∈ {active, paused}).
23. Aucune durée d'exécution mesurée pour un run, alors que les rapports la
    stockent.

---

## 5. Pistes — améliorer, simplifier, supprimer

### Améliorer
| # | Piste | Effet | Effort |
|---|---|---|---|
| 1 | **Prévenir quand un agent s'arrête** : statut `en_panne_de_credits` distinct, badge sur la carte, un email une seule fois. Et traiter les 2 cas en cours. | le client ne perd plus sa veille sans le savoir | faible |
| 2 | **Ne plus facturer un run sans nouveauté au plein tarif** : recherche + comparaison à 1 crédit, rapport complet facturé 5 seulement si `had_changes`. Sur les chiffres actuels : 510 crédits → ≈ 240. | le prix suit la valeur livrée | moyen |
| 3 | **Assistant honnête** (§2) : étape « sources » remplacée par les vrais flux du skill (le composant existe déjà sur la carte), étape « livrable » supprimée, cadences réduites à quotidien / hebdo / manuel, estimation calculée depuis la cadence. | l'app arrête d'affirmer des choses fausses | faible |
| 4 | **Renommer et modifier un agent** : route `PATCH /watches/{id}` + formulaire. | 3 agents sur 5 sont mal nommés | faible |
| 5 | **Supprimer depuis l'UI** (route et helper déjà écrits). | hygiène | très faible |
| 6 | **Afficher les sources et le coût d'un run** (déjà renvoyés / déjà en base). | transparence, cohérence avec les rapports | très faible |
| 7 | **Exporter une veille** en PDF (moteur des rapports) et vers Notion (connecteur existant). | la veille sort de l'email | moyen |
| 8 | **Lancement asynchrone avec état**, comme les rapports v2 : ligne créée à l'envoi, progression, erreur crédits affichée. | plus de bouton qui ment | moyen |
| 9 | **Signaler un run sans RSS** (« aucune source RSS neuve, veille basée sur le web »). | l'utilisateur sait ce qu'il lit | très faible |
| 10 | **Borner la mémoire roulante** (coupe dure à 3 000 caractères, sur une fin de phrase). La reprise sur troncature, elle, existe déjà. | coût d'entrée maîtrisé | faible |

### Simplifier
| # | Piste |
|---|---|
| 11 | `analysis_type` retiré du modèle, du schéma API et de la migration |
| 12 | Skills servis par `/watches/skills` au lieu d'être recopiés dans l'assistant |
| 13 | `_prior_seen_urls` borné (N derniers runs ou 90 jours) |
| 14 | `amorcer_flux` : attacher tous les flux des catégories du skill, pas seulement celles non couvertes |
| 15 | Clés i18n orphelines et statut `idle` supprimés |
| 16 | `data/rss_feeds.csv` versionné (sortie du `.gitignore` ou déplacement hors de `data/`) |
| 17 | Tests de `run_watch` : crédits insuffisants, échec de génération, facturation, reprogrammation, email selon `had_changes` |

### Supprimer ou trancher
| # | Élément | Question |
|---|---|---|
| 18 | Cadence quotidienne par défaut | 150 crédits/mois contre 120 dans le plan Pro. Basculer le défaut en hebdomadaire, baisser le prix du run, ou relever la dotation — trois décisions produit, une seule à prendre. |
| 19 | « 2 agents de veille » (Pro) / « 10 agents » (Premium) | Promesse non tenue et non appliquée dans le code : soit on l'applique, soit on la retire de l'offre. |
| 20 | Email à chaque run vs récap hebdomadaire | Le récap hebdo existe déjà dans le worker. Garder les deux, ou faire de l'email par run une option désactivée par défaut ? |
| 21 | « Trouvaille à confiance haute » | Construire une notion de confiance, ou réécrire le libellé de la préférence. |
| 22 | `email_recipients` libre | Restreindre à l'adresse du compte, ou demander une confirmation au destinataire. |

---

## 6. Ordre proposé
1. **Urgent** : alerte de fin de crédits + statut distinct (#1), et traiter les
   deux agents éteints — dont le seul client externe (#1).
2. **Honnêteté** : assistant aligné sur la réalité (#3), libellé des
   notifications (#21), mention « aucune source RSS neuve » (#9).
3. **Gestion** : renommer / modifier / supprimer (#4, #5).
4. **Décision produit** : facturation du « rien de neuf » (#2) et cadence par
   défaut vs dotation du plan (#18, #19).
5. **Lisibilité** : sources et coût d'un run, export (#6, #7).
6. **Robustesse** : lancement asynchrone et mémoire bornée (#8, #10), puis
   tests de `run_watch` (#17).
7. **Nettoyage** : #11 à #16.
