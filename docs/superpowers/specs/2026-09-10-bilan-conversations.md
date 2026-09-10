# Bilan « Conversations » — synthèse (10/09/2026)

Sources : exploration backend (`2026-09-10-bilan-conversations-backend.md`),
exploration frontend (`2026-09-10-bilan-conversations-frontend.md`), et un
parcours réel en production le 10/09 à 14h01 (compte neuf, question libre de
80 caractères, tier `report`).

---

## 1. Comment ça marche aujourd'hui

### Le parcours utilisateur
1. Menu « Conversations » → panneau de gauche (liste, recherche sur le titre,
   « Nouvelle analyse ») + zone de fil.
2. État vide : 4 questions suggérées, générées depuis le profil entreprise
   (nom, secteur, stade, défi principal) ; repli sur 4 questions françaises
   codées en dur si le profil est vide.
3. Composer : zone de texte (Entrée envoie, Maj+Entrée saute une ligne),
   bouton d'import de document (joint au prochain message seulement),
   sélecteur « Conversation / Market Scanner / Competitor Radar » mémorisé
   globalement dans le navigateur, bouton Envoyer.
4. Premier envoi : le front crée le projet par défaut puis la conversation,
   puis ouvre un flux SSE. Le titre est dérivé de la première question.
5. Réponse : bandeau « AXIAL analyse — recherche web + base de
   connaissance… », puis les sources arrivent (événement dédié), puis le
   texte, puis le payload final (citations, graphiques `viz`).
6. Sur chaque réponse : bouton Copier. Sur le fil : export Markdown / PDF.

### L'architecture d'un tour de parole (backend)
| Étape | Détail | Résilience |
|---|---|---|
| Crédits | `check_credits` avant tout appel réseau (2 crédits fixes par message) | 402 si insuffisant |
| Contexte entreprise | `memory.build_context` (profil) | `""` si absent |
| Documents joints | max 3, 8 000 caractères chacun | ignorés si illisibles |
| Heuristique « trivial » | message < 25 caractères sans pièce jointe → aucune recherche | — |
| RAG + web | en parallèle : Qdrant (documents + base de connaissance) et Exa/Tavily/Linkup, puis rerank Cohere | chaque échec absorbé |
| Notion | pages de l'espace connecté, cache en mémoire de process | absorbé |
| PII | `guard_outbound` en mode `shadow` (n'altère rien en pratique) | — |
| Prompt système | conversation libre : Axial Conseil + VIZ + REGISTRE ; agent explicite : persona + règles communes + « AXIAL Recommande » + VIZ + REGISTRE ; miroir de langue ; instruction d'ancrage entreprise | — |
| Modèle | libre et question longue/analytique → `report` (Claude Sonnet, 16 000 tokens) ; sinon `chat` (Gemini Flash, 8 000). Bascule Claude ⇄ Gemini seulement avant le premier token | — |
| Archivage | message utilisateur + message assistant + citations + viz + tokens + coût modèle ; débit des 2 crédits si non dégradé | réponse vide non facturée |

### Ce que le modèle voit — et ne voit pas
**Aucun message précédent de la conversation n'est envoyé au modèle.** Chaque
tour est indépendant : profil + documents joints + sources + question
courante. Une conversation de 20 messages n'a pas plus de mémoire qu'un
message isolé. Le « fil » n'est donc qu'un regroupement visuel.

### API (préfixe `/intelligence`)
`GET /agents`, `POST /agents/route` (prévisualisation, ne persiste rien),
`POST|GET /projects`, `POST|GET /projects/{id}/conversations`,
`POST /conversations/{id}/messages` (bloquant), `POST …/messages/stream`
(SSE), `GET …/messages`, `GET …/export?format=md|pdf`.
Aucun `DELETE`, `PUT` ou `PATCH`. Aucune pagination.

### Données
`projects` → `conversations` (titre, agent par défaut, `message_count`
dénormalisé) → `messages` (rôle, agent, contenu, citations JSON, viz JSON,
tokens, coût modèle en micro-euros, modèle). Le coût de la recherche web
n'est mesuré nulle part pour un message : le tableau de bord admin le fixe à
0 pour le poste « conversations ».

### Observé en production (10/09, 14h01)
| Mesure | Valeur |
|---|---|
| Recherche web (3 fournisseurs en séquence) | 10 s |
| Génération (Claude, tier `report`, 4 300 caractères, 2 graphiques) | ~2 min 20 |
| Écriture en base des deux messages | 14:03:32 (fin de génération) |
| Affichage final côté navigateur | ~14:05:20 |
| Pastille crédits après la réponse | toujours « 40 » (base : 38) |
| Registre | 0 tutoiement, vouvoiement conforme |

Entre la fin de génération et l'affichage final, le texte affiché a **diminué**
(2 490 → 1 212 caractères) avant de remonter : le payload final remplace le
message et relance l'animation « machine à écrire » côté client depuis zéro,
dont chaque tick re-parse tout le markdown (tableaux, graphiques). Sur une
réponse longue, l'utilisateur voit la réponse arriver, disparaître, puis se
réécrire lentement. À confirmer sur une seconde mesure, mais le mécanisme
est dans le code (`AiMsg`, effet sur `live`).

---

## 2. Ce que l'utilisateur ne peut pas faire
- Renommer, supprimer, archiver, épingler une conversation.
- Chercher dans le contenu des messages (recherche sur le titre seulement).
- Régénérer une réponse, éditer un message envoyé, arrêter une génération.
- Voir ce que coûte un message ou une conversation (les tokens et le coût sont
  en base, jamais exposés).
- Poser une question qui s'appuie sur la réponse précédente (le modèle ne la
  connaît pas).
