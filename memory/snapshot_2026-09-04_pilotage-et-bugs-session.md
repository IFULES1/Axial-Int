# Snapshot — 2026-09-04

## Objectif de la session

Instrumenter les coûts et la rentabilité, livrer un système de pilotage dans
Google Sheets, et traiter les retours utilisateurs — dont deux bugs découverts
en analysant le comportement du premier utilisateur réellement engagé.

## Tâches complétées

- ✓ **Instrumentation complète des coûts** (migrations 0018 et 0019).
  `LLMResult` porte désormais l'entrée et la sortie séparément ; les tarifs
  vivent dans `app/modules/billing/couts.py`, configurables par variable
  d'environnement. Coût persisté sur `reports`, `messages` et `watch_runs`,
  plus le coût de recherche web compté par fournisseur via un compteur passé à
  l'orchestrateur. **Premier coût réel mesuré : 0,529 €** pour un rapport
  (0,446 modèle + 0,083 recherche) — mon estimation antérieure de 0,27 € était
  fausse de près de moitié.

- ✓ **Écran Pilotage** dans l'app (admin uniquement) : coûts, rentabilité par
  type, revenus, activité. Refuse d'afficher une marge quand aucun coût n'est
  mesuré, plutôt qu'un trompeur 100 %.

- ✓ **Catalogue de 56 métriques** (`docs/metriques_axial.csv`), priorisées, avec
  l'état réel de mesurabilité : 42 mesurables, 8 partielles, 6 impossibles.

- ✓ **Classeur de pilotage** livré à Miradie (11 onglets, données réelles).
  Le connecteur Drive ne sait pas écrire dans les cellules d'une feuille
  existante — le classeur est donc créé et déposé, pas rempli sur place.

- ✓ **Automatisation Sheets** : endpoint `GET /api/metrics/export` protégé par
  `METRICS_EXPORT_TOKEN` (en-tête, comparaison à temps constant) et script
  `scripts/appscript/pilotage.gs` à coller dans le classeur, déclencheur
  horaire. Le script ne réécrit QUE les onglets de données.

- ✓ **Carte bancaire** : écran présenté à chaque connexion tant qu'aucun
  abonnement n'est actif, contournable **pendant la période d'essai
  seulement**. Nouveau champ `periode_essai_active` distinct de `trial_active`
  (qui exige des crédits restants).

- ✓ **Premier rapport offert** : les rapports **restaurés** ne bloquent plus
  l'offre. Ils excluaient exactement les comptes visés — Soumeya (22 restaurés,
  0 produit) et Gorjux (5 restaurés, 0 produit).

