# Inventaire des éléments cliquables — App.jsx / bridge.js / page publique

Périmètre : `frontend/app/_prototype/App.jsx` (10107 lignes), `frontend/app/_prototype/bridge.js` (802 lignes), `frontend/app/p/[pseudo]/[slug]/page.tsx` (327 lignes).

Méthode : recensement de tous les `<button`, `<a`, éléments avec `onClick` (grep systématique, 157 occurrences `onClick`, 140 `<button>`), lecture du code source autour de chaque occurrence, et vérification croisée que chaque fonction `axXxx(...)` appelée dans `App.jsx` existe bien comme export dans `bridge.js` (vérification automatisée : **0 fonction manquante** — tous les appels `axXxx(...)` du front trouvent leur export dans `bridge.js`).

## Résumé

- **Total d'éléments cliquables recensés** : ~165 (157 `onClick` + liens `<a href>` fonctionnels de la landing/légal/docs/page publique).
- **Branchés et fonctionnels** : ~161 — la quasi-totalité de l'application (conversations, menus ⋯, rapports, agents/veilles, crédits, abonnement, intégrations Notion/Drive, mémoire/documents, paramètres, onboarding, authentification incluant « mot de passe oublié », page publique de rapport partagé) est correctement câblée : chaque bouton appelle soit un handler local cohérent (changement d'état, ouverture de modale), soit une fonction `axXxx` de `bridge.js` qui correspond à une route existante côté API.
- **Éléments non branchés ou douteux : 4**, tous mineurs et localisés dans la Documentation :
  1. **`App.jsx:7458`** — lien « Écrivez à support@axial.intelligence » (FR) : `href="#"`, pas de `mailto:`. Verdict : **`href="#"`** — clic sans effet.
  2. **`App.jsx:7459`** — même lien en anglais (« Reach support@axial.intelligence »), même défaut : `href="#"` sans `mailto:`. Verdict : **`href="#"`**.
  3. Ces deux liens partagent un second défaut, **douteux** : l'adresse affichée est `support@axial.intelligence`, un domaine différent de celui utilisé ailleurs dans l'app pour les contacts commerciaux (`sales@axial-ia.fr`, landing page et écran Crédits) — probablement une adresse inexistante ou obsolète.
  4. **`App.jsx:1959-1962`** — trois entrées du dictionnaire i18n (« Continuer avec Google », « Se connecter avec Google », « Connexion Google bientôt disponible — utilisez votre email professionnel ») ne sont référencées par **aucun** JSX : pas de bouton Google Sign-in dans `AuthPage`. Verdict : **code mort** (chaînes orphelines, pas un bouton visible — signalé par prudence car il évoque un "bientôt" explicite, mais n'est pas un élément cliquable actif aujourd'hui).

- **Point positif à noter** : le lien `App.jsx:1768` (« Pas encore de compte ? » → « Créer un compte ») utilise aussi `href="#"`, mais il porte un `onClick={(e) => { e.preventDefault(); setMode('signup'); }}` qui neutralise le comportement d'ancre et bascule l'onglet d'inscription : celui-ci est **branché**, ce n'est pas un lien mort malgré l'apparence.

