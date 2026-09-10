# Conversations v2 — spécification (10/09/2026)

Sources : `2026-09-10-bilan-conversations.md` (+ backend, frontend) et les
retours de Miradie du 10/09. Ce document est l'autorité : le plan
`docs/superpowers/plans/2026-09-10-conversations-v2.md` en découle.

## 0. Réponses aux questions de Miradie

**« Explique la prévisualisation de l'API. »** `POST /intelligence/agents/route`
prend une question et renvoie l'agent que le routeur *choisirait* (et une note
de redirection éventuelle) **sans rien enregistrer** : c'était prévu pour que
le front affiche « cette question ira à Competitor Radar » avant l'envoi. Le
front ne l'appelle jamais. Décision : supprimé (§5).

**« GET vs POST. »** GET = lire, sans effet de bord, répétable (liste des
conversations, messages, export). POST = créer ou déclencher (créer une
conversation, envoyer un message). On ajoute PATCH = modifier une partie
(renommer, épingler, archiver) et DELETE = supprimer. La méthode dit au
navigateur, aux proxys et à nous ce qu'une requête a le droit de faire ; un
GET ne doit jamais rien changer.

**« Pourquoi `/intelligence/agents` est public ? »** Aucune raison valable :
il liste les trois agents (clé, nom, cadre). Il ne fuit rien de sensible mais
n'a pas d'usage anonyme. Décision : authentifié comme le reste.

**« Notion de projet. »** En base, une conversation appartient à un projet et
un projet à un utilisateur. Le front crée un projet unique « Workspace » par
utilisateur et n'en parle jamais : c'est un dossier invisible. Décision :
l'exposer comme **dossiers** dans le panneau des conversations (créer,
renommer, archiver un dossier ; déplacer une conversation d'un dossier à
l'autre). Le dossier par défaut s'appelle « Général ».

