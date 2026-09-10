# Bilan factuel — surface « Conversations » (frontend)

Fichiers concernés : `frontend/app/_prototype/App.jsx` (5966 lignes), `frontend/app/_prototype/bridge.js` (485 lignes), `frontend/app/globals.css` (2900 lignes).
Note technique : trois lignes d'`App.jsx` (792, 2305, 2480) font ~60 000 caractères chacune — ce sont des images PNG encodées en base64 inline (logo / marque IA), pas du code.

---

## 1. Écrans et composants

### Route et assemblage
- `subRoute === 'conversations'` monte `<ConversationsRegion>` — App.jsx:5898-5910.
- `ConversationsRegion` (App.jsx:2204-2239) compose trois zones : `ConvListPanel` (liste, toujours affichée), soit `ConvThread` soit `EmptyConvState` (selon `activeId`), et optionnellement `CitationPanel` en overlay.
- Layout CSS : `.app-body { grid-template-columns: 280px 1fr; }` (globals.css:1066-1069) — colonne liste fixe 280px + reste pour le fil. Une classe `.app-body-single` (globals.css:1420-1426) passe en 1 colonne pour **toutes les autres** surfaces (reports, agents, etc.), mais pas pour `conversations` qui garde le grid 2 colonnes.

### `ConvListPanel` (App.jsx:2242-2280)
- Recherche texte (`conv.search`, placeholder « Rechercher une analyse… ») : filtre **uniquement sur `c.title`**, côté client, en local (`conversations.filter(c => c.title.toLowerCase().includes(q.toLowerCase()))`, App.jsx:2245-2246). Aucune recherche dans le contenu des messages.
- Bouton « Nouvelle analyse » — libellé i18n `nav.new_analysis` — appelle `onNew` = `() => setActiveId(null)` (App.jsx:5906), ce qui bascule simplement sur `EmptyConvState` ; **aucune conversation n'est créée côté backend à ce moment** (elle ne l'est qu'au premier envoi, via `handleSendNew`).
- Libellé de section « RÉCENTES » = clé i18n `nav.recent` (App.jsx:2258).
- Chaque item est un `<button className="conv-item">` affichant `c.title` et `(c.lastUpdated || '').toUpperCase()` (App.jsx:2264-2270). `lastUpdated` est calculé **une seule fois** au chargement par `depuisLabel()` (App.jsx:2045-2059, ex. « il y a 3 h ») et n'est **pas recalculé en continu** (pas de timer) : le libellé se fige jusqu'au prochain re-fetch ou message.
- État vide : message `conv.none` (« Aucun résultat. ») si le filtre ne matche rien.

