# Audit front + registre (tu/vous) — état des lieux du 10/09/2026

Base : `frontend/app/_prototype/App.jsx` (6 907 lignes), `globals.css` (3 125),
`bridge.js` (485) ; backend `app/`. Lecture seule, chiffres vérifiés dans le code.

---

## A. Les six observations de Miradie, instruites une à une

| # | Observation | Ce que dit le code | Effort |
|---|---|---|---|
| 1 | Retirer l'historique de la colonne gauche | L'historique est rendu **deux fois** en même temps sur l'onglet Conversations : section « RÉCENTS » de la barre latérale (`AppShell`, l. 2316-2333) et panneau `ConvListPanel` (l. 2417-2456, plus riche : recherche + état vide). Retirer le bloc de la barre = ~20 lignes + 3 props devenues inutiles (`conversations`, `activeId`, `onPickConv`, point d'appel l. 6720-6731). Aucun CSS propre à supprimer. Bonus : élimine le conflit de classes `nav-item conv-item`. | **petit** |
| 2 | Menu gauche ouvrable / fermable | **Rien n'existe** : grille figée `240px 1fr` (`globals.css:914-918`), aucun état, aucun bouton, et les deux seules media queries ne touchent pas la barre → sur mobile, 240 px pris sur 375. Cible : variable `--sidebar-w` (240 → 56 en mode « rail d'icônes »), bouton de bascule, persistance `localStorage`, et en mobile la barre en surcouche glissante avec voile. Le mobile est la moitié du coût. | **moyen** (½ j) |
| 3 | Harmoniser les types de rapports | Six incohérences précises : grille `repeat(5, 1fr)` pour **6** tuiles (la 6ᵉ seule sur sa ligne en desktop, `globals.css:1469`) ; une description de 112 caractères contre 38-58 pour les autres (investisseurs, l. 401) qui casse l'alignement ; quatre vocabulaires de titres (Étude / Cartographie / Veille / Analyse) et un article en trop (« Cartographie **des** investisseurs ») ; `custom_desc` écrit comme une phrase méta (« Axial cadre. ») ; icône `sparkle` partagée avec deux boutons ; **coût jamais affiché sur les tuiles** (seulement après sélection). Et deux en-têtes différents pour le même parcours (`ReportsEmpty` standard vs `ReportsEditor` en styles inline, avec FR/EN + thème collés aux actions du document) ; « Votre avis » non traduit. | **moyen** (½ j) — la grille 3×2 + textes égalisés seule = petit |
| 4 | Abonnement actuel sur la page Crédits | **La carte existe déjà** (« Mon abonnement », l. 4489-4514 : plan, prix, statut, crédits/mois, prochain prélèvement, bouton portail Stripe). Elle est cachée par une garde trop stricte `sub && sub.active` : en essai, annulé ou impayé, elle disparaît — alors que les quatre libellés de statut sont prévus. Il manque aussi un état « aucun abonnement » (l'essai n'y est pas montré), un badge « plan actuel » dans la liste des offres (le plan souscrit garde son bouton « S'abonner »), et la même carte est dupliquée dans Paramètres > Facturation avec un autre format de date. | **petit** |
| 5 | Logos des connexions (Notion) | Une seule connexion visible (Notion, l. 4757), rendue avec le pictogramme générique « document » de 14 px, monochrome. Google Drive est commenté (l. 4759-4761). **Aucun logo dans `public/`** (seulement polices et libs). Il faut déposer `public/logos/notion.svg` (+ Google Drive), un champ `logo` dans `OUTILS`, un `<img>` 20-24 px sur le socle `.icon-tile`, repli sur l'icône. Une fixture morte `SETTINGS_CONNECTIONS` (5 outils de maquette) traîne l. 289-295. Droits d'usage des marques à respecter. | **petit** (les assets sont hors code) |
| 6 | Bouton déconnexion en bas | Toute la ligne utilisateur est le bouton (nom + email + icône, l. 2335-2354) : cliquer son propre nom déconnecte, sans confirmation. L'email déborde sur 2-3 lignes (`.user-email` sans `ellipsis`, `globals.css:997`), pas de `:focus-visible`, libellé « Se déconnecter » via `libelle()` donc non traduit. Cible : ligne d'identité inerte + vrai `<button>` « Se déconnecter » pleine largeur, clé `nav.logout` FR/EN, ellipsis + `title` sur l'email, variante icône seule en mode rail. | **petit** |

---

## B. Ce que l'audit a trouvé en plus (simplification)

1. **~250 lignes mortes du prototype** : 8 fixtures jamais lues (`REPORT_OUTLINE`, `REPORT_SOURCES`, `REPORT_ACTIVITY`, `AGENT_TIMELINE`, `AGENT_FINDINGS`, `MEMORY_FACTS`, `SETTINGS_MEMBERS`, `SETTINGS_CONNECTIONS`, l. 60-104 et 169-295) avec des chiffres XERFI/IDC et des emails inventés ; `makeFakeAiResponse()` (l. 6863-6903) avec une fausse citation McKinsey nommément attribuée — **à supprimer en priorité**.
2. **`TweaksPanel` (l. 6802-6857) est rendu dans l'app connectée** et reste le **seul accès** à quatre écrans : `ReportsQuota`, `SourceConflictModal`, `ShareModal`, `RecipientView` (~570 lignes). Décision produit : brancher ou supprimer.
3. **`ReportsQuota` n'est jamais déclenché par le métier** : `startReport` (l. 6464-6469) lance la génération sans vérifier le solde alors que solde et coûts sont connus → l'utilisateur découvre le manque de crédits pendant la génération.
4. `openShare` : prop morte de `ReportsEditor` (l. 3492, 6759) — le partage est câblé à moitié.
5. **425 `style={{` pour 562 `className`** ; un même bloc « label de section » copié 8 fois. Trois classes (`.section-label`, `.sub-card`, `.editor-head`) absorberaient l'essentiel.
6. Paramètres : un sélecteur « Densité » sans effet (l. 4643-4646) ; la section Connexions à un seul item.
7. Contraintes de prototype conservées : `ReactDOM` neutralisé (l. 8) et un `render` inerte (l. 6905), quatre alias de `useState`. Le fichier a des frontières commentées (`/* conversations.jsx */`, `/* app.jsx */`…) : le découper est mécanique.

---

## C. Registre : tutoiement / vouvoiement

**Constat.** L'app **vouvoie majoritairement** (≈ 85 « vous » contre ≈ 20 « tu » dans `App.jsx`), mais le vouvoiement n'est exclusif que sur trois zones (landing, documentation, onboarding 1-2). **Huit vues mélangent les deux registres** sous les yeux de l'utilisateur, par gravité :

1. Documents : « Tes documents » (l. 4327) suivi 11 lignes plus bas de « Ajoutez vos documents » (l. 4338).
2. Écran carte : « Activez votre essai. » / « votre carte » puis « Tu gardes tes 40 crédits » / « Ta période d'essai est terminée. Ajoute une carte… réponds à un de mes emails » (l. 2170-2219).
3. Mémoire : « Voici ce qu'Axial sait de vous » puis « Ce qu'Axial sait de ton entreprise » (l. 468, 4395).
4. Auth : quatre bascules dans un seul formulaire (« Créez votre espace » / `ton@email.com` / « Votre mot de passe » / « Renseigne d'abord ton email »).
5. Paramètres : l'onglet Compte vouvoie, l'onglet Connexions tutoie.
6. Onboarding 3, 7. Rapports (toast « Déposé dans ton Drive »), 8. Agents (« les runs de tes agents »).

**Le gros du problème est transversal** : les ~90 messages d'erreur du backend (`AppError`) et les 7 réponses dégradées **tutoient à 100 %** (« Session expirée — reconnecte-toi. », « Réessaie dans un instant. »), alors que l'écran qui les affiche vouvoie. Les emails, eux, respectent la règle du 22/08 (tutoiement, voix de Miradie) — sauf la signature de l'email de veille, qui vouvoie.

**Non couvert par la règle actuelle** : aucun prompt ne fixe le registre du **contenu généré** (réponses de chat, rapports, veilles). Le modèle choisit seul.

**Coût des deux bascules :**

| Cible | Chaînes | Lignes | Mécanique (regex sûre) | À réécrire à la main |
|---|---|---|---|---|
| Tout au **tutoiement** | ~84 | ~102 | possessifs, 27 impératifs, placeholders | peu : l'app seulement, le backend et les emails y sont déjà |
| Tout au **vouvoiement** | ~110 | ~137 | possessifs, impératifs | ~45 % : élisions (« t'attendent », « dis-le-moi »), conjugaisons de « tu », et surtout les 10 emails écrits à la première personne de Miradie — un vouvoiement contredit la voix personnelle |

Pièges pour une regex : « Continue », « Active », « Partage » existent aussi comme valeurs anglaises et comme statuts ; « memory.cat.you » = « Vous » comme intitulé d'onglet n'a pas d'équivalent au tutoiement (« Toi » ne marche pas).

---

## D. Lecture d'ensemble (pour le point global)

- Les six observations sont toutes fondées ; quatre sont **petites** (1, 4, 5, 6 : ~½ journée au total), deux **moyennes** (2, 3 : ~1 journée). Le point 4 est en réalité une garde à assouplir : la fonctionnalité existe.
- La dette la plus dangereuse n'est pas dans la liste : `makeFakeAiResponse` et les fixtures inventées (chiffres, citation McKinsey) sont à supprimer avant toute démo.
- Le registre est un choix produit, pas un chantier technique : le tutoiement coûte moitié moins et il est cohérent avec les emails et la voix de Miradie ; le vouvoiement impose de réécrire les emails ou d'assumer deux voix (app impersonnelle / emails personnels). Dans les deux cas, ajouter une consigne de registre aux prompts pour le contenu généré.
- Ordre proposé si tout est retenu : suppressions (B1, B4) → points 1, 6, 4, 5 → registre (bascule mécanique + relecture des 8 vues) → point 3 → point 2 (mobile compris) → décision sur `TweaksPanel` (B2) et sur la vérification de solde avant génération (B3).
