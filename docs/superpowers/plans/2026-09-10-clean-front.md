# Clean front + registre — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une app cohérente (vouvoiement partout dans l'app, tutoiement dans les emails), les six observations front de Miradie appliquées, le code mort du prototype retiré et les manques comblés — sans aucune régression.

**Architecture:** Aucune refonte. Le monolithe `App.jsx` reste un fichier ; on retire, on corrige, on factorise trois classes CSS. Backend : textes des erreurs et consigne de registre dans les prompts. Chaque tâche se termine par `npm run build` (front) et/ou `pytest` + `ruff` (backend) verts.

**Tech Stack:** React 18 / Next 14 (App.jsx, globals.css, bridge.js), FastAPI, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-10-audit-front-et-registre.md` (constat chiffré, numéros de ligne) — à lire avant chaque tâche ; les lignes y sont celles du 10/09 au soir et peuvent glisser de quelques unités après les premières tâches : chercher par le texte cité, pas par le numéro seul.

## Global Constraints

- **Registre** : dans l'app (UI, erreurs backend, réponses dégradées, contenu généré par le modèle) → **vouvoiement** ; dans les emails envoyés par Miradie (cycle de vie, réinitialisation, rapport prêt, campagnes, veille) → **tutoiement**. Les prompts fixent le registre du contenu généré.
- **Zéro régression** : `cd frontend && npm run build` doit afficher `✓ Compiled successfully` à la fin de chaque tâche front ; `.venv/bin/pytest tests/ -q` et `.venv/bin/ruff check app tests` verts à la fin de chaque tâche backend. Ne jamais commiter sur un build rouge.
- **Ne rien inventer** : pas de nouveau composant hors de ce plan, pas de nouvelle dépendance, pas de réécriture de sections qui ne sont pas citées.
- **i18n** : tout nouveau texte visible passe par `t('clé')` (dictionnaires `STRINGS.fr` / `STRINGS.en` dans App.jsx) ou `libelle('FR')` + entrée dans `LABELS_EN`. Aucun texte FR nu dans le JSX.
- **Pas de push, pas de déploiement** par les implémenteurs : commits locaux sur la branche courante uniquement.
- Le fichier `public/proto/index.html` (prototype d'origine) n'est plus servi : il peut être supprimé avec ses libs, mais **pas les polices** `public/proto/fonts/` (référencées par `globals.css`).

---

### Task 1: Registre backend — erreurs, réponses dégradées, prompts

**Files:**
- Modify: tous les fichiers de `app/` contenant des `AppError(...)` ou des messages utilisateur au tutoiement (liste dans la spec § C : `auth/service.py`, `auth/local.py`, `auth/password_reset.py` (les **messages d'erreur HTTP** seulement — pas les corps d'emails), `memory/service.py`, `integrations/delivery.py`, `intelligence/service.py`, `analysis/service.py`, `emailing/router.py` (page de désinscription : c'est une page web → vouvoiement), et tout autre `AppError` trouvé par grep).
- Modify: `app/modules/watches/email.py` (signature « Envoyé par votre agent de veille Axial. » → « Envoyé par ton agent de veille Axial. » : c'est un email).
- Modify: `app/modules/analysis/prompts.py` (`OUTPUT_STYLE`, nouvelle règle 8), `app/modules/intelligence/personas.py` (nouvelle constante `REGISTRE_INSTRUCTION` ajoutée à `full_system_prompt()` ET au chemin conversation libre de `intelligence/service.py` — même mécanique que `VIZ_INSTRUCTION`).
- Create: `tests/test_registre.py`

**Interfaces:**
- Produces: `personas.REGISTRE_INSTRUCTION` (str) ; règle 8 dans `prompts.OUTPUT_STYLE`.

- [ ] **Step 1: Test qui échoue** — `tests/test_registre.py` : parcourt `app/**/*.py` SAUF `app/modules/emailing/sequences.py`, `app/modules/reports/notification.py`, les fonctions d'email de `app/modules/auth/password_reset.py` (tout ce qui est dans `_gabarit`/corps d'email — pour rester simple : exclure le fichier entier et vérifier ses `AppError` par un test ciblé listant leurs messages), `app/modules/watches/email.py` ; pour chaque chaîne littérale française (`"` ou `'`) d'une ligne contenant `AppError(` ou d'une des 7 réponses dégradées (chercher `"⚠️` et `Réessai`), échoue si elle matche `\b(tu|te|toi|ton|ta|tes)\b|-toi\b|\bréessaie\b|\breconnecte-toi\b|\bremplis\b|\bvérifie\b|\bredemande\b` (insensible à la casse). Un second test vérifie `"vouvoie" in prompts.OUTPUT_STYLE` et `"vouvoie" in personas.REGISTRE_INSTRUCTION` et que `personas.MARKET_SCANNER.full_system_prompt()` contient `REGISTRE_INSTRUCTION`.

- [ ] **Step 2: Passer les ~36 chaînes au vouvoiement** (exemples exacts → cibles) : « Session expirée — reconnecte-toi. » → « Session expirée — reconnectez-vous. » ; « Site injoignable — remplis les champs à la main. » → « …remplissez les champs à la main. » ; « Ce lien a expiré. Redemande-en un. » → « …Redemandez-en un. » ; « Notion a refusé la connexion. Reconnecte l'outil. » → « …Reconnectez l'outil. » ; « Merci d'utiliser ton email professionnel. » → « …votre email professionnel. » ; « ⚠️ La génération a échoué. Réessaie dans un instant. » → « …Réessayez dans un instant. » ; « Aucun moteur … Réessaie plus tard. » → « …Réessayez plus tard. » ; « ⚠️ La réponse n'a pas abouti. Repose ta question — aucun crédit n'a été débité. » → « …Reposez votre question — … » ; page de désinscription « Ce lien n'est plus valide. Réponds à l'email et je te retire à la main. » → « …Répondez à l'email et nous vous retirerons à la main. ». Grep exhaustif : `grep -rnE "\b(tu|te|toi|ton|ta|tes)\b|-toi\b" app/ --include=*.py` puis trier ce qui est UI/erreur (à changer) et ce qui est email (à garder).

- [ ] **Step 3: Prompts** — règle 8 dans `OUTPUT_STYLE` : « 8. Registre : le rapport s'adresse au lecteur en le VOUVOYANT (« votre marché », « vous pouvez »), jamais de tutoiement. En anglais, registre professionnel neutre. » ; `REGISTRE_INSTRUCTION` (personas) : « \n\nREGISTRE : vouvoie toujours l'utilisateur (« vous », « votre ») — jamais « tu ». Ton professionnel et direct. » ajoutée à `full_system_prompt()` et au chemin libre (`system = persona.system_prompt + personas.VIZ_INSTRUCTION + personas.REGISTRE_INSTRUCTION`).

- [ ] **Step 4: Tests + lint + commit** — `git commit -m "Registre : l'app vouvoie (erreurs, réponses dégradées, prompts), les emails tutoient"`.

---

### Task 2: Code mort et contraintes de prototype (App.jsx)

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`
- Delete: `frontend/public/proto/libs/` (react, react-dom, babel), `frontend/public/proto/index.html`, `frontend/prototype/` (sources extraites) — après avoir vérifié par grep qu'aucun code n'y fait référence (les polices `public/proto/fonts/` restent).