- ✓ **Veille** : nom par défaut suivant le skill choisi (toutes les veilles
  s'appelaient « Veille concurrentielle »), flux du catalogue attachés
  automatiquement à la création, recherche multi-angles par skill.

- ✓ **Journal des contacts manuels** (migration 0020, `contacts_manuels`,
  `scripts/contact.py`). Les cinq échanges WhatsApp avec Christian y sont
  consignés, avec suite promise et date de relance.

- ✓ **Deux bugs corrigés**, découverts en analysant le parcours du 03/09 :
  voir la section dédiée plus bas.

## Décisions techniques prises

- **Une case vide plutôt qu'un chiffre faux.** Le tableau de bord et le
  classeur laissent vide ce qui n'est pas mesuré, avec la raison en clair.
- **Le jeton d'export est distinct des sessions** : un script planifié ne peut
  pas se reconnecter et un JWT d'administration expire en une heure.
- **Le script Apps Script ne touche jamais les onglets rédigés à la main.**
  Une synchro qui écrase du contenu curé finit désactivée.
- **Les tarifs des modèles sont des ordres de grandeur documentés comme tels**,
  surchargeables par variable d'environnement.

## Les deux bugs du 03/09 — chaîne complète

Le premier utilisateur réellement engagé (`idfinance.conseils@creative-cluster.org`,
Myrlid-Equity) s'est inscrit le 03/09 à 18h58, a rempli son profil, posé une
première question à 19h59, **puis une deuxième question de fond à 20h16** — une
correction sur son modèle économique. Il a reçu **une réponse vide**, a été
**débité de 2 crédits**, puis **déconnecté**. Il n'est pas revenu.

**Bug 1 — réponse vide facturée.** Journaux à 20:15:31 : Gemini répond 503, le
basculement vers Claude fonctionne (HTTP 200). Mais `claude.stream()` ne remonte
que `text_stream`, c'est-à-dire les blocs de TEXTE. Avec `max_tokens=2500`, la
réflexion adaptative a tout consommé sans produire un seul bloc de texte. Le
flux s'est fermé proprement, sans exception : `chunks` vide → `answer=""` →
`degraded=False` → archivé et facturé.
*C'est exactement le bug des rapports vides du 22/08 ; le garde-fou avait été
posé côté rapports et jamais côté conversation.*
→ Corrigé : réponse vide = dégradée, non facturée. Budget chat 2 500 → 8 000.
→ Test : `tests/test_troncature.py::test_reponse_de_chat_vide_non_facturee`.

**Bug 2 — déconnexion silencieuse.** À 20:17, toutes les requêtes passent en
403 (`/auth/me`, `/billing/balance`, `/memory/profile`), et sa tentative de
reposer une question à 20:23 échoue aussi. Cause : au démarrage de l'app,
`axMe()` était suivi de `.catch(() => axClearToken())` — **n'importe quel
échec** (réseau, 500, timeout) effaçait le jeton définitivement. Ensuite les
requêtes partent sans en-tête et FastAPI (`HTTPBearer`) répond 403. Or le
rafraîchissement ne se déclenchait que sur **401**, jamais sur 403 : aucune
récupération possible.
→ Corrigé : déconnexion réservée aux refus d'authentification avérés ;
rafraîchissement déclenché aussi sur 403.

**Ces deux bugs frappaient tous les utilisateurs.** Le second explique
probablement une partie du « ils ne reviennent pas » constaté depuis le début.

## État courant du système

```
Serveur              : 2026-09-04
Comptes              : 8 (4 clients, 4 internes)
Migrations           : 0020_contacts (head)
Tests                : 75 verts · ruff propre
Interrupteurs        : EMAIL_SEQUENCES_ACTIVES=true · PII_GUARD_MODE=shadow
                       COUTS_FIXES_MENSUELS_EUR=0 (à renseigner)
                       METRICS_EXPORT_TOKEN défini
```

Soldes et essais :
```
admin@axial.com                200 crédits · essai expiré 31/08 · BLOQUÉ
christian@eqonx.com             30 crédits · essai 05/09     · BLOQUÉ
soumeya@optimpharma.fr          70 crédits · essai 05/09
s.gorjux@skyted.io              70 crédits · essai 08/09
idfinance.conseils@…            38 crédits · essai 17/09   (nouveau, 03/09)
```

Coûts mesurés à ce jour : rapport ≈ 0,49-0,53 € · veille ≈ 0,13 € ·
message de chat ≈ 0,001-0,005 € (chemin non-streaming uniquement).

## Problèmes résolus

- Rapport tronqué → reprise automatique + garde-fou non facturé (25/08).
- Marché sous-estimé → une absence de source ne peut plus devenir une décote.
- Recherche à requête unique → multi-angles par directive et par skill.
- Rapport perdu à la fermeture du navigateur → archivage dans le thread.
- Faux positif PII sur une suite d'années → clé de Luhn.
- Carte obligatoire → contournable pendant l'essai.
- Réponse de chat vide facturée → garde-fou + budget relevé.
- Déconnexion sur panne passagère → restreinte aux vrais refus.

## Prochaines étapes

1. **Christian : essai expire le 05/09, renouvellement bloqué.** À débloquer ou
   prolonger. Tableaux et liens cliquables lui ont été promis.
2. **Écrire à Myrlid-Equity** — il a fait la boucle complète et s'est heurté aux
   deux bugs. Ses 2 crédits sont remboursés (36 → 38).
3. **Retours de Christian sur la forme des rapports** : tableaux formatés
   (ni le rendu app ni le PDF ne gèrent les tableaux markdown, alors que le
   prompt en demande), citations et références cliquables dans le PDF, synthèse
   exécutive en tête. Réserve assumée sur les graphiques.
4. **Connexion Google** — décision prise : autoriser le freemail via Google
   uniquement. Non implémenté. ~½ journée, débloque la demande de Christian.
5. **Saisir `COUTS_FIXES_MENSUELS_EUR`** : sans ça, ni le coût total ni le point
   mort ne sont calculables.
6. Installer l'Apps Script dans le classeur (jeton fourni séparément).

## Contexte à ne pas oublier

- **Le connecteur Drive ne peut pas écrire dans une feuille existante.** Il lit,
  crée, renomme, partage. Pas d'API Sheets : ni cellules, ni onglets, ni
  formules dans un classeur déjà là.
- **Le fichier « Metrics app »** est partagé depuis `miradie.buranturu@axial-ia.fr`
  (id `1Rk3MLyF5xBVMcoo7PbmkDxcSN2Xif0llvOlu2E01nas`), pas depuis le compte
  Gmail principal.
- **Chat en streaming = coût non mesurable** : le fournisseur ne renvoie pas de
  compteur d'usage. Ces messages restent à `null` plutôt que de porter une
  estimation indistinguable d'une mesure.
- **`admin@axial.com` n'est pas une vraie boîte mail** : la réinitialisation de
  mot de passe ne peut pas l'atteindre. À rattacher à une adresse réelle.
- Vérifier l'onboarding **depuis un compte neuf**, jamais connecté.
- Toujours lancer la simulation avant un envoi d'emails.
- Deux Qdrant sur le serveur : le bon est le **6355**.