### Zone du fil — état vide (`EmptyConvState`, App.jsx:2291-2321)
- Logo (image base64), titre `conv.hook`, sous-titre `conv.sub`.
- **Questions suggérées** (`suggestedPrompts`, prop venant de l'état `suggested` — App.jsx:5585) : cliquables, remplissent l'appel `onSend(p)` = `handleSendNew`.
  - Origine : par défaut, `SUGGESTED_PROMPTS` codées en dur **en français** (App.jsx:13-18 : « Mes 3 concurrents directs… », etc.), utilisées tant que le profil n'est pas chargé — y compris pour un utilisateur en anglais (pas de variante EN pour ce fallback).
  - Dès que la route `app` est atteinte, un effet (App.jsx:5588-5607) appelle `axGetProfile()` et, si `company_name` ou `sector` est renseigné, **génère 4 questions à partir du profil réel** (nom d'entreprise, secteur, stade de financement, `main_challenge`), en FR ou EN selon `window.AXIAL_LANG`. Donc oui : les suggestions sont générées depuis le profil quand il existe, sinon repli sur les 4 questions génériques françaises.
- Un `Composer` local avec un `draft` pré-rempli depuis `localStorage.axial_seed_q` si présent (question posée depuis l'onboarding) — App.jsx:2298-2305 — jamais envoyée automatiquement.

### Bulles de message
- `UserMsg` (App.jsx:2427-2432) : bulle simple à droite, pas de markdown, texte brut.
- `AiMsg` (App.jsx:2438-2492) :
  - État `__PENDING__` (contenu littéral) → bloc « AXIAL analyse — recherche web + base de connaissance… » avec animation de points (`.ax-thinking`, App.jsx:2440-2450).
  - Sinon, texte rendu par `MarkdownView` (headings `#`/`##`/`###`, listes à puces `-`/`*`, tableaux `| … |` avec séparateur, gras `**...**`, citations `[N]` cliquables, blocs ```` ```viz ```` pour les visualisations). **Pas de support** pour les blocs de code générique (```` ``` ```` hors `viz`), le code inline `` `x` ``, les liens markdown `[texte](url)`, ni les listes numérotées `1.` (rendu en paragraphe brut, App.jsx:3222-3311).
  - Badge agent (`AGENT_LABELS`, App.jsx:2417 : « Market Scanner · PESTEL », « Competitor Radar · Porter ») affiché seulement si `agent` correspond à un agent spécialisé — la conversation libre (`auto`) n'a pas de badge.
  - Animation de « streaming » simulée côté client (`shown`/`fullText.slice`) désactivée si `live` est vrai (flux réel déjà progressif) — App.jsx:2457-2472.
  - Curseur clignotant (`.typing-cursor`) tant que `stillStreaming`.
  - Une fois le flux terminé, un bloc d'actions avec un seul bouton : **Copier** (`BoutonCopier`, App.jsx:2325-2346, clipboard API + repli `execCommand('copy')`). Aucune autre action (pas de regénérer, pas d'éditer, pas de partager par message).
  - Il n'existe **aucun** bloc « AXIAL Recommande » dans le code (recherche exhaustive de la chaîne « Recommande » : seule occurrence hors sujet, App.jsx:5196, dans une autre surface). Cette fonctionnalité n'existe pas dans le produit actuel.
- Panneau de citation (`CitationPanel`, App.jsx:2901-2934, classe `.cite-panel`) : overlay latéral fixe (420px, `max-width: 92vw`) avec titre, source, extrait, lien externe. `role="dialog"` mais **sans `aria-modal`, sans piège de focus, sans fermeture au clavier (`Escape`)** — seule fermeture possible via le bouton × ou un clic sur le fond (`cite-panel-backdrop`).
- Erreur affichée dans le fil : préfixe littéral `'⚠️ ' + (e.message || 'Erreur')` inséré comme contenu de message assistant (App.jsx:5743, 5764) — rendu par le même `MarkdownView`, donc affiché comme texte brut.

### En-tête du fil (`ConvThread`, App.jsx:2361-2426)
- Barre discrète : titre de la conversation + deux boutons d'export **Markdown** et **PDF** (`axExporterConversation`, bridge.js:361-377), désactivés pendant l'export (`exportEnCours`).
- Scroll : `scrollRef.current.scrollTop = scrollRef.current.scrollHeight` dans un `useEffect` dont les dépendances sont `[conversation.messages.length, conversation.id]` (App.jsx:2366-2371).

### Composer (App.jsx:2511-2622)
- Placeholder i18n `conv.placeholder` (« Posez votre question stratégique… (Maj+Entrée pour aller à la ligne) »).
- Raccourci clavier : `Enter` seul envoie (`onKey`, App.jsx:2554-2556), `Shift+Enter` insère un retour à la ligne (comportement par défaut du `textarea`, pas de traitement spécial nécessaire).
- Bouton import de document (icône `+`) : `<input type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md">`, upload via `axUploadDocument` (bridge.js:387-406). Les documents importés sont mis en file (`window.AXIAL_PENDING_DOCS`, un event global `axial-pending-docs`) et **joints au prochain message envoyé uniquement** (retirables individuellement avant envoi). Pas de limite de taille ni de nombre affichée côté front.
- Sélecteur d'agent (`AGENT_MODES`, App.jsx:2505-2509) : trois boutons pill « Conversation » (`auto`), « Market Scanner », « Competitor Radar ». Le choix est persisté dans `localStorage.axial_agent_mode` (App.jsx:2517-2521) et lu à l'envoi par `axStreamChatIn`/`axChatIn` (bridge.js:226-227, 241-242) — **global à l'app**, pas attaché à une conversation précise.
- Bouton d'envoi (`composer-send`, icône flèche) désactivé seulement si `!value.trim()` — **pas désactivé pendant qu'une réponse est en cours de génération** (voir §3/§6).
- Aucune limite de caractères visible ni contrôlée côté front (pas de `maxLength`, pas de compteur).

### Topbar / breadcrumb / pastille crédits
- Fil d'Ariane dynamique (App.jsx:5859-5867) : `subRoute === 'conversations'` affiche `t('nav.conversations')` / titre de la conversation active ou `t('nav.new_analysis')` si aucune n'est sélectionnée.
- Pastille crédits (`.chip`, App.jsx:5874-5876) : `{axBal == null ? '…' : axBal} {t('topbar.credits')}`, cliquable → bascule `subRoute` sur `credits`. Alimentée par `axBal`, un état chargé **une seule fois** au montage de la route `app` (voir §2).

---

## 2. État et flux de données

### État React (App.jsx:5508-5518)
- `conversations` : tableau d'objets `{ id, title, lastUpdated, loaded, messages }`. Initialisé vide (`useState(() => [])`) — pas de seed mock.
- `activeId` : id de la conversation ouverte, ou `null`.
- `showCitePanelFor` : `{ convId, sourceId } | null`.
- Chaque conversation porte un flag `loaded` (booléen) qui distingue « connue via la liste » de « messages effectivement chargés ».

### Chargement
- Au montage de la route `app` (App.jsx:5610-5633, effet dépendant de `[route]`) :
  1. `axGetProfile()` → génère les 4 suggestions personnalisées si profil rempli.
  2. `axListConversations()` (bridge.js:305-313) → liste **tous les projets** de l'utilisateur, fusionne leurs conversations, triées par `last_message_at` décroissant ; fusionnées dans l'état local en ne gardant que les nouvelles (`known` = Set des ids déjà présents) — préserve les conversations déjà ouvertes localement (avec leurs messages chargés) sans les écraser.
  3. `axBalance()` → `setAxBal(b.available)` (une seule fois).
  4. `axMe()` → nom, initiales, `is_admin`.
- **Chargement paresseux des messages** : `openConversation(id)` (App.jsx:5697-5707) est la fonction passée comme `setActiveId` à `ConversationsRegion` (App.jsx:5898). Elle règle `activeId` immédiatement puis, si `conv.loaded` est faux, appelle `axMessages(id)` (bridge.js:315-317) et remplit `messages` + passe `loaded: true`. **Aucun indicateur de chargement** n'est affiché pendant ce fetch : le fil bascule instantanément sur la conversation (vide) puis se peuple quand la réponse arrive — flash de fil vide visible à chaque premier clic sur une conversation.

### Envoi de message
- Nouvelle conversation : `handleSendNew` (App.jsx:5743-5761) — crée un id optimiste au format `title` tronqué à 48 caractères (`slice(0,45) + '…'`), tente `axCreateConversation()` (bridge.js:298-300, crée un vrai id backend) ; **en cas d'échec, replie sur un id client `'c-' + Date.now()`** (App.jsx:5748) — cette conversation « fantôme » n'existe pas côté serveur : elle disparaîtra au prochain `axListConversations()` / rechargement de page, et les messages envoyés dans ce fil ne seront jamais persistés si la création backend échoue mais que `sendStreamed` réussit malgré tout via un id invalide.
- Conversation existante : `handleSendInActive` (App.jsx:5718-5735) — ajoute optimistiquement `{role:'user'}` + `{role:'assistant', content:'__PENDING__'}` à la conversation active, puis appelle `sendStreamed`.
- `sendStreamed(cid, text, baseMessages)` (App.jsx:5698-5716) pilote le flux :
  - `onEvent({step:'sources', agent, citations})` → remplace le dernier message par `{content:'__PENDING__', agent, sources: mapCitations(citations), live:true}` — **les citations arrivent donc avant le texte**, en tant qu'événement de flux dédié, pas dans le payload final uniquement.
  - `onEvent({step:'delta', delta})` → accumule `acc += delta` et met à jour `content: acc` sur le dernier message, `live:true`.
  - À la fin, `axStreamChatIn` retourne l'objet final persistant (`final.content`, `final.agent`, `final.citations`, `final.viz`) qui remplace le dernier message avec `live:false`.
  - **Cas limite non géré** : si le backend envoie un `delta` avant un `sources`, le premier `delta` écrase `content:'__PENDING__'` par `acc` (potentiellement une chaîne vide au tout premier chunk) — l'indicateur « AXIAL analyse… » peut disparaître avant que du texte visible n'arrive, laissant un instant un message assistant vide.

### Flux SSE (`axStreamChatIn`, bridge.js:240-295)
- `fetch(POST /intelligence/conversations/{cid}/messages/stream)`, lecture via `res.body.getReader()`, découpage sur `\n\n` (frames SSE), extraction de la ligne `data:`, `JSON.parse`.
- Sur `evt.done` : si `evt.error`, lève une erreur (`code` inclus) ; sinon `final = evt.data`.
- Repli automatique : si la requête initiale échoue à s'ouvrir (`!res.ok || !res.body`), l'erreur `"stream_unavailable"` est interceptée et la fonction retente en mode **non-streamé** via `axChatIn` (bridge.js:291-293) — repli silencieux, invisible pour l'utilisateur (pas de bascule visuelle vers un mode « bloquant »).
- **Aucun `AbortController`** n'est utilisé nulle part dans `bridge.js` ni `App.jsx` : changer de conversation, naviguer vers un autre `subRoute`, ou fermer l'app **n'annule pas** une requête de streaming en cours. Le `reader.read()` continue en arrière-plan et, à la fin, `setConversations` sera appelé même si la conversation n'est plus affichée (mise à jour silencieuse d'un état qui peut ne plus être visible, ou race condition si l'utilisateur a rouvert entre-temps).

### Rafraîchissement du jeton (401) — bridge.js:23-82
- `axFetch` : sur 401 **ou 403** (FastAPI répond 403 sans en-tête `Authorization`), tente un `POST /auth/refresh` avec le refresh token stocké, une seule tentative concurrente partagée (`_refreshing`), puis rejoue la requête originale une fois (`_retried`).
- Le token n'est effacé (`axClearToken`) que sur un refus **avéré** du refresh (401/400) — pas sur une erreur réseau ou un 5xx passager (commentaire explicite App.jsx:5578-5584 relatant un incident réel du 03/09 où un utilisateur a été déconnecté à tort).
- `axStreamChatIn` et `axStreamAnalysis` dupliquent cette même logique de retry-après-refresh en local (bridge.js:256-259, 424-427), au lieu de réutiliser `tryRefresh`/`axFetch` — deux implémentations quasi identiques du parsing SSE + retry token (voir §6).

### Pastille crédits
- `axBal` est réglé **une seule fois**, au montage de la route `app` (§2). Aucun appel à `axBalance()` n'existe dans `handleSendNew`, `handleSendInActive` ou `sendStreamed` (confirmé par recherche exhaustive de `setAxBal`/`axBalance` dans App.jsx — seules occurrences : ligne 5517, 5626, et deux usages non liés aux conversations lignes 1945/4223). **La pastille de crédits n'est donc jamais mise à jour après l'envoi d'un message** ; elle ne se rafraîchit qu'en revisitant la route `app` (rechargement de page) ou en ouvrant l'écran Crédits.

### Citations / visualisations
- Citations : arrivent soit via l'événement de flux `step:'sources'` (avant le texte), soit dans le payload final (`final.citations`), mappées par `mapCitations` (App.jsx:5674-5683) vers `{id, title, source, excerpt, link}`.
- Visualisations (`viz`) : arrivent uniquement dans le payload **final** (`final.viz`), jamais en flux — pendant le streaming, un bloc ```` ```viz ```` détecté dans le texte accumulé affiche `<div className="viz-attente">Graphique en préparation…</div>` (App.jsx:3260-3261, `VizFigure`) tant que le bloc n'est pas fermé ou que `live` est vrai ; une fois clos et non-live, `axRenduViz(spec)` (bridge.js:357) est appelé côté client pour obtenir le SVG rendu serveur, avec repli tableau si échec de parsing JSON du bloc.

---

## 3. Ce que l'utilisateur NE PEUT PAS faire

- **Renommer une conversation** : aucun endpoint `PATCH`/`PUT` sur `/intelligence/conversations/{id}` dans `bridge.js` (seuls verbes présents : `GET` liste/messages, `POST` création/messages/stream, `GET` export). Aucun handler ni bouton dans `ConvListPanel`/`ConvThread`.
- **Supprimer une conversation** : aucun `DELETE` sur les conversations dans `bridge.js` (à comparer avec `axDeleteDocument`, `axDeleteFeed`, `axDeleteWatch` qui existent pour d'autres ressources). Aucun bouton de suppression dans l'UI.
- **Archiver une conversation** : aucun champ ni endpoint dédié ; le mot « archivage » n'apparaît qu'une fois dans tout le fichier, en dehors du contexte conversations (App.jsx:5170, texte descriptif d'agents de veille).
- **Épingler une conversation** : aucune trace de « pin »/« épingle » dans le code ni le CSS.
- **Rechercher dans le contenu des messages** : la recherche de `ConvListPanel` ne filtre que sur `c.title` (App.jsx:2245-2246) — confirmé plus haut.
- **Copier/exporter une conversation entière** : en fait **possible** — deux boutons « Markdown » et « PDF » existent dans l'en-tête du fil (`ConvThread`, App.jsx:2379-2386) via `axExporterConversation` (bridge.js:361-377). Seule la copie **par message individuel** existe (`BoutonCopier`), pas de bouton « copier toute la conversation ».
- **Régénérer une réponse** : `AiMsg` n'a qu'un bouton Copier dans `.msg-ai-actions` (App.jsx:2483-2487) ; aucun bouton « régénérer », aucun handler correspondant, aucun endpoint dédié dans `bridge.js`.
- **Éditer un message envoyé** : `UserMsg` (App.jsx:2427-2432) rend un simple `<div>{text}</div>`, non éditable, sans `onClick`/handler.
- **Arrêter une génération en cours** : pas de bouton « stop », pas d'`AbortController` (voir §2) — une fois lancée, une génération va jusqu'à son terme ou son échec réseau.
- **Changer d'agent en cours de fil** : en réalité **possible** — `ConvThread` monte le même composant `Composer` que `EmptyConvState` (App.jsx:2419-2421), avec le même sélecteur `AGENT_MODES` visible et actif dans une conversation déjà ouverte. Le mode choisi est lu à chaque envoi depuis `localStorage.axial_agent_mode` (bridge.js:226-227/241-242), donc rien n'empêche de changer d'agent au milieu d'un fil existant — le badge affiché sur chaque message (`AGENT_LABELS`) reflète l'agent utilisé **pour ce message précis**, pas un agent figé pour toute la conversation.
- **Partager une conversation** : les clés i18n `common.share` (App.jsx:137/352) et `share.title` (App.jsx:290/497) existent dans les dictionnaires de traduction mais ne sont **utilisées nulle part** (`t('common.share')`/`t('share.title')` absents du reste du fichier) — traductions mortes, aucune fonctionnalité de partage de conversation.

---

## 4. Faits visuels / UX

- **Largeurs** : `.conv-list-panel` n'a pas de largeur propre en CSS ; elle hérite de la première colonne du grid `.app-body { grid-template-columns: 280px 1fr }` (globals.css:1066-1069), donc 280px fixes. `.thread-region` prend le `1fr` restant, hauteur `calc(100vh - 56px)` (globals.css:1162-1167).
- **Mobile (< 768px)** : le seul point de rupture pertinent pour la sidebar globale est `@media (max-width: 767px)` (globals.css:1074-1093), qui fait passer `.sidebar` en panneau overlay coulissant. **Aucune media query ne modifie `.app-body` ou `.conv-list-panel` en dessous de 768px** — le grid `280px 1fr` reste appliqué tel quel sur un écran de ~375px de large, ce qui laisse ~95px pour le fil de conversation (hors marges) : mise en page très resserrée voire cassée sur mobile pour cet écran précis (à la différence de `.app-body-single`, qui s'applique à tous les autres `subRoute` mais pas à `conversations`, cf. §1).
- **Défilement automatique** : déclenché uniquement par un `useEffect` dépendant de `[conversation.messages.length, conversation.id]` (App.jsx:2366-2371). Pendant le streaming, `sendStreamed` met à jour le contenu du **dernier message existant** (`acc`) sans changer la longueur du tableau `messages` — donc **l'auto-scroll ne se redéclenche pas à chaque fragment de texte reçu**, seulement au moment où le nombre de messages change (ajout du placeholder `__PENDING__`, puis rien jusqu'au message suivant). Sur une réponse longue, la vue peut rester figée alors que du texte continue d'apparaître sous la ligne de flottaison.
- **Rendu markdown / cas limites** : voir §1 — pas de blocs de code génériques, pas de code inline, pas de liens `[texte](url)`, pas de listes numérotées ; seuls `#`/`##`/`###`, `-`/`*`, tableaux `|...|`, gras `**`, citations `[N]` et blocs ```` ```viz ```` sont reconnus. Tout le reste (par ex. un bloc ```` ```python ```` collé par le modèle) se rend comme texte brut avec les triples backticks visibles.
- **i18n / textes français en dur** : les 4 questions suggérées par défaut (`SUGGESTED_PROMPTS`, App.jsx:13-18) sont câblées en français et servent de repli même pour un utilisateur en anglais tant que le profil n'a pas été chargé/rempli. Les libellés « RÉCENTES », placeholders, hooks passent tous par `t()` avec variantes FR/EN correctement définies (App.jsx:145-161, 359-375).
- **Skeletons / indicateurs de chargement** : les seuls `.skeleton` du code servent à l'écran de génération de rapport (App.jsx:3145-3148, `.rep-gen-doc .skeleton`, globals.css:1719-1728). **Aucun skeleton ni spinner** pour le chargement de la liste des conversations ni pour le chargement paresseux des messages d'une conversation cliquée (flash de fil vide, §2).
- **Accessibilité** : peu d'attributs ARIA sur la surface conversations — seulement `aria-label` sur le bouton d'import de document, le bouton d'envoi, le bouton « Retirer » un document en attente, et le bouton de fermeture du panneau de citation (App.jsx:2567, 2581, 2591, 2918). Le panneau de citation a `role="dialog"` (App.jsx:2915) mais **pas de `aria-modal`, pas de piège de focus, pas de fermeture au clavier (`Escape`)**. Le champ de recherche de la liste n'a pas de `<label>`/`aria-label` (repose sur le seul `placeholder`). Aucune région `aria-live` pour annoncer l'arrivée du texte en streaming aux lecteurs d'écran.

---

## 5. Erreurs rencontrables et affichage

- **Panne réseau en cours de flux** : `axStreamChatIn` lève une exception (`reader.read()` échoue, ou `!final` après la boucle → `new Error("Réponse interrompue.")`, bridge.js:282). Remontée jusqu'à `handleSendInActive`/`handleSendNew`, qui remplace le dernier message par `{content: '⚠️ ' + e.message}` (App.jsx:5743, 5764) — affiché comme texte brut dans la bulle assistant, sans bouton « réessayer ».
- **Session expirée (401)** : géré de façon transparente par `axFetch`/`axStreamChatIn` via le refresh token (§2) — invisible pour l'utilisateur si le refresh réussit. Si le refresh échoue franchement (401/400 du endpoint refresh), `axClearToken()` est appelé côté `bridge.js`, mais **rien ne déconnecte automatiquement l'utilisateur depuis l'intérieur de `sendStreamed`/`handleSend*`** : la requête suivante échouera avec un message d'erreur générique affiché en `⚠️ ...` dans le fil, sans redirection vers l'écran de connexion (la seule redirection explicite sur 401/403 se trouve dans l'effet de reprise de session au montage de l'app, App.jsx:5577-5584, pas dans le flux d'envoi de message).
- **Crédits insuffisants** : **aucun garde-fou côté client** dans `handleSendInActive`/`handleSendNew`/`sendStreamed` — à comparer explicitement avec `startReport` (App.jsx:5638-5647) qui vérifie `axBal < cost` et bascule sur un écran `ReportsQuota` dédié *avant* d'appeler l'API. Pour les conversations, si le solde est insuffisant, la seule chose que verra l'utilisateur est ce que le backend renvoie comme erreur HTTP, affichée telle quelle (générique) en `⚠️ message` dans la bulle assistant — pas d'écran dédié, pas de blocage préventif de l'envoi.
- **Message surdimensionné** : aucune limite ni validation côté front (pas de `maxLength`, pas de contrôle de taille avant envoi) ; le comportement dépend entièrement d'une éventuelle limite backend, dont l'erreur (si elle existe) remonterait aussi comme `⚠️ message` générique.
- **Réponse dégradée du LLM** : rien dans le front ne distingue une réponse « dégradée » d'une réponse normale — le texte reçu est rendu tel quel par `MarkdownView`, sans marquage de qualité/complétude.
- **Repli silencieux du streaming** : si `POST .../messages/stream` échoue à s'ouvrir, bascule automatique et invisible vers `axChatIn` (mode bloquant, une seule réponse d'un coup) — l'utilisateur ne voit aucune différence de mode, juste une réponse qui apparaît sans effet de frappe progressive.