- Utiliser l'app confortablement sur mobile : la colonne des conversations
  reste à 280 px fixes, le fil garde ~95 px.

---

## 3. Irritants classés (du plus coûteux pour l'utilisateur au moins)

### A. Bloquants pour la valeur
1. **Pas de mémoire de fil.** « Développe le point 2 » ne fonctionne pas. C'est
   la promesse implicite d'une « conversation » et elle n'est pas tenue.
2. **Attente longue sans information.** 10 s de recherche + jusqu'à 2 min de
   génération derrière un bandeau unique « AXIAL analyse… ». Rien n'indique
   l'étape (recherche / lecture des sources / rédaction) ni une durée.
3. **Réponse qui se réécrit** après le flux (§1, observé). Perte de confiance
   immédiate : « ça bug ».
4. **Solde jamais rafraîchi** après un message, et **aucun garde-fou de
   crédits** avant l'envoi (contrairement aux rapports). L'utilisateur
   découvre le refus dans une bulle « ⚠️ … » générique.

### B. Frictions quotidiennes
5. Pas de suppression ni de renommage : la liste se remplit de titres
   tronqués à 48 caractères, sans tri autre que la date.
6. Clic sur une conversation → fil vide sans indicateur pendant le
   chargement.
7. L'auto-défilement ne suit pas le texte pendant le flux (indexé sur le
   nombre de messages).
8. On peut envoyer un second message pendant qu'une réponse s'écrit ; on peut
   changer d'agent au milieu d'un fil sans que rien ne le signale.
9. Markdown incomplet : listes numérotées, liens, code inline et blocs de code
   s'affichent en texte brut avec leurs symboles.
10. Erreurs indifférenciées (« ⚠️ Réponse interrompue. ») sans bouton
    Réessayer, y compris pour une session expirée.
11. Questions suggérées de repli en français pour un utilisateur en anglais.

### C. Dette invisible pour l'utilisateur mais coûteuse pour Axial
12. Routage multi-agents « intelligent » jamais exercé en mode libre (Axial
    Conseil répond toujours) ; endpoint `/agents/route` et tests couvrent un
    chemin mort.
13. Coût de recherche non mesuré par message → coût réel des conversations
    sous-estimé dans le tableau de bord, prix (2 crédits) déconnecté du coût.
14. Pas d'idempotence : double clic = deux messages et deux débits.
15. Flux interrompu après le premier token = facturé comme complet ; reprise
    sur troncature absente en streaming.
16. Aucun test de bout en bout de `stream_message` (persistance, facturation,
    déconnexion client).