**« Quand rafraîchir le RAG ? »** Le RAG (Qdrant) a deux collections :
`documents` (ce que l'utilisateur importe, indexé **au moment de l'import**,
donc toujours à jour tant que l'import a réussi) et `knowledge_base` (corpus
Axial, statique, rechargé seulement par un script d'admin). Il n'y a rien à
rafraîchir périodiquement : le seul cas utile est un import qui a échoué à
l'indexation (`chunk_count = 0`). Décision : afficher ce cas à l'utilisateur
(« document importé mais non lisible ») et offrir « Réindexer » sur la page
Documents. Pas de tâche planifiée.

**« Axial doit router seul, mais qu'est-ce que cela signifie ? »** En mode
« Conversation » (défaut), Axial lit la question et choisit lui-même :
question macro-marché → Market Scanner (cadre PESTEL), question concurrence
→ Competitor Radar (Porter), sinon Axial Conseil. Les agents spécialisés
n'interviennent que si la question s'y prête nettement, ou si l'utilisateur
les choisit explicitement. Les mêmes cadres existent ailleurs (types de
rapports, agents de veille) : ce sont des *cadres d'analyse* réutilisés, pas
des modules distincts. Décision : le sélecteur reste (choix explicite), la
valeur par défaut est `auto` (constante `AUTO`), et en `auto` le routeur réel
`personas.route` est enfin appelé ; chaque réponse porte le badge de l'agent
qui a répondu.

## 1. Mémoire de fil (ce que le modèle voit)

- Le modèle reçoit, en plus du contexte actuel : les **8 derniers messages**
  de la conversation (4 tours, tronqués à 1 500 caractères chacun) sous forme
  de tableau `messages` alternant user/assistant, puis la question courante.
- Au-delà de 8 messages, un **résumé roulant** (`conversations.resume`,
  ≤ 600 mots, généré en tier `chat` après chaque tour dont l'index dépasse 8,
  hors flux, jamais bloquant) est injecté en tête du prompt :
  « Résumé de la conversation jusqu'ici : … ».
- `llm_client.generate/stream_text` acceptent `history: list[{role, content}]`
  et le passent tel quel à Claude (`messages`) et Gemini (`contents`).
- Les citations des tours passés ne sont pas renvoyées (pas de doublon de
  sources) ; les blocs ```viz des réponses passées sont retirés du texte
  envoyé.

## 2. Retours explicites à l'utilisateur

| Cas | Comportement |
|---|---|
| Crédits insuffisants | Front : garde avant envoi (`axBal < 2`) → **modale** « Plus de crédits » avec « Acheter des crédits » / « Voir les abonnements » (route Crédits) / « Fermer ». Backend : 402 inchangé, affiché par la même modale si le front était en retard. |
| Solde | Le payload final du flux porte `balance` ; la pastille se met à jour immédiatement. |
| Contexte entreprise manquant | Bandeau discret au-dessus du composer : « Votre profil entreprise est vide : les réponses ne seront pas personnalisées. Compléter ». Backend : événement SSE `avertissement: contexte_absent`. |
| Documents joints | 3 maximum par message : le bouton d'import est désactivé au 3ᵉ avec l'infobulle « 3 documents maximum par message ». Échec d'import (taille, format, indexation `chunk_count = 0`) : message rouge sous le composer avec la raison exacte renvoyée par l'API. |
| Session expirée | Si le rafraîchissement échoue pendant un envoi : déconnexion propre + écran de connexion avec « Votre session a expiré, reconnectez-vous ». |
| Message trop long | `maxLength` 6 000 caractères + compteur à partir de 5 000. Backend : 413 au-delà. |

## 3. Attente et affichage

- Événements SSE d'étape : `etape: recherche` (avec `fournisseurs`),
  `etape: sources` (avec le nombre), `etape: redaction`. Le bandeau affiche
  « Recherche web… » → « 17 sources lues » → « Rédaction… », avec un compteur
  de secondes.
- Fin de flux : le texte affiché n'est **jamais réinitialisé** ; le payload
  final ne fait que compléter (viz, citations). L'animation machine à
  écrire locale est supprimée (`streamingSpeed` disparaît).
- Auto-défilement indexé sur la longueur du contenu, seulement si
  l'utilisateur est déjà en bas (sinon bouton « ↓ Nouveaux messages »).
- Skeleton de trois lignes pendant le chargement d'un fil.

## 4. Ce que l'utilisateur peut faire

| Action | Backend | Front |
|---|---|---|
| Renommer | `PATCH /conversations/{id} {title}` | menu ⋯ sur l'item → champ inline |
| Supprimer | `DELETE /conversations/{id}` (cascade messages) | menu ⋯ → confirmation |
| Archiver / désarchiver | `PATCH {archived: bool}` (colonne `archived_at`) | menu ⋯ ; filtre « Archivées » en bas de liste |
| Épingler | `PATCH {pinned: bool}` (colonne `pinned_at`) | menu ⋯ ; section « Épinglées » en tête |
| Dossiers (projets) | `PATCH /projects/{id}`, `DELETE`, `PATCH /conversations/{id} {project_id}` | groupe par dossier dans la liste, « Nouveau dossier », déplacer via menu ⋯ |
| Chercher dans le contenu | `GET /conversations/search?q=` (ILIKE sur titre + contenu, 20 résultats avec extrait) | même champ de recherche, résultats avec extrait, à partir de 3 caractères |
| Régénérer | `POST /conversations/{id}/messages/{msg_id}/regenerer` : supprime la réponse, relance le flux avec le même message utilisateur | bouton sous la réponse |
| Éditer un message envoyé | `POST /conversations/{id}/messages/{msg_id}/editer {content}` : supprime ce message et tout ce qui suit, relance | crayon sur la bulle utilisateur |
| Stopper | Front : `AbortController` ; serveur : le générateur détecte la déconnexion (`request.is_disconnected()`), archive le texte partiel avec `statut='partiel'` sans facturer | bouton « Stop » remplaçant Envoyer pendant le flux |
| Coût | `MessageOut` expose `tokens_entree`, `tokens_sortie`, `credits` ; `GET /conversations/{id}/cout` → total crédits, tokens, coût € (admin seulement pour le €) | pastille « 2 crédits · 3,1 k tokens » sous chaque réponse ; total dans l'en-tête du fil ; le € n'est montré qu'aux admins |
| Question de suite | §1 | — |
| Mobile | — | §6 |

Verrous : pendant un flux, Envoyer devient Stop et le composer est verrouillé
pour ce fil ; changer d'agent dans un fil existant insère une note système
« Agent changé : Competitor Radar » avant le message suivant.

## 5. Dette backend

1. Routage : `_prepare_turn` appelle `personas.route(content, requested)` dans
   tous les cas ; `DEFAULT_AGENT = AUTO` ; `conversations.default_agent`
   par défaut `auto`. `/agents/route` supprimé. `/agents` authentifié.
2. Coût de recherche : colonnes `cout_recherche_micro_eur`, `appels_recherche`
   sur `messages` (migration `0022_conversations_v2`), compteur passé à
   `web_search.search`, `metrics` lit la colonne au lieu de `0`.
3. Idempotence : en-tête `X-Idempotency-Key` (uuid côté client par envoi),
   colonne `messages.cle_idempotence` unique ; un rejeu renvoie le message
   existant sans débit.
4. Statut de message : colonne `statut` ∈ `complet | partiel | degrade`
   (défaut `complet`). `partiel` (stop ou coupure après le premier token)
   n'est pas facturé ; `degrade` idem.
5. Reprise sur troncature en streaming : `claude.stream` renvoie le
   `stop_reason` final ; si `max_tokens`, le service relance jusqu'à 2 fois
   avec « Continue exactement où tu t'es arrêté » en gardant le flux ouvert.
6. Cache Notion : TTL 10 min et 200 entrées maximum (un seul worker uvicorn en
   prod, documenté dans le code).
7. Titres génériques : une seule constante `TITRES_GENERIQUES` importée par
   `export.py`.
8. Pagination : `GET …/messages?limit=50&before=<id>` ; le front charge les 50
   derniers et propose « Charger les messages précédents ». Listes de
   conversations : `limit` 100 par défaut.
9. `message_count` recalculé à la suppression/édition (`COUNT(*)`).
10. Notification d'erreur : dans `errors.py`, le gestionnaire `Exception`
    envoie un email à `miradie.buranturu@axial-ia.fr` via
    `emailing.envoi.envoyer` (sujet « [Axial] Erreur backend : {méthode}
    {route} », corps : compte, route, horodatage, traceback, action
    suggérée), dédupliqué par signature (route + type d'exception) sur 1 h,
    désactivable par `ERREURS_NOTIF_ACTIVES=false`. Idem pour les échecs
    absorbés critiques (génération échouée, flux coupé) via un utilitaire
    `notifier_erreur(...)`.
11. Code mort supprimé : `axChat`, `axNewConversation`, `_convId`,
    `ensureConversation` non forcé, `common.share`, `share.title`,
    `/agents/route`, `SUGGESTED_PROMPTS` FR en dur (remplacé par FR/EN via
    `t()`), parsing SSE factorisé (`lireFluxSSE`) partagé chat/rapports.

## 6. Mobile (priorité)

- Sous 768 px : le panneau des conversations devient un tiroir (même
  mécanisme que la barre latérale : bouton « Conversations » dans la topbar,
  voile, fermeture au choix d'un fil) ; le fil prend toute la largeur.
- Composer collé en bas, bulles à 100 %, tableaux et graphiques dans un
  conteneur `overflow-x: auto`, panneau de citation en plein écran.
- Passe générale : aucune surface ne doit dépasser horizontalement à 375 px
  (rapports, crédits, paramètres, agents, mémoire, documentation) ; grilles
  en une colonne, tableaux scrollables, topbar sans débordement.

## 7. Markdown

Rendu complet : titres, listes à puces **et numérotées** (imbriquées un
niveau), liens `[texte](url)` (ouverture dans un nouvel onglet, `rel`
noopener), code inline, blocs de code avec bouton Copier, tableaux, gras,
italique, citations `> `, séparateurs, citations `[N]`, blocs ```viz. Pas de
dépendance externe : le parseur maison est complété et testé (fichier
`frontend/app/_prototype/markdown.js` + tests Node `frontend/tests/markdown.test.mjs`
lancés par `npm test`).

## 8. Erreurs nommées

Une seule fonction `decrireErreur(e)` → `{ titre, detail, action }` :
`insufficient_credits` → modale crédits ; `refresh_invalid` / 401 →
reconnexion ; réseau / `Réponse interrompue.` → « Connexion perdue pendant la
réponse » + Réessayer (renvoie le même message) ; 413 → « Message trop long » ;
`degraded` → bandeau « Réponse partielle » sur la bulle. Plus jamais de
`⚠️ e.message` brut.

## 9. Tests (backend, `tests/test_conversations_v2.py` + existants)

Bout en bout sur SQLite en mémoire avec `llm_client` simulé : persistance
(`Message`, `message_count`, `last_message_at`), facturation 2 crédits et
402, routage `auto` réel (macro → market_scanner, concurrence →
competitor_radar, générique → conseiller), historique envoyé (8 derniers,
résumé au-delà), citations et viz persistés, statut partiel non facturé,
survie du flux à la déconnexion, idempotence, 401 en cours de conversation,
renommer/supprimer/archiver/épingler/déplacer, recherche, régénérer, éditer,
pagination, export (titre de secours), `_attached_docs_context` (3 × 8 000),
`grounding.assemble`, coût modèle + recherche, notification d'erreur
(dédupliquée, désactivable), `/agents` authentifié, `/agents/route` absent.

## 10. Hors périmètre
Tarification par message (reste 2 crédits ; le coût réel devient mesurable,
la décision de prix viendra après un mois de données). Partage de
conversation. Recherche sémantique dans l'historique.