---

## 6. Code mort ou dupliqué dans la surface conversations

- **Imports jamais appelés** dans `App.jsx` : `axChat`, `axChatIn`, `axNewConversation` sont importés (App.jsx:7) mais **aucun appel direct** n'existe dans tout `App.jsx` (confirmé par recherche exhaustive). `axChatIn` n'est utilisé qu'en interne à `bridge.js`, comme repli dans `axStreamChatIn` (bridge.js:292) et par `axChat` lui-même (bridge.js:220) — `axChat` et `axNewConversation`, eux, ne sont appelés nulle part, ni dans `App.jsx` ni ailleurs dans `bridge.js`.
- **Traductions mortes** : `common.share` et `share.title` définies en FR/EN (App.jsx:137, 290, 352, 497) mais jamais lues par `t()` dans le fichier — aucune fonctionnalité de partage ne les consomme.
- **Duplication de logique SSE + retry-token** : `axStreamChatIn` (bridge.js:240-295) et `axStreamAnalysis` (bridge.js:414-464) réimplémentent chacun, quasi à l'identique, le découpage de frames SSE (`split('\n\n')`, extraction de la ligne `data:`, `JSON.parse`, boucle `reader.read()`) et la logique de retry sur 401/403 avec `tryRefresh()` — ce n'est pas factorisé dans une fonction commune malgré une structure identique à quelques noms de variables près (`final = evt.data` etc.).
- **`_convId` module-scope dans `bridge.js`** (bridge.js:184) : variable globale mutable utilisée par `ensureConversation`/`axChat`/`axNewConversation`, donc par les fonctions jamais appelées depuis `App.jsx` — code mort qui entraîne cet état module global avec lui (aucun risque actif tant que rien ne l'appelle, mais la fonction `ensureConversation` gérant la création implicite de conversation/projet n'est plus le chemin réellement emprunté : le chemin réel passe par `axCreateConversation` → `ensureConversation(true)`, qui, lui, est bien utilisé).
- **`removePending`/gestion des documents en attente** : le compteur d'upload (`uploading`, `uploadMsg`) n'a pas de retour visuel de succès — seul le cas d'échec (`uploadMsg.ok === false`) est rendu (App.jsx:2597-2600) ; en cas de succès, `uploadMsg` reste `null` et rien n'indique explicitement la réussite de l'import autre que l'apparition de la puce du document dans la liste `pendingDocs`.

