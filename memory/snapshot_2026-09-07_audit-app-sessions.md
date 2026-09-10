# Snapshot — 2026-09-07

## Objectif de la session

Audit complet de l'app à la demande de Miradie (« trop de bugs »), avec trois
points nommés : reconnexion depuis le navigateur, sessions qui ne persistent
pas, historique des conversations. Session commencée le 04/09 (changement
d'adresse du compte admin, écran carte), reprise le 07/09.

## Tâches complétées

- ✓ **Compte d'administration rattaché à `miradie.buranturu@axial-ia.fr`**
  (ex `admin@axial.com`, qui n'était pas une boîte mail). Même identifiant,
  mêmes crédits/rapports/veilles. Le circuit « Mot de passe oublié » fonctionne
  désormais sans intervention.

- ✓ **Écran carte contournable sans limite pour les comptes internes**
  (`carte_contournable` dans `/billing/balance`, calculé côté serveur). La
  notion de compte interne est définie une seule fois dans
  `app/shared/comptes.py` ; les métriques en dérivent leurs motifs SQL.

- ✓ **Bug de session (cause racine) corrigé** — `app/modules/auth/supabase_client.py`.
  Un seul client Supabase partagé (`lru_cache`) servait toutes les connexions ;
  supabase-py y rangeait la dernière session et armait un minuteur qui
  rafraîchissait le jeton **côté serveur** 10 s avant expiration. Supabase
  faisait tourner le jeton, celui du navigateur devenait périmé → 400 au refresh
  → déconnexion au bout d'une heure. Preuve dans le journal : paires d'appels
  `grant_type=refresh_token` toutes les 59 min 50 s sans requête navigateur.
  Correctif : `ClientOptions(auto_refresh_token=False, persist_session=False)`
  + `oublier_session()` après chaque sign-in/refresh (le client ne retient
  plus rien). Preuve post-déploiement : après connexion réelle par
  `service._sign_in`, `_refresh_token_timer is None` et
  `_in_memory_session is None`.

- ✓ **Navigateur (`bridge.js`)** : `tryRefresh` n'efface plus les jetons que
  sur 401/400 (un 502 pendant un redémarrage déconnectait définitivement) ;
  les trois `fetch` bruts (chat en flux, upload, rapport en flux) réessaient
  sur 403 comme sur 401 ; `axListConversations` lit **tous** les projets, plus
  seulement `projects[0]`.

- ✓ **Historique lisible** : 14 conversations sur 19 s'appelaient « Workspace ».
  Désormais la première question devient le titre (`titre_depuis()` dans
  `intelligence/service.py`), et les 14 existantes ont été rattrapées.

- ✓ **Clé API Gemini masquée dans les journaux** (`_sans_secret()` dans
  `app/shared/llm_client/__init__.py`). Vue en direct le 07/09 : `key=<masqué>`.

- ✓ **Régression majeure de mon fait, trouvée et corrigée** : mes `npm run
  build` du 04/09 et 07/09 ont tourné sans `NEXT_PUBLIC_API_URL` → le bundle
  appelait `http://127.0.0.1:8090`. **App cassée pour tout le monde du 04/09
  16:16 au 07/09 17:50** — zéro connexion possible pendant 3 jours. Détecté
  uniquement en testant une inscription neuve dans le navigateur.
  `.env.local` du VPS porte maintenant l'URL de production.

- ✓ **Vignettes d'historique invisibles** : `.conv-item` est un `<button>` sans
  reset (fond gris natif + texte clair). Corrigé dans `globals.css`. Étiquette
  « IL Y A 7 SEPT. » remplacée par `depuisLabel()` (durée relative < 7 j,
  date au-delà).

- ✓ **Déconnexion accessible** : la ligne utilisateur (div cliquable) a un
  rôle, un libellé « Se déconnecter » et le clavier.

- ✓ Tests : `tests/test_comptes.py`, `tests/test_audit_sessions.py` — 86 verts
  en local, 85 sur le serveur (un test local absent du VPS).

## Suite de soirée (07/09, 18h-21h UTC)

- ✓ **Essais prolongés au 14/09** pour `christian@eqonx.com` et
  `soumeya@optimpharma.fr` (`credit_balances.trial_expires_at`). Côté Stripe,
  l'abonnement d'essai de Christian est passé `canceled` le 05/09 alors que la
  base dit encore `trialing` : le webhook `subscription.deleted` n'a pas
  synchronisé. L'accès app dépend de la date en base → rouvert.
- ✓ **`is_admin: true` posé sur `miradie.buranturu@axial-ia.fr`** (app_metadata).
  Ouvre l'écran Pilotage. Effet de bord : son usage n'est plus facturé.
- ✓ **Onglet « Comptes » dans Pilotage** : `GET /metrics/comptes` (mêmes
  colonnes que l'onglet UTILISATEURS du classeur), `POST …/crediter`
  (crédits offerts, 1-500, motif tracé `admin:<motif>` dans credit_events),
  `POST …/prolonger` (1-90 j depuis aujourd'hui ou la fin actuelle si future).
  Vérifié : admin → 200, non-admin → 403.
- ✓ **Point 5 (historique d'un autre compte visible)** : la déconnexion
  routait vers l'accueil sans vider l'état React ; le compte suivant, dans le
  même onglet, héritait des conversations du précédent. `deconnecter()` fait
  maintenant un rechargement complet. Vérifié (navigation type `navigate`).
- ✓ **Apps Script** (`scripts/appscript/pilotage.gs`, local uniquement) écrit
  désormais un onglet `DASHBOARD_AUTO` à partir de `tableau` de l'export ; à
  recoller dans le classeur `1-OywR1s…` par Miradie. L'onglet DASHBOARD manuel
  du 27/08 n'est plus la référence.
- ✓ **Relance septembre** : `scripts/relance_non_inscrits_2026_09.py`,
  campagne `relance_2026_09`, 33 destinataires, exclusions nominatives
  Henry Tran (3 adresses) et `sabinjohan@gmail.com`. **Non envoyée** — texte à
  valider. Prénoms douteux hérités : Arthur (`calebmeinerad@`), Di
  (`steveny1989@`), Pellero (`v.pellero@`), Tiph (`tiphanie.doye@trinity-asia`).
- ✓ **Envois programmés le 08/09 à 07:00 UTC (9h Paris)** — minuteur systemd
  transitoire `axial-envois-2026-09-08.timer`, journal dans
  `/var/log/axial-envois-2026-09-08.log`. Exécute d'abord
  `scripts/point_jeudi_2026_09.py --envoyer` (Christian en anglais, Soumeya en
  français, campagne `point_jeudi_2026_09`), puis
  `scripts/relance_non_inscrits_2026_09.py --envoyer` (**28** destinataires :
  les 4 prénoms douteux retirés, une seule adresse pour Valérie Doye —
  `valerie.doye71@gmail.com`). Annulation :
  `systemctl stop axial-envois-2026-09-08.timer`.

## Bilan du 10/09 (jeudi)

- ✗ **Les envois du 08/09 n'ont PAS eu lieu.** L'unité transitoire n'avait pas
  de `$HOME`, Doppler a refusé de démarrer, le service est passé `failed` en
  344 ms. Zéro email sur `relance_2026_09` et `point_jeudi_2026_09`. Découvert
  le jour du rendez-vous proposé.
- ✓ Correctif vérifié à blanc (`systemd-run --wait --pipe --setenv=HOME=/root`
  → 28 destinataires). **Relance reprogrammée : vendredi 11/09 07:00 UTC**
  (9h Paris), unité `axial-relance-2026-09-11.timer`, journal
  `/var/log/axial-relance-2026-09-11.log`.
- ⏳ Emails Christian/Soumeya : texte à réécrire (le « jeudi » est passé), en
  attente d'un nouveau créneau et d'une validation.
- **Christian est revenu de lui-même le 08/09 à 14:26** (après la prolongation,
  avant tout email) : login → subscription → balance, puis plus rien. Il s'est
  arrêté sur l'écran carte, alors que « Continuer sans carte » y était.
- Miradie a testé l'inscription Gmail (`miradieburanturu@gmail.com`, 07/09
  18:07) : +40 essai, +30 retour migration, étude de marché offerte produite
  (0,47 €). Un second rapport (0,59 €) a été produit depuis le compte de
  contrôle de l'audit via le panneau navigateur.
- `cycle_reactivation` automatique parti à Christian (08/09) et Skyted (09/09),
  non ouverts. Skyted : essai expiré le 08/09.
- Les veilles de `miradie.buranturu@axial-ia.fr` continuent de débiter
  (−5/run) malgré `is_admin` : l'exemption ne couvre pas le worker. Solde 140.
  `miradie@francedigitale.org` est à 0 crédit avec une veille active.

## Décisions techniques prises

- **Le serveur ne détient aucune session Supabase** : il relaie des jetons.
  Toute alternative (client par requête) coûterait un thread par connexion.
- **Compte interne = domaine exact** (`%@axial-ia.fr`), plus un suffixe
  (`%axial-ia.fr` acceptait `faux-axial-ia.fr`).
- **Journaux `email_sends` / `password_resets` gardent l'ancienne adresse
  admin** : ce sont des faits historiques.
- **Le préfixe « il y a » vit dans la fonction d'étiquette, jamais dans le JSX.**
- **`is_admin` n'a été posé sur aucun compte** (décision laissée à Miradie :
  ce flag exonère aussi de facturation). Conséquence : l'écran Pilotage est
  inaccessible depuis l'app.

## État courant du système

```
Serveur              : 2026-09-07 18:05 UTC — backend/front/worker actifs
Bundle front         : 855.876381c40229888b.js — 0 trace de 127.0.0.1
Tests                : 86 verts local · ruff propre
Comptes              : 8 réels + 1 de contrôle (audit-0907-…@axial-qa.fr, supprimé des emails)
Connexions 04→07/09  : AUCUNE (app cassée) ; première connexion réelle = mon test 17:45
Stripe               : 0 écart base ↔ Stripe (2 abonnements) ; 1 client orphelin = test skema.edu
Apps Script          : tourne toutes les heures (/metrics/export 200)
Gemini               : 503 récurrents (5 bascules en 14 j) — Claude prend le relais
```

## Problèmes résolus

- Déconnexion ~1 h → minuteur serveur supprimé + refresh navigateur plus robuste.
- Historique « Workspace » ×14 → titre = première question + rattrapage.
- Vignettes blanches sans titre → reset CSS du bouton.
- « Il y a 7 sept. » → étiquette relative correcte.
- Clé Gemini en clair dans systemd → masquée.
- App injoignable (127.0.0.1 dans le bundle) → `.env.local` prod + rebuild.
- Désinscription « inconnue » du 07/09 16:42 → sonde du scanner Microsoft
  (IP 4.251.x, Safe Links) sur l'email de henry.tran@hec.edu, pas un humain.
  Les compteurs d'ouverture n=9 sont gonflés par ces scanners.

## Prochaines étapes

1. **Prévenir les utilisateurs actifs** que l'app était inaccessible du 04 au
   07/09 (Myrlid-Equity, Soumeya, Skyted, Christian) — c'est à Miradie de
   décider du message.
2. **`is_admin`** : poser ou non le flag sur le compte de Miradie (ouvre le
   Pilotage, exonère de facturation).
3. **Adresse `miradie.buranturu@axial-ia.fr` et emails de cycle de vie** :
   la suppression n'a pas été posée (0 envoi prévu aujourd'hui) — à trancher.
4. Christian : essai expiré le 05/09, renouvellement bloqué.
5. Écrire à Myrlid-Equity (2 crédits remboursés le 04/09).
6. Filtrer les ouvertures de scanners (plages Azure/Microsoft) dans les
   métriques email.
7. Le mystère `ibrahima.diabakhate@creative-cluster.org` : 3 tentatives de
   connexion le 04/09 depuis l'IP de Miradie, aucun compte à ce nom.
8. Reliquats : `COUTS_FIXES_MENSUELS_EUR`, retours de Christian sur la forme
   des rapports (tableaux, citations cliquables, synthèse en tête).

## Contexte à ne pas oublier

- **`frontend/app/_prototype/App.jsx` est compilé par Next.js** : `npm run
  build` puis `systemctl restart axial-frontend`. Le build fige
  `NEXT_PUBLIC_API_URL` ; vérifier `grep -c '127.0.0.1:8090' .next/static/chunks/*.js`
  = 0 puis **tester une inscription neuve dans le navigateur**. Un `curl /` à
  200 ne prouve rien.
- Trois jours sans connexion dans les journaux étaient le **symptôme**, pas le
  calme. Toujours croiser « pas d'erreur » avec « y a-t-il de l'activité ? ».
- Compte de contrôle de l'audit : `audit-0907-1757265000@axial-qa.fr`
  (mot de passe dans le scratchpad de session, non persistant).
- `docs/DEPLOY.md` du VPS était désynchronisé du dépôt local (URL `.com`) ;
  recopié le 07/09.
- Deux Qdrant : le bon est le **6355**. Accès prod : `ssh hostinger`,
  `PYTHONPATH=. doppler run --config prd -- .venv/bin/python`.
- Le classifieur de permissions bloque les commandes `scp && ssh` enchaînées :
  un fichier par appel.