Aucun `onClick={() => {}}` vide, aucun `console.log`/`alert(` de diagnostic laissé dans un handler de clic (les deux seuls `window.alert(...)` — lignes 4232 et 4238, écran Pilotage/Comptes admin — sont des remontées d'erreur volontaires dans un flux `try/catch`, pas des placeholders), aucun `TODO` dans le JSX, aucun bouton avec `disabled` codé en dur en production (tous les `disabled` rencontrés sont conditionnels : `busy`, `!value.trim()`, `isCurrent`, etc.).

Le tableau détaillé (élément par élément, écran par écran) n'est pas reproduit dans cette réponse — voir `inventaire.md` pour le détail complet.

---

## Tableau détaillé

Légende handler : « inline » = fonction fléchée définie directement dans le `onClick`. Verdict par défaut « branché » sauf mention contraire.

### Landing page (logged-out)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| LandingLangPill | FR | 1358 | inline `window.setAxialLang('fr')` | change langue globale | branché |
| LandingLangPill | EN | 1359 | inline `window.setAxialLang('en')` | change langue globale | branché |
| LandingPage nav | `landing.nav.signin` | 1399 | `onCTASignIn` (prop) | route vers AuthPage mode login | branché |
| LandingPage nav | `landing.nav.start` | 1400 | `onCTAStart` (prop) | route vers AuthPage mode signup | branché |
| LandingPage hero | `landing.hero.cta.start` | 1425 | `onCTAStart` | idem | branché |
| LandingPage hero | `landing.hero.cta.signin` | 1428 | `onCTASignIn` | idem | branché |
| LandingPage pricing | "Commencer"/"Get started" | 1526 | `onCTAStart` | idem | branché |
| LandingPage pricing (Enterprise) | "Nous contacter" | 1525 | `<a href="mailto:sales@axial-ia.fr">` | ouvre client mail | branché |
| LandingPage CTA finale | `landing.cta.btn` | 1539 | `onCTAStart` | idem | branché |
| LandingPage footer | CGU / Confidentialité / Mentions | 1555-1557 | `<a href="/legal/...">` | navigation interne | branché |
| LandingPage nav | Product/How/Trust/Pricing | 1392-1395 | `<a href="#product">` etc. | ancres internes à la page | branché |

### Authentification (auth.jsx)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| AuthPage | Retour | 1694 | `onBack` (prop) | retour à landing | branché |
| AuthPage tabs | Créer un compte | 1722 | inline `setMode('signup')` | bascule onglet | branché |
| AuthPage tabs | Se connecter | 1725 | inline `setMode('login')` | bascule onglet | branché |
| AuthPage | "Mot de passe oublié ?" | 1742 | `askReset` → `axForgotPassword(email)` | POST /forgot-password (bridge.js:124) | branché |
| AuthPage | submit "Créer mon compte"/"Se connecter" | 1755 (`type=submit`, `form onSubmit={submit}`) | `submit` → `finish('email')` → `onSubmit` (prop, appelle `axRegister`/`axLogin`) | inscription/connexion | branché |
| AuthPage | "Créer un compte" (lien bas de page, mode login) | 1768 | inline `e.preventDefault(); setMode('signup')` | bascule onglet malgré `href="#"` | branché (href="#" neutralisé par preventDefault) |
| ResetPasswordPage | "Valider et me connecter" | (submit, form `onSubmit={submit}`) | `submit` → `axResetPassword(token, pwd)` | POST /reset-password (bridge.js:128) | branché |
| CGU / Politique de confidentialité (liens signup) | 1766 | `<a href="/legal/...">` | navigation interne | branché |

### Onboarding (4 étapes)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| OnbStep1 | "Pré-remplir depuis mon site" | 2089 | `doPrefill` → `axPrefill(url)` | POST /prefill (bridge.js:176) | branché |
| OnbDocUpload | "Ajouter un document" | 2177 | inline `fileRef.current.click()` puis `onFile` → `axUploadDocument` | POST document (bridge.js:553) | branché |
| ChipsRow (secteur/stade/défi/marché) | chips dynamiques | 2206 | inline `onChange(o)` | met à jour l'état du formulaire (prop `onChange`) | branché |
| OnbStep3 | "Lancer cette analyse" | 2410 | inline `axPremierRapport()` puis `onLaunch(null)` | POST /analysis/premier-rapport (bridge.js:518) | branché |
| OnbStep3 | "Je préfère poser ma propre question" | 2420 | inline `onLaunch(seedQ)` | ouvre le composer pré-rempli | branché |
| OnbShell | "Retour" | 2476 | `onBack` (prop) | étape précédente | branché |
| OnbShell | "Continuer" | 2481 | `onNext` (prop) | étape suivante | branché |
| OnbStep4 | "Ajouter ma carte et commencer" | 2550 | `start` → `axSubscribe('pro', true)` puis redirection Stripe | POST /subscribe (bridge.js:164) | branché |
| OnbStep4 | "Continuer sans carte" | 2564 | `onSkip` (prop) | passe à l'app sans carte | branché |

### Shell (sidebar/topbar)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| AppShell | Bascule sidebar (rail/ouvert) | 2706 | inline `setSidebarMode(...)` | UI locale | branché |
| ToolBtn (Conversations/Rapports/Agents/Mémoire/Crédits/Documentation/Paramètres/Pilotage) | 2683 | inline `goSubRoute(id)` | change `subRoute` | branché |
| AppShell backdrop mobile | (voile) | 2692 | inline `setMobileOpen(false)` | ferme le tiroir mobile | branché |
| AppShell backdrop conv-list mobile | (voile) | 2695 | inline `setConvListOpen(false)` | ferme le tiroir conversation mobile | branché |
| AppShell | "Se déconnecter" | 2742 | `onLogout` → `deconnecter()` (App.jsx:2620) | `axClearToken()` + reload | branché |
| AppShell topbar | hamburger mobile | 2754 | inline `setMobileOpen(true)` | ouvre tiroir | branché |
| AppShell topbar | hamburger conv-list mobile | 2768 | inline `setConvListOpen(!convListOpen)` | ouvre/ferme tiroir conv | branché |
| Topbar | chip crédits | 9911 | inline `setSubRoute('credits')` | navigation | branché |
| Topbar | icône réglages | 9914 | inline `setSubRoute('settings')` | navigation | branché |
| TopControls (répété sur chaque surface) | FR/EN | 4537-4538 | inline `window.setAxialLang(...)` | change langue | branché |
| TopControls | bascule thème clair/sombre | 4542 | inline `setTheme(...)` | UI locale (localStorage) | branché |

### Modales génériques

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| ModaleCredits | "Acheter des crédits" | 2911 | `onCredits` (prop) | navigue vers Crédits | branché |
| ModaleCredits | "Voir les abonnements" | 2914 | `onCredits` (prop) | navigue vers Crédits | branché |
| ModaleCredits | "Fermer" | 2917 | `onClose` (prop) | ferme modale | branché |
| CarteErreur (fil de conversation) | action contextuelle (crédits/reconnexion/réessayer/rouvrir) | 2942 | `onAction` (prop) | rejoue l'action ou reconnecte | branché |
| ModaleConfirmation | "Supprimer" | 2966 | `onConfirmer` (prop) → `confirmerSuppression` | `axSupprimerConversation`/`axSupprimerRapport`/`axSupprimerProjet` selon le contexte | branché |
| ModaleConfirmation | "Annuler" | 2969 | `onAnnuler` (prop) | ferme modale | branché |

### Menu ⋯ conversations / dossiers (MenuConversation)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| MenuConversation | déclencheur ⋯ | 3087 | inline `onBasculer()` | ouvre/ferme le menu | branché |
| MenuConversation | entrée avec sous-menu ("Déplacer vers…") | 3095 | inline bascule `sousOuvert` | déplie l'accordéon | branché |
| MenuConversation | item de sous-menu (ex. un dossier cible) | 3106 | inline `s.onClick()` | `axDeplacerConversation`/`axDeplacerRapport` | branché |
| MenuConversation | item simple (Renommer/Épingler/Archiver/Supprimer) | 3119 | inline `a.onClick()` | voir tableau `actionsConversation`/`actions(r)` ci-dessous | branché |
| ConvListPanel — action "Renommer" | conv.menu.renommer | 3298 | `ouvrirRenommage('conv', c.id, ...)` | ouvre champ inline puis `axRenommerConversation` au blur/Enter | branché |
| ConvListPanel — action "Épingler/Désépingler" | conv.menu.epingler | 3301 | `onEpingler(c.id, !c.pinnedAt)` → `axEpinglerConversation` | PATCH pin | branché |
| ConvListPanel — action "Archiver/Désarchiver" | conv.menu.archiver | 3304 | `onArchiver(c.id, !c.archivedAt)` → `axArchiverConversation` | PATCH archive | branché |
| ConvListPanel — action "Déplacer" (sous-menu) | conv.menu.deplacer | 3309 | `onDeplacer(c.id, p.id)` → `axDeplacerConversation` | PATCH project_id | branché |
| ConvListPanel — action "Supprimer" | common.delete | 3312 | `onSupprimer(c)` → ouvre `ModaleConfirmation` → `axSupprimerConversation` | DELETE conversation | branché |
| DossierGroupe | bascule repli dossier | 3140 | `onBasculer` (prop) | replie/déplie (persisté localStorage) | branché |
| ConvListPanel | ligne conversation | 3327 | inline `choisir(c.id)` | sélectionne le fil | branché |
| ConvListPanel | "Fermer" (bandeau erreur liste) | 3359 | `onFermerErreur` (prop) | masque le bandeau | branché |
| ConvListPanel | "Nouvelle analyse" | 3365 | inline `nouveau()` → `onNew` (prop) | crée un fil | branché |
| ConvListPanel | "Nouveau dossier" | 3370 | `ouvrirNouveauDossier` | ouvre champ inline → `onCreerDossier` → `axCreerProjet` | branché |
| ConvListPanel | ligne résultat de recherche | 3401 | inline `choisir(r.conversation_id, r)` | ouvre le fil trouvé | branché |
| ConvListPanel (dossiers) — "Renommer" | 3454 | `ouvrirRenommage('dossier', p.id, ...)` → `axRenommerProjet` | branché |
| ConvListPanel (dossiers) — "Archiver" | 3456 | `onArchiverDossier(p.id, true)` → `axArchiverProjet` | branché |
| ConvListPanel (dossiers) — "Supprimer" | 3458 | `onSupprimerDossier(p)` → `axSupprimerProjet` | branché |
| ConvListPanel — "Désarchiver" (ligne dossier archivé) | 3501 | `onArchiverDossier(p.id, false)` → `axArchiverProjet` | branché |

### Fil de conversation (Composer + bulles)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| EmptyConvState | "Réessayer" (erreur de création) | 3569 | `onRetryCreation` (prop) | relance création + envoi | branché |
| EmptyConvState | prompt-chip suggéré | 3576 | inline `onSend(p)` | envoie la suggestion | branché |
| BoutonCopier | "Copier" | 3628 | `copier` → `copierDansPressePapier(texte)` | copie presse-papiers | branché |
| ConvThread head | "Exporter en Markdown" | 3731 | inline `exporter('md')` → `axExporterConversation` | GET export (bridge.js:521) | branché |
| ConvThread head | "Exporter en PDF" | 3735 | inline `exporter('pdf')` → `axExporterConversation` | idem | branché |
| ConvThread | "Charger les précédents" | 3754 | `chargerPrecedents` → `onChargerPrecedents` (prop) → `axMessagesPage` | pagination historique | branché |
| ConvThread | bouton "aller en bas" | 3796 | `allerEnBas` | scroll local | branché |
| UserMsg (édition) | "Renvoyer" | 3840 | inline `onEditer(propre)` → `onEditerMessage` → `axEditerMessage` (App.jsx:9796) | SSE édition + relance | branché |
| UserMsg (édition) | "Annuler" | 3847 | inline `setEdition(null)` | ferme l'édition | branché |
| UserMsg | crayon "Éditer" | 3860 | inline `setEdition(...)` | ouvre le textarea d'édition | branché |
| AiMsg | "Régénérer" | 3998 | `onRegenerer` (prop) → `axRegenerer` (App.jsx:9748) | SSE régénération | branché |
| Composer | lien "Compléter mon profil" (bandeau profil vide) | 4114 | `onCompleterProfil` (prop) | navigue vers Mémoire | branché |
| Composer | bouton trombone (joindre document) | 4120 | inline `fileRef.current.click()` → `onPickFile` → upload | branché |
| Composer | Stop (pendant un flux) | 4138 | `onStop` (prop) | annule le flux SSE | branché |
| Composer | Envoyer | 4143 | `onSend` (prop) | envoie le message | branché |
| Composer | retirer un document en attente | 4161 | inline `removePending(d.id)` | retire de la liste locale | branché |
| Composer | chip mode agent (auto/spécialisé) | 4177 | inline `pickMode(m.key)` | change le mode d'agent du composer | branché |
| CitationPanel | fermeture (backdrop + croix) | 4486, 4490 | `onClose` (prop) | ferme le panneau | branché |
| Citation inline `[n]` dans une réponse | 5427 | `onCite(n.n)` (prop) | ouvre `CitationPanel` sur la source n | branché |

### Pilotage (admin)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| ComptesAdmin | "+ crédits" | 4275 | `geste(l, 'credits')` → `window.prompt` puis `axCrediterCompte` | POST crédit (bridge.js:510) | branché |
| ComptesAdmin | "+ essai" | 4277 | `geste(l, 'essai')` → `window.prompt` puis `axProlongerEssai` | POST prolongation (bridge.js:513) | branché |
| PilotageSurface | onglets "Chiffres"/"Comptes" | 4336, 4338 | inline `setVue(...)` | bascule vue | branché |
| PilotageSurface | filtre 7/30/90 jours | 4341 | inline `setJours(n)` → `axMetrics(jours)` | GET /metrics/tableau | branché |

### Rapports — liste, génération, édition

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| ReportsList — menu ⋯ "Renommer" | 4689 | `ouvrirRenommage(r)` → `axRenommerRapport` | branché |
| ReportsList — "Épingler/Désépingler" | 4692 | `gestion.epingler(r.id, !r.pinned_at)` → `axEpinglerRapport` | branché |
| ReportsList — "Archiver/Désarchiver" | 4695 | `gestion.archiver(r.id, !r.archived_at)` → `axArchiverRapport` | branché |
| ReportsList — "Retirer du dossier" | 4705 | `gestion.deplacer(r.id, null)` → `axDeplacerRapport` | branché |
| ReportsList — "Déplacer vers [dossier]" | 4709 | `gestion.deplacer(r.id, p.id)` → `axDeplacerRapport` | branché |
| ReportsList — "Comparer avec…" | 4716 | `gestion.comparer(r)` | ouvre le mode comparaison | branché |
| ReportsList — "Supprimer" | 4719 | `gestion.demanderSuppression(r)` → `axSupprimerRapport` | branché |
| ReportsList | ligne rapport | 4749 | inline `onOuvrir(r)` | ouvre l'éditeur/écran de suivi | branché |
| ReportsList | "Annuler la comparaison" | 4797 | `gestion.annulerComparaison` | quitte le mode comparaison | branché |
| ReportsList | "Fermer" (bandeau erreur) | 4810 | `onFermerErreur` (prop) | masque le bandeau | branché |
| ReportsList | ligne résultat recherche | 4836 | inline `onOuvrir(r)` | ouvre le rapport trouvé | branché |
| ReportsList | "Charger plus" | 4900 | `gestion.chargerPlus` → `axRapports({before})` | pagination | branché |
| ReportsEmpty | tuile type de rapport | 4974 | inline `setType(tp.id)` | change le type sélectionné | branché |
| ReportsEmpty | "Lancer l'analyse" | 4998 | inline `onStart({...})` → `axLancerRapport` (App.jsx, via `startReport`) | POST /reports (SSE) | branché |
| ReportsEmpty | chip de template de prompt | 5010 | inline `setPrompt(s)` | pré-remplit le textarea | branché |
| ReportsGenerating | "Relancer" | 5146 | `onRelancer` (prop) → `axRelancerRapport` | branché |
| ReportsGenerating | "Signaler un problème" | 5151 | `onSignaler` (prop) | ouvre `ModaleSignalement` | branché |
| ReportsGenerating | "Retour" | 5155 | `onRetour` (prop) | quitte l'écran de suivi | branché |
| ReportsGenerating | "Stop" | 5209 | `onStop` (prop) → `axAnnulerRapport` | annule le rapport en cours | branché |
| ReportsSourcesInsuffisantes | "Reformuler" | 5252 | `onReformuler` (prop) | retour au composer avec la question | branché |
| ReportsSourcesInsuffisantes | "Chercher plus large" | 5256 | `onElargir` (prop) → relance avec `elargir: true` | branché |
| ReportsSourcesInsuffisantes | "Générer quand même" | 5260 | `onForcer` (prop) → relance avec `forcer: true` | branché |
| ReportsSourcesInsuffisantes | "Retour" | 5263 | `onRetour` (prop) | branché |
| ModaleSignalement | note 1-5 | 5369 | inline `setNote(...)` | sélection locale | branché |
| ModaleSignalement | "Envoyer" | 5394 | `envoyer` → `axSignalerRapport` | POST /reports/{id}/signaler | branché |
| ModaleSignalement | "Fermer" | 5398 | `onFerme` (prop) | ferme modale | branché |
| PanneauPartage | "Créer le lien"/"Copier" | 5777 | `creer(...)` → `axPartagerRapport` | POST /reports/{id}/partage | branché |
| PanneauPartage | "Copier" (lien déjà créé) | 5784 | `copier` → `copierDansPressePapier` | copie le lien | branché |
| PanneauPartage | "Révoquer" | 5790 | `revoquer` → `axRevoquerPartage` | DELETE partage | branché |
| ReportsEditor | "Retour" | 5901 | `onBack` (prop) | branché |
| ReportsEditor — menu export | PDF/MD/DOCX | 5914-5918 | `exporter(format)` → `axExporterRapport` | GET export (bridge.js:778) | branché |
| ReportsEditor — menu "Livrer" | Notion | 5930 | `livrer('notion')` → `axDeliverReport('notion', id)` | POST /integrations/notion/deliver | branché |
| ReportsEditor — menu "Livrer" | Google Drive | 5933 | `livrer('google')` → `axDeliverReport('google', id)` | POST /integrations/google/deliver | branché |
| ReportsEditor | "Partager" (ouvre PanneauPartage) | 5939 | inline `setPartageOuvert(...)` | UI locale | branché |
| ReportsEditor | "Régénérer" | 5945 | `onRegenerer` (prop) | relance génération identique | branché |
| ReportsEditor | "Modifier et relancer" | 5951 | `onModifierRelancer` (prop) | retour au composer avec options | branché |
| ReportsEditor | "Donnez votre avis"/"Signaler" | 5960 | inline `setSignalement(true)` | ouvre `ModaleSignalement` | branché |
| ReportsCompare | "Quitter la comparaison" | 6090 | `onSortir` (prop) | ferme le mode comparaison | branché |
| Erreur rapport (écran) | "Retour" | 10046 | inline `setErreurRapport(null); setReportsState('empty')` | ferme l'écran d'erreur | branché |

### Agents / veilles

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| FeedsManager | "Fermer" | 6191 | `onClose` (prop) | branché |
| FeedsManager | tuile source du catalogue | 6219 | `ajouterDuCatalogue(f)` → `axAddFeed` | POST /watches/feeds | branché |
| FeedsManager | "Ajouter" (URL libre) | 6240 | `add` → `axAddFeed` | idem | branché |
| FeedsManager | supprimer un flux | 6253 | `del(f.id)` → `axDeleteFeed` | DELETE /watches/feeds/{id} | branché |
| ActivityHistory | "Fermer" | 6273 | `onClose` (prop) | branché |
| AgentsLibrary | "Historique" | 6333 | inline `setShowHistory(true)` | ouvre `ActivityHistory` (→ `axWatchActivity`) | branché |
| AgentsLibrary | "Sources RSS" | 6336 | inline `setShowFeeds(true)` | ouvre `FeedsManager` | branché |
| AgentsLibrary | "Créer un agent" (bouton + carte) | 6339, 6350 | `onCreate` (prop) | ouvre `AgentWizard` | branché |
| AgentsLibrary | carte agent | 6372 | inline `onOpenSession(a)` | ouvre `AgentSession` | branché |
| AgentWizard | "Fermer" | 6439 | `onClose` (prop) | branché |
| AgentWizard | tuile skill | 6482 | inline `setSkill(c.id)` | sélection locale | branché |
| AgentWizard | tuile output | 6526 | inline `setOutput(c.id)` | sélection locale | branché |
| AgentWizard | tuile cadence | 6556 | inline `setCadence(c.id)` | sélection locale | branché |
| AgentWizard | "Retour"/"Annuler" | 6569 | inline `step === 0 ? onClose() : setStep(step - 1)` | navigation wizard | branché |
| AgentWizard | "Continuer"/"Créer l'agent" | 6573 | inline → `onCreate({...})` → `axCreateWatch` | POST /watches | branché |
| AgentSession | "Retour" | 6622 | `onBack` (prop) | branché |
| AgentSession | "Lancer maintenant" | 6638 | `runNow` → `axRunWatch(agent.id)` | POST /watches/{id}/run | branché |
| AgentSession | "Pause"/"Reprendre" | 6642 | `toggle` → `axPauseWatch`/`axResumeWatch` | POST pause/resume | branché |
| AgentSession | ligne timeline (run) | 6664 | inline `setOpenRunId(r.id)` | affiche le détail du run | branché |

### Mémoire / documents

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| DocumentsPanel | "Ajouter" | 6754 | inline `fileRef.current.click()` → `onFile` → `axUploadDocument` | branché |
| DocumentsPanel | "Réindexer" | 6775 | `reindexer(d.id)` → `axReindexerDocument` | POST réindexation | branché |
| DocumentsPanel | supprimer document | 6783 | `del(d.id)` → `axDeleteDocument` | DELETE document | branché |
| MemorySurface | "Enregistrer" (profil) | 6858 | `save` → `axSaveProfile` | PATCH profil | branché |

### Crédits / abonnement

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| CreditsSurface | "Gérer l'abonnement" | 6977 | `openPortal` → `axPortal` | redirige vers portail Stripe | branché |
| CreditsSurface | "S'abonner" (plan payant) | 7004 | inline `subscribe(p.key)` → `axSubscribe` | checkout Stripe | branché |
| CreditsSurface | "Acheter" (pack ponctuel) | 7021 | inline `buy(p.key)` → `axCheckout` | checkout Stripe | branché |
| CreditsSurface (Enterprise) | "Nous contacter" | (ligne 7007 zone) | `<a href="mailto:sales@axial-ia.fr">` | branché |

### Paramètres

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| SettingsSurface | onglets (Compte/Notifications/Apparence/Connexions/Facturation) | 7075 | inline `setTab(i.id)` | navigation interne | branché |
| Notifications | toggle (findings/weekly/marketing) | 7098 | inline `setNotif({...})` → `axSetNotifPrefs` | PATCH préférences (persistance silencieuse) | branché |
| Apparence | Sombre/Clair | 7113-7114 | inline `setTheme(...)` | UI locale | branché |
| IntegrationsSettings | "Déconnecter" (Notion/Google) | 7293 | `deconnecter(o.id)` → `axDisconnectIntegration` | POST déconnexion | branché |
| IntegrationsSettings | "Connecter" (Notion/Google) | 7298 | `connecter(o.id)` → `axConnectIntegration` | démarre le flux OAuth | branché |
| BillingSettings | "Gérer" (portail Stripe) | 7358 | inline → `axPortal` | redirige vers portail Stripe | branché |

### Documentation

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| DocsSurface | item sommaire (use-cases/prompts/agents/memory/credits) | 7444 | inline `setTopic(tp.id)` | navigation interne | branché |
| DocsSurface | lien "support@axial.intelligence" (FR) | 7458 | `<a href="#">`, pas de handler | ne fait rien au clic | **href="#"** (pas de `mailto:`) — et adresse **douteuse** (domaine différent de `sales@axial-ia.fr` utilisé ailleurs) |
| DocsSurface | lien "support@axial.intelligence" (EN) | 7459 | `<a href="#">`, pas de handler | idem | **href="#"** + **douteux** |
| DocsPrompts | "Copier" (un template de prompt) | 7745 | inline `navigator.clipboard?.writeText(...)` | copie le prompt, feedback texte temporaire | branché |

### Éléments recensés mais non cliqués (dictionnaire i18n orphelin)

| Élément | Ligne | Constat | Verdict |
|---|---|---|---|
| "Continuer avec Google" / "Se connecter avec Google" / "Connexion Google bientôt disponible — utilisez votre email professionnel." | 1959-1962 | Trois clés de traduction définies mais **jamais référencées** dans le JSX de `AuthPage` — aucun bouton Google Sign-in n'existe dans le rendu actuel. | code mort (pas un élément cliquable actif — signalé pour information, mention explicite « bientôt ») |

### Page publique de rapport partagé (`frontend/app/p/[pseudo]/[slug]/page.tsx`)

| Écran | Libellé | Ligne | Handler | Action | Verdict |
|---|---|---|---|---|---|
| En-tête | lien marque (retour à l'app) | 289 | `<a href={APP}>` | navigation vers l'app | branché |
| Corps du rapport | liens `[n]` vers les sources | 135 | `<a href="#rp-src-{n}">` | ancre interne vers la liste des sources | branché |
| Corps du rapport | liens externes (markdown) | 127 | `<a href={n.href} target="_blank" rel="nofollow noopener noreferrer">` | ouvre la source dans un nouvel onglet | branché |
| Liste des sources | lien source | 309 | `<a href={s.url} target="_blank" rel="nofollow noopener noreferrer">` | idem | branché |
| Pied de page | lien marque | 322 | `<a href={APP}>` | navigation vers l'app | branché |

---

## Vérifications complémentaires effectuées

- **Correspondance `axXxx` ↔ `bridge.js`** : script `comm` entre la liste des `axXxx(` appelés dans `App.jsx` et la liste des `export (async )?function axXxx` de `bridge.js` → **aucune fonction manquante**.
- **Recherche de placeholders** : `console.log`, `alert(`, `TODO`, "prochainement", "bientôt" → seules occurrences : les deux `window.alert(...)` volontaires de `ComptesAdmin` (gestion d'erreur, pas un placeholder) et la chaîne i18n orpheline "bientôt disponible" pour Google Sign-in (non rendue).
- **`disabled` en dur** : aucun bouton n'a un `disabled` non conditionnel en production — tous les `disabled` rencontrés dépendent d'un état (`busy`, `!value.trim()`, `isCurrent`, `occupe`, etc.).
- **`onClick={() => {}}` vide** : aucune occurrence.