---

## Constats bruts

- La pastille de crédits (topbar) ne se rafraîchit jamais après l'envoi d'un message ; elle n'est réglée qu'une fois au montage de la route `app`.
- Aucun garde-fou de crédits avant l'envoi d'un message de conversation, contrairement au flux Rapports (`startReport`) qui vérifie le solde et bascule sur un écran dédié avant d'appeler l'API.
- Aucun `AbortController` n'existe dans `bridge.js` ni `App.jsx` : changer de conversation ou de route pendant un streaming ne l'annule pas ; le `setConversations` final s'exécute quand même, potentiellement après que l'utilisateur a quitté l'écran.
- L'auto-scroll du fil est indexé sur `messages.length`, qui ne change pas pendant l'accumulation des deltas de streaming : la vue peut rester figée pendant qu'une longue réponse continue d'apparaître sous la ligne visible.
- Si l'événement de flux `delta` arrive avant l'événement `sources`, le contenu `__PENDING__` est écrasé par une chaîne potentiellement vide, faisant disparaître l'indicateur « AXIAL analyse… » avant l'arrivée de texte visible.
- La création de conversation peut échouer silencieusement et retomber sur un id client `'c-' + Date.now()` non persistant côté backend ; les messages envoyés dans ce fil ne seront jamais retrouvés après rechargement.
- Clic sur une conversation dans la liste : le fil s'affiche immédiatement vide (aucun skeleton/spinner) avant que `axMessages` ne réponde et peuple les messages.
- La recherche de la liste des conversations ne filtre que sur le titre, jamais sur le contenu des messages.
- Aucun moyen de renommer, supprimer, archiver ou épingler une conversation, ni côté UI ni côté `bridge.js` (aucun endpoint `PATCH`/`DELETE` correspondant).
- Aucun bouton pour régénérer une réponse, éditer un message envoyé, ou arrêter une génération en cours.
- Changer d'agent (Conversation / Market Scanner / Competitor Radar) en cours de fil est possible et non empêché — le sélecteur est visible et actif dans le composer d'une conversation déjà ouverte, et le mode est lu depuis `localStorage` à chaque envoi, indépendamment de l'historique du fil.
- Le bouton d'envoi n'est désactivé que si le champ est vide — rien n'empêche d'envoyer un nouveau message pendant qu'une réponse précédente est encore en cours de streaming dans le même fil.
- Les traductions `common.share` et `share.title` existent en FR/EN mais ne sont utilisées nulle part — aucune fonctionnalité de partage de conversation n'existe.
- Les imports `axChat` et `axNewConversation` (bridge.js) ne sont appelés depuis aucun endroit du code (`App.jsx` ni ailleurs) — code mort mais toujours exporté.
- La logique de parsing SSE + retry sur 401/403 est dupliquée quasi à l'identique entre `axStreamChatIn` (chat) et `axStreamAnalysis` (rapports) dans `bridge.js`.
- Le rendu markdown des réponses ne supporte pas les blocs de code génériques, le code inline, les liens `[texte](url)` ni les listes numérotées — seuls titres, listes à puces, tableaux, gras, citations `[N]` et blocs `viz` sont reconnus ; tout le reste s'affiche en texte brut, backticks compris.
- Les 4 questions suggérées par défaut (avant chargement du profil) sont câblées en français en dur et servent de repli même pour un utilisateur ayant choisi l'anglais.
- `.app-body` garde un grid fixe `280px 1fr` sur l'écran Conversations à toutes les tailles d'écran (aucune media query ne le change en dessous de 768px), contrairement aux autres surfaces qui basculent en une seule colonne via `.app-body-single`.
- Le panneau de citation (`role="dialog"`) n'a ni `aria-modal`, ni piège de focus, ni fermeture au clavier (`Escape`).
- Aucun garde-fou de taille de message côté front (pas de `maxLength`, pas de compteur de caractères).
- L'affichage d'erreur (`⚠️ ...`) est un message générique tiré directement de `e.message` du backend, rendu comme texte de bulle assistant — aucune distinction visuelle entre erreur réseau, session expirée, crédits insuffisants ou message trop long.
