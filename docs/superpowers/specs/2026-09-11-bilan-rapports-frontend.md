# Bilan factuel — surface « Rapports » (frontend)

Fichiers concernés : `frontend/app/_prototype/App.jsx` (8214 lignes), `frontend/app/_prototype/bridge.js` (610 lignes), `frontend/app/_prototype/markdown.js` (204 lignes), `frontend/app/globals.css` (3431 lignes). Backend de référence pour croiser le contrat d'API : `app/modules/reports/router.py`, `app/modules/analysis/router.py`, `app/modules/analysis/schemas.py`.

---

## 1. Écrans et composants

### Route et assemblage
- `subRoute === 'reports'` pilote une machine à 5 états locaux au composant racine : `reportsState` ∈ `{ empty, generating, editor, quota, erreur }`, déclarée avec `reportData`, `genMeta`, `quotaInfo`, `erreurRapport` (App.jsx:7049-7055). Aucun de ces états n'est dans une URL/route — changer de sous-route et revenir sur « Rapports » retombe sur l'état courant en mémoire (pas de perte tant que l'onglet reste ouvert), mais un rechargement de page réinitialise tout à `empty` (voir §2).
- Montage conditionnel direct dans le JSX racine, pas de sous-composant « Region » comme pour les conversations (App.jsx:8125-8163) : `ReportsEmpty` (state `empty`), `ReportsGenerating` (state `generating`), `ReportsEditor` (state `editor`), une carte d'erreur inline (state `erreur`), `ReportsQuota` (state `quota`).
- Layout : `.app-body-single` (globals.css:1432-1435) applique une seule colonne à toutes les sous-routes sauf `conversations` — Rapports est en pleine largeur, pas de panneau latéral de liste persistant.

### `ReportsEmpty` (App.jsx:4233-4326) — composeur
- `useEffectS(() => { axListReports().then(setSaved)... }, [])` (App.jsx:4239) : charge la liste des rapports archivés **à chaque montage** du composant (donc à chaque retour sur l'état `empty`, y compris après un `onBack` depuis l'éditeur — la liste se rafraîchit).
- Grille `.rep-types` (App.jsx:4278-4291, CSS globals.css:1571-1576) : 6 tuiles cliquables issues de `REPORT_TYPES` (App.jsx:28-35) —
  | id | icône | `analysis_type` backend | coût (crédits) |
  |---|---|---|---|
  | market | trending | etude_marche | 40 |
  | competitive | users | analyse_concurrentielle | 25 |
  | regulatory | shield | analyse_reglementaire | 25 |
  | risk | alert | analyse_risques | 25 |
  | investors | briefcase | cartographie_investisseurs | 30 |
  | custom | edit | synthese_executive | 40 |
  Une seule tuile active à la fois (`type` state, défaut `'market'`). Chaque tuile affiche titre + description i18n + coût en crédits (`tp.cost`), pas de durée par tuile.
- `rep-prompt-card` (App.jsx:4293-4311) : un unique `<textarea>` libre (pas de champ titre séparé), placeholder incitatif. Pied de carte : ligne d'estimation `reports.estimate : <strong>{credits}</strong> {reports.cost} · ~1 min` — **le « ~1 min » est un texte fixe, pas calculé**, et ne varie ni avec le type ni avec la longueur du prompt. Bouton « Lancer le rapport » (`reports.start`) appelle `onStart({ type, analysisType: sel.at, prompt })`.
- **Aucun sélecteur de profondeur n'existe dans cet écran.** La classe CSS `rep-depth-seg` (globals.css:1642-1661) est bien définie, mais dans le JSX elle n'est utilisée nulle part dans `ReportsEmpty` — elle est réemployée ailleurs, pour le toggle Clair/Sombre de l'onglet « Apparence » des réglages (App.jsx:5776-5779, `SettingsSurface`). Il n'y a donc pas de notion « Scan / Standard / Approfondi » quelque part dans l'interface actuelle, malgré les clés i18n `reports.depth`, `reports.depth.scan`, `reports.depth.standard`, `reports.depth.deep` définies (App.jsx:232-235, 545-548) et **jamais appelées par `t(...)` dans le composant**.
- `rep-templates` (App.jsx:4313-4322) : chips d'exemples de questions, `REPORT_TEMPLATES[lang]` (App.jsx:37-50), 4 par langue, codées en dur, cliquer une chip remplace le contenu du textarea (`setPrompt(s)`) — n'écrase pas le type sélectionné, ne lance rien automatiquement.
- Liste « Vos rapports » (App.jsx:4246-4266) : apparaît sous le composeur seulement si `saved.length > 0`. Chaque ligne = bouton pleine largeur avec icône fichier, titre tronqué (`text-overflow: ellipsis`), date formatée localement (`toLocaleDateString`, format court). Cliquer ouvre `onOpenReport(r.id)` → `openSavedReport`. **Pas de tri visible autre que celui renvoyé par le backend** (`axListReports`, ordre non garanti côté front), pas de recherche, pas de pagination, pas de filtre par type.

### `ReportsGenerating` (App.jsx:4331-4404) — génération
- Titre + sous-titre explicite : « Vous pouvez naviguer ailleurs — le rapport s'ouvrira ici dès qu'il est prêt. » (App.jsx:4362-4364) — message de confort qui annonce la persistance décrite en §2.
- Chronomètre local (`elapsed`, incrémenté chaque seconde par `setInterval`, App.jsx:4335-4338) affiché en `mm:ss`.
- Barre de progression réelle si le backend émet un `progress` numérique dans l'événement SSE (`genMeta.progress`), sinon repli **estimé sur le temps écoulé** : `elapsed < 15 → étape 0`, `< 35 → étape 1`, sinon `étape 2` (App.jsx:4353-4355) — un repli purement local si le flux ne renvoie pas de `progress`.
- Libellé d'état (`etatCourant`) mappé depuis `genMeta.step` via un dictionnaire à 5 clés (`start, retrieve, generate, finalize, done` → App.jsx:4346-4350) ; si `step` est absent ou inconnu, replie sur un texte générique « Génération en cours »/« Generating ».
- Liste de 3 étapes fixes affichées avec icône check/point actif/point vide (App.jsx:4342-4344, 4382-4394) : « Recherche des sources », « Analyse et rédaction », « Finalisation ». Ces 3 étapes sont **indépendantes** des 5 clés `ETATS` ci-dessus (deux découpages différents cohabitent dans le même écran).
- 4 blocs `.skeleton` shimmer statiques sous les étapes (App.jsx:4396-4399) — un simple effet de chargement, pas un aperçu du contenu en cours de génération (contrairement au chat, il n'y a pas de texte qui s'écrit progressivement pour les rapports).
- Layout : `.rep-gen` est une grille CSS 2 colonnes `1fr 360px` (globals.css:1692-1697, prévue pour un panneau latéral `.rep-gen-side`) mais le composant ne rend qu'un seul enfant, `.rep-gen-doc` — **la seconde colonne de 360px reste vide sur desktop**, gouttière inoccupée (voir §6, CSS mort `.rep-gen-side`, `.rep-gen-progress`, `.task-list`).

### `ReportsEditor` (App.jsx:4615-4737) — lecture d'un rapport (nouveau ou archivé)
- En-tête : titre du rapport, sous-titre mono `{N} sources · Rapport Axial`, `TopControls` (langue/thème).
- Barre d'actions (`editor-head`, App.jsx:4672-4702) : bouton retour (flèche), bouton **PDF** (`exportPdf`), lien **« Votre avis »** (`reports.feedback`), bouton **Notion** conditionnel.
  - Il n'y a **pas de tabs de rail** (« Plan » / « Sources » / « Activité ») dans le JSX rendu, malgré les clés i18n `reports.editor.outline`, `reports.editor.sources`, `reports.editor.activity`, `reports.editor.suggest` (App.jsx:249-252, 562-565) et la classe CSS `.rep-rail-tabs` (globals.css:1993-2012) — ces clés et cette classe ne sont référencées nulle part ailleurs dans `App.jsx` (recherche exhaustive : 0 occurrence de `rep-rail`, `rep-outline`, `rep-suggest`, `rep-chart`, `rep-source-counter`, `confidence-row`, `source-card`, `task-list` en dehors de `globals.css`). Le rail latéral à onglets décrit par le CSS n'existe pas dans le produit actuel.
  - « Votre avis » : `<a href={FORMULAIRE_FEEDBACK} target="_blank">` — un lien statique vers un Google Form public (App.jsx:23-26, 4682-4686), pas un appel API, pas de contexte du rapport transmis (ni id, ni titre). Le commentaire source (App.jsx:4678-4681) précise que c'est parce qu'« aucun moyen de dire ce qu'on pense d'un rapport n'existait dans l'app » avant ce bouton.
  - Livraison Notion : bouton affiché seulement si `outils.notion && outils.notion.connecte` (`axIntegrations()`, App.jsx:4627, 4687-4692). Pas de bouton Google Drive dans ce composant, bien qu'une intégration Drive existe ailleurs dans l'app (paramètres) et qu'un commentaire mentionne « Axial can drop your reports straight into your Drive » en code commenté (App.jsx:5897) — cette phrase n'est reliée à aucun bouton actif dans `ReportsEditor`.
  - Export PDF : `axDownloadReportPdf(id, title.slice(0,60)+'.pdf')` (bridge.js:595-610) télécharge un blob authentifié et déclenche un téléchargement navigateur classique (pas d'ouverture d'onglet, pas d'aperçu). Si le rapport n'a pas encore d'`id` archivé (`savedId` null), le front appelle d'abord `axCreateReport(...)` pour l'archiver, puis exporte — mais en pratique un rapport généré via `axStreamAnalysis` arrive déjà avec un `report_id` non nul la plupart du temps (voir §2, archivage automatique côté backend), donc ce chemin de secours ne s'active surtout que pour un cas dégradé où le backend n'a pas pu archiver.
- Corps du document : `MarkdownView` (App.jsx:4704-4714) rend `content` avec le parseur `markdown.js` — titres `#`/`##`/`###`, paragraphes, listes (1 niveau d'imbrication), citations `>` (récursives), tableaux `| … |`, blocs de code ``` (avec bouton copier), et blocs ` ```viz ` rendus en figure SVG (`VizFigure`) ou en tableau de repli. Citations `[N]` cliquables (`onCite`) qui scrollent vers la source correspondante (`#src-N`) et appliquent une classe `.src-flash` 1.2 s.
- `VizFigure` (App.jsx:4443-4482) : si un objet `viz` est fourni (rapport archivé), affiche `<img src="{AX_API}/viz/{empreinte}.svg">` — l'image est **toujours générée côté serveur**, jamais tracée en Canvas/SVG côté client. En l'absence de `viz` archivé pour un bloc ` ```viz `, tente `axRenduViz(spec)` à la volée puis retombe sur un rendu en tableau HTML si le rendu échoue (`statut !== 'ok'`).
- Bloc Sources (App.jsx:4717-4734) : liste simple `[N] titre/lien · domaine`, ancrée par id `src-{n}` pour le scroll depuis les citations. Pas de tri, pas de regroupement par domaine, pas de compteur d'extraits par source.
- Largeur : `.surface` conteneur à `maxWidth: 1000`, corps du texte `.rep-doc` à `maxWidth: 820` (styles inline, App.jsx:4661, 4704) — recouvrent/priment sur les valeurs CSS `.rep-doc` (padding `40px 64px` en desktop, globals.css:1882-1888).

### `ReportsQuota` (App.jsx:4742-4775) — crédits insuffisants
- Affichée quand `axBal < cost` **avant même l'appel réseau** (garde côté client, voir §2) ou après un 402 en cours de génération.
- Carte unique (`.quota-usage`) répétant titre + corps, plus une ligne mono optionnelle « Ce rapport coûte {needed} crédits, vous en avez {available}. » si les deux valeurs sont connues.
- Deux boutons : « Retour » (repasse à `empty`) et « Voir les crédits » (`onSeeCredits` → `setSubRoute('credits')`, simple navigation, **pas d'achat direct depuis cet écran** — contrairement à `ModaleCredits` (App.jsx:2590-2616) qui, elle, propose des CTA d'achat/abonnement directs ailleurs dans l'app).

### État d'erreur (`reportsState === 'erreur'`, App.jsx:8137-8155)
- Pas de composant dédié : réutilise l'enveloppe `.rep-gen > .rep-gen-doc` (la même que l'écran de génération) pour poser une `CarteErreur` (App.jsx:2619-2643) + un bouton « Retour ».
- `CarteErreur` est le **même composant que celui utilisé pour les erreurs de chat** dans les conversations (partagé, pas dupliqué) : titre + détail + un bouton d'action optionnel dont le libellé dépend de `erreur.action` (`credits`, `reconnexion`, `reessayer`, `rouvrir`).

### « Historique » des rapports — pas d'écran dédié
- Il n'existe **pas** de composant `ReportsList` séparé : la liste « Vos rapports » est une simple section de `ReportsEmpty` (voir plus haut), pas une vue plein écran, pas de route propre, pas de filtre/recherche/tri.
- Il n'y a **aucune trace** d'anciens rapports « de l'ancienne plateforme » dans ce module : le texte « Rapports produits » et les métriques de coût par rapport (App.jsx:1608-1615) appartiennent à `PilotageSurface`, l'écran d'administration interne (`subRoute === 'pilotage'`, réservé aux comptes `is_admin`), pas à la surface utilisateur `reports`.

---

## 2. État et flux de données

### `startReport` (App.jsx:7056-7093)
1. Garde crédits côté client : `REPORT_TYPES.find(...).cost` comparé à `axBal` (solde chargé une fois au montage de la route `app`, comme documenté pour les conversations). Si insuffisant → `reportsState = 'quota'`, **aucun appel réseau n'est fait**.
2. Sinon : `setGenMeta({ prompt, progress: 5, step: 'start' })`, `reportsState = 'generating'`.
3. Appelle `axStreamAnalysis({ query: prompt, analysis_type: analysisType || 'synthese_executive' }, onEvent)` (bridge.js:580-589). `onEvent` met à jour `genMeta` en fusionnant `progress`, `step`, `message` à chaque trame SSE reçue (App.jsx:7072).
4. À la résolution : `reportData = r`, `genMeta = null`, `reportsState = 'editor'`.
5. En cas d'échec : `decrireErreur(e, t)` (App.jsx:2523-2586) transforme l'erreur brute en `{ titre, detail, action }` ; sur `action === 'reconnexion'` → déconnexion forcée (`sessionExpiree()`) ; sur `action === 'credits'` → ouvre `ModaleCredits` **en plus** de l'écran d'erreur et rafraîchit le solde ; sinon la carte d'erreur garde `args` (type/analysisType/prompt d'origine) pour permettre un « Réessayer » qui relance **exactement** la même requête (mais avec une nouvelle clé d'idempotence implicite, `axStreamAnalysis` n'en prend d'ailleurs pas — voir ci-dessous).

### `axStreamAnalysis` / `lireFluxSSE` (bridge.js:580-589, 216-253, 265-311)
- Ouvre `POST {AX_API}/analysis/stream` via `ouvrirFluxSSE`, partagée avec le chat. Comportement commun : rejoue une fois sur 401/403 après `tryRefresh()`, ne réessaie jamais un 4xx métier (402/413/etc. remontent tels quels), replie sur la route bloquante `axRunAnalysis` (`POST /analysis/run`) **uniquement** si le flux ne s'ouvre pas du tout (`stream_unavailable`, réponse 5xx ou sans corps).
- Contrairement à `axStreamChatIn`, `axStreamAnalysis` **ne prend pas de paramètre `idempotencyKey`** — un « Réessayer » après échec relance une requête normale, sans protection contre un double débit si le premier appel avait en fait réussi côté serveur avant l'erreur réseau côté client.
- `lireFluxSSE` transmet **chaque** événement `data:` reçu à `onEvent`, sans filtrage : le composant `ReportsGenerating` ne lit que `progress`, `step`, `message`, mais rien n'empêche le backend d'envoyer d'autres champs (non exploités côté front s'ils existent).
- La réponse finale (`evt.done && evt.data`) correspond au schéma backend `AnalysisResponse` (app/modules/analysis/schemas.py:18-26) : `{ analysis_type, title, content, report_id, sources, degraded, status_note, metadata }`. **`degraded` et `status_note` — qui signalent un contenu dégradé (ex. moteur de recherche web indisponible) — sont présents dans la charge utile mais ne sont lus nulle part dans `App.jsx`** (recherche exhaustive des chaînes `degraded`, `status_note`, `metadata` dans App.jsx : 0 occurrence) : un rapport dégradé s'affiche exactement comme un rapport complet, sans bandeau ni mention.
- `report_id` est déjà renseigné par le backend à la fin d'un flux réussi (archivage automatique côté serveur, commentaire backend « rapport archivé automatiquement »), donc `ReportsEditor` a en général `savedId` dès l'ouverture et n'a besoin d'appeler `axCreateReport` que dans les cas où ce champ manquerait.

### Navigation pendant la génération
- `reportsState`/`genMeta` vivent dans le composant racine de l'app (au même niveau que `route`/`subRoute`), pas dans `ReportsGenerating` lui-même : changer de `subRoute` (ex. aller sur « Conversations ») démonte `ReportsGenerating` mais **ne coupe pas** la promesse `axStreamAnalysis` en cours — elle continue de s'exécuter et, à sa résolution, met à jour `reportData`/`reportsState` même si l'utilisateur n'est plus sur l'écran Rapports. Revenir sur « Rapports » pendant que ça tourne réaffiche `ReportsGenerating` avec la progression alors accumulée dans `genMeta` (cohérent avec le message affiché à l'utilisateur, App.jsx:4362-4364).
- **Un rechargement de page (F5) perd tout** : `reportsState`, `genMeta`, `reportData` sont des `useState` sans persistance (`localStorage`/`sessionStorage`) — un rechargement pendant la génération retombe sur `reportsState = 'empty'`, sans aucun moyen de retrouver ou de reprendre le suivi de cette génération (pas de polling par identifiant de tâche, pas de endpoint `/analysis/jobs/{id}` appelé côté front). Le rapport, s'il finit par être produit côté serveur, apparaîtra plus tard dans la liste « Vos rapports » (car archivé côté backend indépendamment de la session front), mais l'utilisateur n'a aucun signal de progression pendant ce temps.

### `axListReports` / `axGetReport` / `openSavedReport`
- `axListReports()` → `GET /reports`, renvoie `ReportOut[]` (`id, title, analysis_type, created_at`, **pas de `content`/`sources`/coût**, app/modules/reports/router.py:24-28, 49-56).
- `axGetReport(id)` → `GET /reports/{id}`, renvoie `ReportDetail` (ajoute `content, sources, viz`).
- `openSavedReport(id)` (App.jsx:7094-7100) : `setReportData({ ...r, report_id: r.id })`, `reportsState = 'editor'`. Aucune gestion d'erreur visible à l'utilisateur (`catch (e) { /* noop */ }`) — un échec de chargement (rapport supprimé côté serveur entre-temps, id invalide, etc.) ne produit **aucun message ni changement d'écran** ; l'utilisateur reste sur l'écran d'où il a cliqué, sans retour.

### `VizFigure` / `axRenduViz`
- Deux sources possibles pour une visualisation : un objet `viz` déjà résolu (archivé dans `ReportDetail.viz`, ou reçu en flux dans le chat) → affichage direct de l'image SVG servie par `{AX_API}/viz/{empreinte}.svg` ; ou un bloc brut ` ```viz ` sans `viz` associé → appel `axRenduViz(spec)` (`POST /viz/rendu`) qui rend soit `{ statut:'ok', empreinte }` (image), soit un statut de repli avec un `tableau` (rendu en `<table>`). Dans `ReportsEditor`, les rapports archivés fournissent `data.viz` (tableau d'objets `{statut, empreinte}` par index de bloc) — le rendu est donc normalement direct, sans appel `axRenduViz` supplémentaire, sauf lacune dans l'archive.

### Export PDF (`axDownloadReportPdf`, bridge.js:595-610)
- `GET {AX_API}/reports/{id}/pdf` avec en-tête `Authorization`, réponse `blob()`, déclenchement navigateur (`<a download>`), révocation immédiate de l'URL objet (contrairement à `axExporterConversation` qui attend 1 s avant de révoquer — incohérence mineure entre les deux fonctions, bridge.js:536 vs 609).
- Le rendu du PDF est **entièrement généré côté backend** (`service.export_pdf`, `app/modules/reports/router.py:68-76`) — le front n'a aucune règle CSS `@media print` (recherche exhaustive dans `globals.css` : 0 occurrence) : il ne peut ni prévisualiser, ni garantir que la mise en page PDF ressemble à celle de `ReportsEditor` à l'écran ; les deux rendus sont produits par deux moteurs différents (React+CSS pour l'écran, backend pour le PDF).

### Retour utilisateur (« Votre avis »)
- Aucune route API de feedback n'existe côté `bridge.js` (aucune fonction `axFeedback*`). Le seul mécanisme est le lien Google Form externe cité en §1 — aucune donnée structurée n'est envoyée vers le backend Axial lui-même.

---

## 3. Ce que l'utilisateur NE peut PAS faire (vérifié)

- **Renommer un rapport** : ni bouton, ni fonction bridge (`axListReports`/`axGetReport`/`axCreateReport` sont les seules routes reports côté front ; pas de `PATCH /reports/{id}` — confirmé aussi côté backend, `app/modules/reports/router.py` n'a aucune route `PATCH`).
- **Supprimer un rapport** — alors que **le backend le permet** : `DELETE /reports/{report_id}` existe (`app/modules/reports/router.py:80-84`, `service.delete_report`), mais `bridge.js` n'expose **aucune** fonction `axDeleteReport`/`axSupprimerRapport`, et aucun bouton de suppression n'apparaît dans `ReportsEmpty` ni `ReportsEditor`. C'est une capacité backend non câblée côté front, pas une absence de fonctionnalité côté produit.
- **Archiver / masquer un rapport** : aucune notion d'archive pour les rapports (à ne pas confondre avec l'archivage des conversations/dossiers, qui existe ailleurs).
- **Taguer / classer un rapport** : pas de dossier, pas de tag ; seul `analysis_type` (le type choisi à la création) existe et n'est ni affiché ni filtrable dans la liste « Vos rapports ».
- **Rechercher dans les rapports** : pas de champ de recherche sur la liste « Vos rapports » (contrairement aux conversations qui ont `conv.search`) ni de recherche plein texte dans le contenu.
- **Régénérer une section** : aucune granularité section par section — `startReport` régénère un rapport entier, il n'existe pas de bouton par section/paragraphe (les clés i18n `reports.gap.*`/`reports.conflict.*` décrivant des cartes « donnée insuffisante » / « sources en désaccord » avec actions « Fournir une donnée », « Recherche profonde », « Utiliser source A/B », « Citer les deux » sont définies — App.jsx:254-265, 567-578 — mais **ne sont référencées par aucun composant rendu** ; recherche exhaustive des chaînes `reports.gap`, `reports.conflict` en dehors du dictionnaire i18n : 0 occurrence).
- **Éditer le prompt après génération** : le textarea disparaît avec `ReportsEmpty` dès que `reportsState` passe à `generating`/`editor` ; il n'y a pas de champ prompt visible ni modifiable dans `ReportsEditor`. Un « Réessayer » après erreur relance le prompt d'origine tel quel (`args`), sans possibilité de le modifier avant relance.
- **Arrêter une génération en cours** : `ReportsGenerating` n'a aucun bouton d'annulation, et `axStreamAnalysis`/`ouvrirFluxSSE` ne reçoit pas de `signal` d'`AbortController` (contrairement à `axStreamChatIn`/`axRegenerer`/`axEditerMessage`, qui acceptent tous un `signal` — App.jsx/bridge.js: comparaison des signatures, bridge.js:427-444 vs 580-589). Un rapport lancé va jusqu'à son terme (ou son échec) sans intervention possible.
- **Voir le coût/nombre de tokens d'un rapport précis** : `ReportOut`/`ReportDetail` (backend) n'exposent ni coût ni tokens par rapport (contrairement aux messages de conversation, qui portent `credits`, `tokens_entree`, `tokens_sortie`, `cout_micro_eur` — voir le bilan Conversations, §2). Seul un coût *agrégé, par type de rapport*, existe dans l'écran d'administration `Pilotage` (réservé `is_admin`), pas dans la surface utilisateur.
- **Partager un rapport (lien public)** : la seule « livraison » possible est Notion (si connecté) ou l'export PDF téléchargé manuellement ; il n'existe pas de lien de partage public/URL signée généré côté front.
- **Comparer deux rapports** : aucune vue à deux colonnes, aucune sélection multiple dans la liste « Vos rapports » (chaque ligne n'est qu'un bouton d'ouverture simple).
- **Exporter en DOCX (ou tout format hors PDF/Notion)** : `bridge.js` n'a que `axDownloadReportPdf` et `axDeliverReport('notion', ...)` pour les rapports (à comparer à `axExporterConversation(id, format, ...)` pour les conversations, qui accepte un paramètre `format` — le mécanisme reports est plus restreint, pas paramétrable en format).
- **Voir la progression de génération après un rechargement de page** : confirmé en §2 — aucune persistance, aucun polling par identifiant de tâche.
- **Choisir une profondeur d'analyse (Scan/Standard/Approfondi)** : clés i18n définies, aucun sélecteur rendu (voir §1).

---

## 4. Faits visuels / UX

- **Largeurs** : conteneur `.surface` en pleine largeur avec `max-width: 1000px` posé en inline sur `ReportsEditor` (App.jsx:4661) ; corps de texte `.rep-doc` limité à `max-width: 820px` en inline (App.jsx:4704) — ces valeurs inline priment sur les règles `.rep-doc` de `globals.css` (padding `40px 64px` desktop, globals.css:1882-1888).
- **Grille des types de rapport** : 3 colonnes desktop (`repeat(3,1fr)`, globals.css:1571-1576), 2 colonnes sous 960px, 1 colonne sous 600px (globals.css:2769-2774).
- **Mobile 375px (passe responsive récente, commentaires explicites dans `globals.css` autour de la ligne 3395-3406)** :
  - `.rep-gen { height: auto; }` — sur desktop `.rep-gen` a une hauteur figée `calc(100vh - 56px - 32px)` avec `overflow-y: auto` interne (deux panneaux qui défilent chacun dans leur bloc) ; en mobile la hauteur est libérée pour que ce soit **la page entière** qui défile (correctif documenté : « la hauteur figée … empilait deux panneaux défilants dans la hauteur d'un seul »).
  - `.rep-gen-doc` et `.rep-doc` passent de `padding: 40px 56/64px` à `20px 14px` — le commentaire source chiffre l'ancien problème : « 64 px de marge de chaque côté ne laissaient que 219 px de texte sur un écran de 375 ».
  - `.rep-gen-doc h1`/`.rep-doc h1` passent de 28-30px à 22px.
  - Un commentaire confirme explicitement qu'une classe `.rep-editor` a été **retirée du fichier CSS** car « la classe n'était rendue nulle part dans `App.jsx` » — trace directe d'un nettoyage de code mort lié à cette passe responsive.
  - Tableaux longs : `.md-table-wrap` a `overflow-x:auto` en permanence ; en mobile, `.md-table { min-width: 460px }` est ajouté (globals.css:3352) pour forcer un défilement horizontal propre plutôt qu'un tableau écrasé.
  - Figures de visualisation : `figure.viz { overflow-x:auto }` + `figure.viz img { min-width: 480px }` en mobile (globals.css:3353-3354) — l'image garde sa largeur native et défile horizontalement plutôt que de se déformer.
- **PDF vs écran** : pas de feuille de style `@media print` — le rendu PDF est produit par un moteur backend indépendant (voir §2), donc rien ne garantit visuellement la parité avec `ReportsEditor` à l'écran ; c'est un fait vérifiable par l'absence de toute règle print dans `globals.css`.
- **États de chargement** : skeletons shimmer statiques dans `ReportsGenerating` (4 barres, pas de texte progressif) ; aucun skeleton dans `ReportsEditor` pendant l'ouverture d'un rapport archivé (`openSavedReport` n'a pas d'indicateur de chargement propre — l'écran reste sur son état précédent jusqu'à la résolution de `axGetReport`, sans spinner).
- **i18n / français en dur** : la structure des clés `reports.*` est bien traduite FR/EN (dictionnaires séparés, App.jsx:183-270 pour FR, 498-583 pour EN). Restent en français fixe, indépendamment de la langue choisie : le libellé de section « Vos rapports »/« Your reports » est en fait conditionné par `lang` directement en JS (pas une clé `t()`, App.jsx:4249) — donc traduit correctement mais par un chemin différent du reste ; en revanche `REPORT_TEMPLATES` (les 4 questions d'exemple) n'a pas de mélange de langue (une liste FR et une liste EN distinctes, correctement choisies par `tpl = REPORT_TEMPLATES[lang]`). Le formulaire de feedback Google (§1) est un lien unique, non localisé, quelle que soit la langue de l'interface.
- **Accessibilité** : recherche exhaustive d'attributs `aria-*`/`role=` dans le bloc de code des 4 composants Reports (App.jsx:4193-4780) : la seule occurrence est `role="group" aria-label="Language"` sur le sélecteur FR/EN de `TopControls` (composant partagé, pas spécifique aux rapports). Ni la grille de types, ni le textarea, ni la liste de rapports sauvegardés, ni la barre de progression, ni la carte d'erreur ne portent de rôle ARIA dédié (la carte d'erreur porte `role="alert"`, héritée du composant partagé `CarteErreur`, App.jsx:2630).

---

## 5. Erreurs

- **Chemin d'erreur de génération** : confirmé que la génération de rapport utilise désormais le même mécanisme que le chat — `decrireErreur(e, t)` + `CarteErreur` (§1, §2) — plus de message d'exception brut injecté comme faux contenu de rapport (commentaire explicite dans le code, App.jsx:7078-7082, qui documente le changement par rapport à un ancien comportement).
- **Crédits insuffisants** :
  - **Avant l'appel réseau** : détecté côté client via `axBal` (solde en cache) comparé au coût de la tuile choisie → écran `ReportsQuota` directement, sans requête.
  - **Pendant/à la fin d'un flux** (ex. solde consommé entre-temps par un autre onglet) : `decrireErreur` détecte `code === 'insufficient_credits'` ou `statut === 402` → ouvre en plus `ModaleCredits` (superposée à l'écran d'erreur) et rafraîchit `axBal`.
  - Ces deux chemins produisent des écrans différents pour la même cause (`ReportsQuota` en pré-vérification vs `ModaleCredits` + `CarteErreur` en post-échec) — pas un écran unique de « crédits insuffisants ».
- **Session expirée** (401 + refresh échoué) : `erreur.action === 'reconnexion'` → déconnexion forcée immédiate (`sessionExpiree()`), pas d'affichage de la carte d'erreur reports dans ce cas précis (retour anticipé, App.jsx:7085).
- **Flux réseau coupé sans `done`** : `lireFluxSSE` lève une erreur `code: 'reseau'` avec le message `"Génération interrompue."` (bridge.js:583) — passé par `decrireErreur` sous la branche réseau générique (`err.reseau.*`, action `reessayer`).
- **Flux indisponible dès l'ouverture** (5xx, pas de corps) : `axStreamAnalysis` retente automatiquement la route bloquante `axRunAnalysis` (repli silencieux, pas d'erreur visible à l'utilisateur si ce repli réussit) — seul un échec du repli lui-même remonte une erreur.
- **Ouverture d'un rapport archivé en échec** (`openSavedReport`) : `catch (e) { /* noop */ }` — **aucune erreur n'est montrée à l'utilisateur**, ni carte, ni toast ; l'écran reste inchangé (voir §2). C'est le seul point d'entrée reports qui n'utilise pas `decrireErreur`/`CarteErreur`.
- **Contenu dégradé** (`degraded`/`status_note` du backend, quand la recherche web primaire est indisponible) : reçu dans la charge utile finale mais **jamais lu ni affiché** côté front (confirmé en §2) — un rapport dégradé apparaît visuellement identique à un rapport complet, sans bandeau d'avertissement, contrairement à ce que suggèrent les champs prévus côté backend.
- **Sections/paragraphes vides ou lacunaires** : pas de traitement spécial — le markdown est rendu tel quel ; les mécanismes envisagés de « lacune de donnée » / « sources en désaccord » (`reports.gap.*`, `reports.conflict.*`) ne sont pas implémentés (voir §3), donc un paragraphe pauvre en signal ne déclenche aucune UI particulière, il s'affiche comme n'importe quel autre paragraphe.
- **Timeouts** : pas de gestion de timeout dédiée côté front (pas de `setTimeout`/limite de durée sur `axStreamAnalysis` ou `ouvrirFluxSSE`) — la génération peut rester dans l'état `generating` indéfiniment tant que la connexion SSE reste ouverte côté navigateur ; seule une coupure réelle de flux (paquet fermé sans `done`) déclenche l'erreur réseau décrite plus haut.

---

## 6. Code mort ou dupliqué dans les surfaces Rapports

- **CSS d'un éditeur 3 colonnes jamais construit** : `globals.css` définit un système complet — rail latéral à onglets (`.rep-rail`, `.rep-rail-section`, `.rep-rail-tabs`, globals.css:1983-2012), panneau outline (`.rep-outline`, `.rep-outline-label`, `.rep-outline-item`, globals.css:1844-1880), cartes de suggestion Axial (`.rep-suggest`, `.rep-suggest-icon`, `.rep-suggest-body`, `.rep-suggest-label`, `.rep-suggest-actions`, globals.css:1937-1964), bloc graphique nommé (`.rep-chart`, `.rep-chart-title`, globals.css:1966-1980), compteur de sources (`.rep-source-counter`, `.num`, `.lbl`, globals.css:1821-1839), cartes source individuelles (`.source-card` et enfants, globals.css:2014-2040+), barre de confiance par section (`.confidence-row`, `.confidence-fill`, globals.css:2095-2103) et panneau latéral de génération avec liste de tâches (`.rep-gen-side`, `.rep-gen-progress*`, `.task-list`, `.task`, `.task-dot`, `.task-body`, `.task-title`, `.task-meta`, globals.css:1752-1819). **Aucune de ces classes n'est utilisée dans `App.jsx`** (vérifié par recherche exhaustive de chaque nom de classe). Elles correspondent très probablement à une itération antérieure — plus ambitieuse — de l'écran Rapports (rail de navigation, gestion des conflits de sources, confiance par section) qui a été remplacée par la version actuelle plus simple, sans que le CSS associé soit nettoyé.
- **Clés i18n orphelines** : `reports.depth`, `reports.depth.scan/standard/deep`, `reports.editor.outline`, `reports.editor.sources` (doublon : aussi utilisée en dur dans le bloc Sources de `ReportsEditor` sans passer par `t()`, App.jsx:4720), `reports.editor.activity`, `reports.editor.suggest`, `reports.gap.title/body/add/deepen/confidence`, `reports.conflict.title/body/recommendation/use_a/use_b/cite_both` — définies en FR et EN (donc doublées) mais jamais appelées par `t(...)` dans le code des composants Reports.
- **`rep-depth-seg` détourné** : la classe CSS conçue pour un segmented control « profondeur » (globals.css:1642-1661) est en réalité utilisée dans `SettingsSurface` pour le toggle Clair/Sombre (App.jsx:5776), un réemploi opportuniste sans rapport sémantique avec son nom.
- **`.rep-gen` grille à 2 colonnes sous-exploitée** : la grille CSS réserve une colonne de 360px (`.rep-gen-side`) qui n'est jamais peuplée ni par `ReportsGenerating` ni par l'écran d'erreur (qui réutilise le même conteneur `.rep-gen`/`.rep-gen-doc`) — gouttière vide visible sur desktop pour ces deux états.
- **Incohérence mineure entre exports** : `axExporterConversation` révoque son URL objet après 1000 ms (`setTimeout`, bridge.js:536), `axDownloadReportPdf` la révoque immédiatement en synchrone (bridge.js:609) — deux fonctions très proches, écrites différemment, sans qu'une raison fonctionnelle n'explique l'écart (risque, en théorie, de révoquer l'URL avant que certains navigateurs aient fini d'écrire le fichier téléchargé).
- **Capacité backend non câblée** : `DELETE /reports/{report_id}` existe côté API (app/modules/reports/router.py:80-84) sans aucune fonction bridge ni bouton front correspondants (voir §3) — pas du code mort côté front à proprement parler, mais une fonctionnalité backend prête, invisible côté produit.
- **Champs de réponse ignorés** : `degraded`, `status_note`, `metadata` du schéma `AnalysisResponse` (backend) transitent jusqu'au front dans `reportData` sans jamais être lus (voir §2, §5) — donnée transportée mais non exploitée.

---

## Constats bruts

- La génération de rapport n'a ni pause, ni annulation, ni reprise après rechargement de page : un F5 pendant `generating` perd tout affichage de progression sans moyen de le retrouver, même si le rapport finit par être archivé côté serveur.
- Le backend expose une suppression de rapport (`DELETE /reports/{id}`) que le frontend ne câble nulle part — l'utilisateur ne peut supprimer aucun rapport depuis l'interface.
- Une quantité significative de CSS (rail à onglets, outline, cartes de suggestion, confiance par section, compteur de sources, panneau de progression à tâches) décrit un éditeur de rapport plus riche que celui réellement rendu ; aucune de ces classes n'est référencée dans `App.jsx`.
- Les clés i18n pour la profondeur d'analyse (Scan/Standard/Approfondi) et pour les cartes « donnée insuffisante » / « sources en désaccord » existent en FR et EN mais ne sont appelées par aucun composant — ces fonctionnalités n'existent pas dans le produit actuel malgré leur préparation en i18n.
- Les champs `degraded` et `status_note`, renvoyés par le backend pour signaler un contenu de rapport dégradé, ne sont lus nulle part côté front : un rapport dégradé et un rapport complet sont visuellement indiscernables pour l'utilisateur.
- Le seul mécanisme de retour utilisateur sur un rapport est un lien statique vers un Google Form public, sans transmission d'aucune donnée structurée (id, titre, contenu) au backend Axial.
- `openSavedReport` avale silencieusement ses erreurs (`catch (e) { /* noop */ }`) — c'est le seul point d'entrée du module Rapports qui ne passe pas par `decrireErreur`/`CarteErreur`.
- La passe responsive à 375px a explicitement retiré une classe CSS `.rep-editor` documentée comme non rendue nulle part, confirmant que le nettoyage du CSS mort de ce module est partiel (beaucoup d'autres classes mortes, listées en §6, restent en place).
- Aucune règle `@media print` n'existe dans `globals.css` : le rendu PDF, produit par un moteur backend séparé, n'a aucune garantie de parité visuelle avec l'écran `ReportsEditor`.
- Aucun attribut ARIA dédié n'existe sur les composants Rapports au-delà de ceux hérités de composants partagés (`TopControls`, `CarteErreur`) — grille de types, textarea, liste de rapports sauvegardés et barre de progression sont sans rôle explicite.