17. Code mort : `axChat`, `axNewConversation`, `_convId`, clés i18n
    `common.share`/`share.title`, `Project.archived_at` jamais écrit, listes de
    titres génériques dupliquées (service vs export), parsing SSE dupliqué
    entre chat et rapports.
18. Cache Notion en mémoire de process, incohérent dès qu'il y a plusieurs
    workers.

---

## 4. Pistes — améliorer, simplifier, supprimer

### Améliorer (valeur directe)
| # | Piste | Effet | Effort |
|---|---|---|---|
| 1 | Envoyer les N derniers tours au modèle (fenêtre glissante + résumé compact au-delà) | la conversation devient une vraie conversation | moyen (backend + test) |
| 2 | Bandeau d'étapes pendant l'attente : « Recherche (3 sources) → Lecture → Rédaction » avec les événements SSE déjà existants (`sources`) + un événement `etape` | l'attente devient lisible | faible |
| 3 | Supprimer la double animation : à réception du payload final, ne pas réinitialiser le texte affiché (garder `shown` à la longueur courante) | plus de réponse qui « disparaît » | très faible |
| 4 | Rafraîchir le solde après chaque réponse (le payload final peut porter `balance`) + garde de solde avant envoi, réutilisant l'écran quota des rapports | cohérence avec les rapports | faible |
| 5 | Supprimer / renommer une conversation (endpoints `DELETE`, `PATCH` + menu contextuel dans la liste) | hygiène de la liste | faible |
| 6 | Bouton Stop (AbortController côté client, fermeture du générateur côté serveur) et verrou d'envoi pendant le flux | contrôle | faible |
| 7 | Compléter le rendu markdown (listes numérotées, liens, code) ou passer à un parseur éprouvé chargé depuis le CDN | fidélité des réponses | faible à moyen |
| 8 | Auto-défilement sur la longueur du contenu, skeleton au chargement d'un fil | confort | très faible |
| 9 | Erreurs typées (crédits, session, réseau) avec action (Voir les crédits / Se reconnecter / Réessayer) | moins de « ⚠️ » opaques | faible |

### Simplifier
| # | Piste | Justification |
|---|---|---|
| 10 | Un seul chemin de streaming partagé entre chat et rapports (`bridge.js`) | duplication actuelle |
| 11 | Une seule liste de titres génériques (service + export) | divergence silencieuse |
| 12 | Mesurer le coût de recherche par message comme pour les rapports (colonne + compteur) | tableau de bord juste, prix ajustable |
| 13 | Idempotence : clé côté client sur `POST …/messages` | double débit impossible |
| 14 | Colonne des conversations en tiroir sous 768 px (même mécanisme que la barre latérale) | mobile utilisable |

### Supprimer ou trancher
| # | Élément | Question à trancher |
|---|---|---|
| 15 | Sélecteur d'agent dans le composer (Market Scanner / Competitor Radar) | Les agents spécialisés existent aussi comme « Agents » de veille et comme types de rapports. En conversation, l'utilisateur doit-il choisir un cadre, ou Axial doit-il router seul ? Si router seul : activer réellement `personas.route` en mode libre et retirer le sélecteur. Si choisir : le figer par conversation, pas globalement. |
| 16 | `POST /agents/route`, `axChat`, `axNewConversation`, `_convId`, clés i18n de partage, `Project.archived_at` | code mort, à retirer |
| 17 | Endpoint bloquant `POST …/messages` | ne sert que de repli si le SSE n'ouvre pas ; à garder seulement si ce repli est réellement observé en production |
| 18 | Notion de « projet » | invisible pour l'utilisateur (un projet par défaut créé côté front). Soit l'exposer (dossiers de conversations), soit l'aplatir. |

---

## 5. Ordre proposé
1. Quick wins sans risque (#3, #4, #8, #9, #2) — une journée, effet immédiat
   sur la perception.
2. Mémoire de fil (#1) avec test de bout en bout de `stream_message` — c'est
   le cœur.
3. Hygiène : supprimer/renommer (#5), Stop (#6), markdown (#7), mobile (#14).
4. Décisions produit (#15, #18) puis nettoyage (#16, #17, #10-#13).