- [ ] **Step 1: Supprimer** (spec § B) : les 8 fixtures jamais lues (`REPORT_OUTLINE`, `REPORT_SOURCES`, `REPORT_ACTIVITY`, `AGENT_TIMELINE`, `AGENT_FINDINGS`, `MEMORY_FACTS`, `SETTINGS_MEMBERS`, `SETTINGS_CONNECTIONS`) et l'export `window.AXIAL_SURFACES` qui ne servait qu'à elles ; `makeFakeAiResponse()` ; `TweaksPanel` et son rendu dans l'app connectée ; les composants uniquement atteignables par ce panneau : `SourceConflictModal`, `ShareModal`, `RecipientView` et la route `'recipient'`, ainsi que les états `showConflict`, `showShare`, `showWizard` s'ils ne servent plus qu'à eux (vérifier `showWizard` : s'il ouvre le wizard d'agent depuis un vrai bouton, le garder) ; la prop `openShare` de `ReportsEditor` et son passage ; le `<select>` « Densité » sans effet dans Paramètres ; le stub `const ReactDOM = …` et l'appel `ReactDOM.createRoot(...).render(<App />)` en fin de fichier ; les alias `useStateS`, `useStateM`, `useConvState`, `useConvEffect` remplacés par `React.useState` / `React.useEffect` (ou par un seul `const { useState, useEffect } = React;` en tête si le fichier n'en a pas déjà un — vérifier les collisions `var {…} = React` héritées du prototype : les unifier en une seule déclaration en tête de fichier).
- **Garder** `ReportsQuota` (Task 4 le branche). Garder `AgentWizard`.
- [ ] **Step 2: Vérifier** : `grep -n "AXIAL_SURFACES\|makeFakeAiResponse\|TweaksPanel\|ShareModal\|RecipientView\|SourceConflictModal\|openShare\|useStateS\|useStateM\|useConvState" App.jsx` → 0 ligne. `npm run build` vert. Ouvrir mentalement chaque site d'appel supprimé : aucun identifiant orphelin (le build Next ne détecte PAS les identifiants non définis — faire `grep -n "<NomSupprimé"` pour chaque composant retiré).
- [ ] **Step 3: Commit** — `"Front : code mort du prototype retiré (fixtures inventées, fausse réponse IA, panneau de réglages, écrans orphelins)"`.

---

### Task 3: Registre front — vouvoiement dans App.jsx

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`

- [ ] **Step 1:** Passer au vouvoiement toutes les chaînes FR tutoyantes de la spec § C (≈ 25 lignes : écran carte l. ~2170-2219, Documents « Tes documents », Mémoire « ton entreprise », Auth « Renseigne d'abord ton email », « Vérifie ta boîte », placeholder `ton@email.com` → `vous@entreprise.com`, Reset « Choisis un nouveau mot de passe », « Tu seras connecté », « Retape le même », Onboarding 3 « aucun de tes crédits. Tu reçois un email », Rapports « Déposé dans ton Drive », Agents « les runs de tes agents », Crédits « Ton solde, ton abonnement », « vérifie la config Stripe », Paramètres « ton espace », « Connecte tes outils », `LABELS_EN` : conserver les clés FR modifiées en cohérence). La chaîne de l'écran carte « …ou réponds à un de mes emails si tu as besoin de plus de temps » devient « …ou répondez à l'un de nos emails si vous avez besoin de plus de temps. ».
- [ ] **Step 2: Vérifier** : `grep -nE "\b(tu|te|toi|ton|ta|tes)\b|-toi\b" App.jsx` ne renvoie plus que des chaînes **anglaises** ou du code (ex. `t(`, `.te`) — lister les faux positifs dans le rapport. Attention : ne pas toucher « Continue », « Active », « Partage » côté valeurs EN. `npm run build` vert.
- [ ] **Step 3: Commit** — `"Front : l'app vouvoie partout"`.

---

### Task 4: Les quatre petits points + solde avant génération

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`, `frontend/app/globals.css`
- Create: `frontend/public/logos/notion.svg`, `frontend/public/logos/google-drive.svg` (monochromes, simples, ≤ 2 Ko ; pas de reproduction de logo protégé au pixel près — une lettre « N » dans un carré arrondi et un triangle à trois branches stylisé suffisent ; le rapport signale que des assets officiels devront être validés par Miradie)

- [ ] **Step 1 (obs. 1)** : retirer le bloc « RÉCENTS » de la barre latérale (`sidebar-recents`) et les props `conversations`, `activeId`, `onPickConv` de `AppShell` + point d'appel. Le panneau `ConvListPanel` reste la seule liste.
- [ ] **Step 2 (obs. 6)** : `user-row` redevient un bloc d'identité inerte (retirer `onClick`, `role`, `tabIndex`, `onKeyDown`, `cursor`) ; ajouter dessous un `<button className="btn btn-ghost" style={{ width: '100%' }}>` avec `<Icon name="logout" size={14} />` + `t('nav.logout')` (FR « Se déconnecter », EN « Sign out ») ; CSS `.user-name, .user-email { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }` + `title={user.email}` ; `.user-row:focus-visible` retiré (plus focusable).
- [ ] **Step 3 (obs. 4)** : `CreditsSurface` : garde `{sub && sub.active && (…)}` → `{sub && (…)}` avec, dans la carte, trois cas : abonnement actif (rendu actuel), essai / annulé / impayé (statut coloré `SUB_STATUS` + date de fin), aucun abonnement (« Aucun abonnement — essai jusqu'au <date> » en utilisant `bal` : si `bal.trial_credits > 0` afficher l'essai). Badge « Plan actuel » (`t('credits.current')`) sur la carte du plan souscrit et bouton « S'abonner » désactivé sur celle-ci. Extraire la carte dans une classe `.sub-card` (globals.css) et l'utiliser aussi dans `BillingSettings` avec le même `fmtDate` (une seule fonction, définie une fois au niveau module).
- [ ] **Step 4 (obs. 5)** : `OUTILS` gagne `logo: '/logos/notion.svg'` ; rendu `<span className="icon-tile"><img src={o.logo} alt="" width="20" height="20" /></span>` avec repli `<Icon>` si `logo` absent ; Google Drive reste commenté mais son entrée porte déjà `logo: '/logos/google-drive.svg'`.
- [ ] **Step 5 (comblement)** : `startReport` vérifie le solde avant de lancer : coût = `REPORT_TYPES[type].cost` ; si `axBal != null && axBal < cost` → `setReportsState('quota')` et `ReportsQuota` reçoit `{ needed: cost, available: axBal }` (adapter ses props à ce qu'il affiche déjà) ; sinon génération comme avant. `ReportsQuota` doit avoir un bouton « Voir les crédits » (route `credits`) et « Retour ».
- [ ] **Step 6** : `npm run build` vert ; grep des identifiants retirés ; commit `"Front : historique unique, bouton de déconnexion, carte abonnement toujours visible, logos des connexions, solde vérifié avant génération"`.

---

### Task 5: Types de rapports harmonisés + classes communes

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`, `frontend/app/globals.css`

- [ ] **Step 1** : `.rep-types { grid-template-columns: repeat(3, 1fr) }` (desktop), `repeat(2, 1fr)` < 960 px, `1fr` < 600 px. Descriptions FR/EN réécrites, toutes en **liste nominale de 40 à 60 caractères**, sans verbe conjugué ni marque : market « TAM/SAM/SOM, segments, dynamiques de croissance » ; competitive « Positionnement, parts, forces structurelles » ; regulatory « Cadres légaux, calendriers, obligations en vigueur » ; risks « Risques opérationnels, marché, réglementaires » ; investors « Fonds et réseaux adaptés à votre secteur et votre stade » ; custom « Question ouverte, cadrage libre, sources citées ». Titres : « Étude de marché », « Cartographie concurrentielle », « Veille réglementaire », « Analyse de risques », « Cartographie investisseurs » (sans article), « Étude personnalisée ». Icône de `custom` : `edit` (ou toute icône existante autre que `sparkle` — vérifier la liste des icônes disponibles dans le composant `Icon`).
- [ ] **Step 2** : afficher le coût sur chaque tuile : ligne mono « 40 crédits » (`t('reports.credits')` : FR « crédits », EN « credits ») en bas de tuile ; `min-height` retiré au profit de `display: flex; flex-direction: column;` avec le coût poussé en bas (`margin-top: auto`).
- [ ] **Step 3** : en-tête de `ReportsEditor` aligné sur `ReportsEmpty` : utiliser `.surface-head` avec `h1` standard et le sous-titre mono ; `TopControls` (FR/EN + thème) sort de la barre d'actions du document et se place à droite de `.surface-head` comme dans `ReportsEmpty` ; « Votre avis » passe par `t('reports.feedback')` (FR « Votre avis », EN « Your feedback »).
- [ ] **Step 4** : trois classes dans `globals.css` : `.section-label` (le bloc mono répété 8 fois : `font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); letter-spacing: .10em; text-transform: uppercase; margin-bottom: 12px;`), `.sub-card` (Task 4), `.editor-head` ; remplacer les 8 blocs inline par `className="section-label"`.
- [ ] **Step 5** : build vert ; commit `"Front : tuiles de rapports harmonisées (grille 3×2, coût affiché, textes alignés), en-tête d'éditeur unifié, classes communes"`.

---

### Task 6: Barre latérale repliable (desktop + mobile)

**Files:**
- Modify: `frontend/app/_prototype/App.jsx`, `frontend/app/globals.css`

- [ ] **Step 1** : `globals.css` : `.app-shell { grid-template-columns: var(--sidebar-w, 240px) 1fr; }` ; `html[data-sidebar="rail"] { --sidebar-w: 60px; }` ; en mode rail : `.sidebar .lockup-text, .sidebar .nav-item span.label, .sidebar .user-meta, .sidebar .sidebar-newconv .label { display: none; }`, icônes centrées, `title` sur chaque `ToolBtn` (déjà le libellé) ; transition 160 ms sur la largeur.
- [ ] **Step 2** : hook `useSidebar()` sur le modèle de `window.useTheme()` : état `'open' | 'rail'`, persistance `localStorage` clé `axial_sidebar`, application de `document.documentElement.dataset.sidebar`. Bouton de bascule dans `.sidebar-foot` au-dessus du bouton de déconnexion (icône `chevrons-left` / `chevrons-right` si elles existent dans `Icon`, sinon `menu`), `aria-label` `t('nav.collapse')` / `t('nav.expand')`.
- [ ] **Step 3 (mobile, < 768 px)** : `.app-shell { grid-template-columns: 1fr; }` ; `.sidebar { position: fixed; inset: 0 auto 0 0; width: 260px; transform: translateX(-100%); z-index: 40; }` ; `html[data-sidebar-mobile="open"] .sidebar { transform: none; }` ; voile `.sidebar-backdrop` (fixed, `rgba(0,0,0,.45)`) qui ferme au clic ; bouton hamburger (`menu`) en tête de `.topbar` visible seulement < 768 px ; toute navigation (`ToolBtn` cliqué) referme la barre en mobile.
- [ ] **Step 4** : build vert ; vérifier à 1280 px (rail ↔ ouvert) et 375 px (hamburger, voile) dans le navigateur si l'outil est disponible, sinon décrire dans le rapport ce qui a été vérifié ; commit `"Front : barre latérale repliable (rail desktop, surcouche mobile), choix mémorisé"`.

---

### Task 7: Déploiement et vérification réelle (contrôleur)

- [ ] Backend : `rsync` des fichiers modifiés, tests sur le serveur, `systemctl restart axial-backend axial-worker`.
- [ ] Front : `rsync`, `npm run build`, `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` = 0, `systemctl restart axial-frontend`.
- [ ] Parcours réel avec le compte de contrôle : connexion, écran carte (registre), Conversations (historique unique), Rapports (tuiles, coût, quota si solde insuffisant), Crédits (carte abonnement en essai), Paramètres > Connexions (logo), déconnexion par le bouton, barre latérale rail/ouvert et mobile 375 px. Une question de chat : la réponse vouvoie.
- [ ] Snapshot + push.
