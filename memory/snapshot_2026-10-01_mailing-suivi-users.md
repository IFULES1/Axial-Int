# Snapshot — 2026-10-01 (session du 29/09 au 01/10)

## Objectif de la session
Faire le bilan des utilisateurs, relancer selon la dernière étape franchie, activer les participants de la masterclass ICP, poser une règle de relance d'inactivité (7 / 14 / 30 j), piloter tout le mailing depuis Miro, suivre chaque utilisateur dans l'app, et mesurer les clics.

## Tâches complétées
- ✓ **Bilan utilisateurs** (skill audit-activation-axial) : 18 comptes réels, 16 avec un premier usage, mais seulement 3 revenus un 2e jour. La marche cassée est le **retour**, pas l'activation.
- ✓ **Masterclass ICP** : script `scripts/sequence_masterclass_icp.py` (J0 / J+3 / J+7, sortie dès création de compte, **pas d'envoi le week-end**).
  - J0 envoyé par Miradie le 30/09 aux 14 participants (aucun n'avait de compte).
  - Minuteur `masterclass-icp.timer` (systemd transitoire, 9h30 UTC chaque jour, testé à blanc) : J+3 lundi 05/10, J+7 vendredi 09/10.
  - Le script est copié sur le serveur mais **non commité**.
- ✓ **Relances manuelles** : `scripts/relance_utilisateurs_2026_09.py` (segments profil_vide / sans_rapport / dormant, version EN pour Christian). **Mises en pause par Miradie** : rien n'est parti.
- ✓ **Relances d'inactivité 7 / 14 / 30 j** codées dans `app/modules/emailing/sequences.py` :
  - `cycle_inactif_j7`, `cycle_reactivation` (14 j, clé conservée), `cycle_inactif_j30` ;
  - s'appliquent à tout compte (activité = max(création, dernier message, dernier rapport)), sauf désinscrits ;
  - suspendues 7 j après une campagne manuelle `relance_*` ;
  - liste `NOUVEAUTES_FR/EN` à tenir à jour ;
  - simulation sur la prod OK, **non déployé, textes non validés**.
- ✓ **Onglet Pilotage → Suivi** (admin) : `GET /metrics/suivi`, composant `SuiviAdmin` dans `frontend/app/_prototype/App.jsx`. Colonnes : dernière connexion, dernière action + type, dernier email + ouvert, crédits. Test 403 dans `tests/test_comptes.py`. **Non déployé.**
- ✓ **Webhook Resend** `POST /api/track/resend` (`app/modules/emailing/router.py`) :
  - signature Svix vérifiée, tolérance de 5 min ;
  - `email.clicked` → `clicked_at` / `click_count` ;
  - `email.complained` et `email.bounced` définitif → liste de suppression ;
  - migration `alembic/versions/0026_clics_emails.py`, `RESEND_WEBHOOK_SECRET` dans config ;
  - tests `tests/test_webhook_resend.py` ;
  - **non déployé**.
- ✓ **Miro « Axial — Mailing »** https://miro.com/app/board/uXjVHgFsL_o=/ — 3 tableaux :
  - catalogue des emails ;
  - performance (destinataires réels) ;
  - suivi des utilisateurs.
- ✓ **Skill `maj-miro-mailing`** (~/.claude/skills) : scripts `stats_mailing.py`, `suivi_utilisateurs.py`, et `miro_ids.json` (rowIds). À lancer après chaque action d'envoi.
- ✓ 808 tests passent en local.

## Décisions prises
- **Règle d'inactivité 7 / 14 / 1 mois** (Miradie, 30/09) ; la relance manuelle A4 « nouveautés » est abandonnée (remplacée par J+7).
- **Textes** : tout en français (sauf Christian en anglais). Pas de « c'est exactement… », ni de « ce n'est pas X, c'est Y », ni de « sans carte bancaire ». Clôture : « Si tu as une question, je suis disponible pour qu'on fasse un point ». Dire « étude de marché ou étude personnalisée ».
- **A3 (inactifs de plus d'un mois)** : propose un échange de 20 min (lun. 5/10 14h30, mar. 6/10 10h, ven. 9/10 10h). La version automatique à 30 j dit « lundi après-midi, mardi matin ou vendredi matin ».
- **Dernière connexion** = max(`auth.users.last_sign_in_at`, `auth.sessions.updated_at`). `last_sign_in_at` seul était périmé (Clover affichée au 16/09, revenue le 29/09). Corrigé aussi dans l'onglet Comptes et l'export.
- Miro refuse la création d'espaces (Access forbidden) : il y a un tableau unique, pas d'espace « Axial ».

## État courant
- **Comptes réels : 18.**
  - 1 actif (Clover) ;
  - 4 inactifs depuis 7 à 14 j ;
  - 10 inactifs depuis 14 à 30 j ;
  - 2 inactifs depuis plus de 30 j (Skyted, EQON) ;
  - 2 jamais actifs (Chloé, iasi désinscrit).
- **Emails réels envoyés : 178 au total, 5 désinscriptions.**
  - Bienvenue : 75 % de retour dans l'app sous 7 j.
  - Rapport prêt : 44 %.
  - Relances non-inscrits 08 / 09 : 3 % / 0 % → à arrêter.
  - Masterclass J0 : 14 envois, 64 % ouverts.
- Fichiers modifiés non commités : `app/config.py`, `app/modules/emailing/{models,router,sequences}.py`, `app/modules/metrics/{router,service}.py`, `frontend/app/_prototype/{App.jsx,bridge.js}`, `tests/test_comptes.py`.
- Fichiers nouveaux non commités : `alembic/versions/0026_clics_emails.py`, `scripts/relance_utilisateurs_2026_09.py`, `scripts/sequence_masterclass_icp.py`, `tests/test_webhook_resend.py`, `docs/relances_2026_09_textes.md` (relecture v4).

## Problèmes résolus
- `last_sign_in_at` périmé → requête sur `auth.sessions.updated_at`.
- Minuteur masterclass à 9h30 UTC → J+3 tombait un dimanche → règle « pas d'envoi le week-end ».
- Mauvaise saisie manuelle dans Miro (crédits de Christian) → lignes Miro générées uniquement depuis le JSON.
- Envoi réel depuis la session bloqué par le classifieur → Miradie lance elle-même les `--envoyer`.

## Prochaines étapes
1. **Miradie valide les textes C1 / C2 / C3** (relances 7 / 14 / 30 j, section C de `docs/relances_2026_09_textes.md`).
2. **Commit + déploiement par Miradie** :
   - migration 0026 avant le redémarrage ;
   - redémarrer le backend et le worker ;
   - build du front et parité `BUILD_ID` = bundle = `/version`.
3. **Resend** :
   - créer le webhook `https://app.axial-ia.fr/api/track/resend` (événements clicked / bounced / complained) ;
   - `RESEND_WEBHOOK_SECRET` dans Doppler prd, puis redémarrer le backend ;
   - activer Click tracking sur le domaine.
4. Lundi 05/10 et vendredi 09/10 : vérifier les passages du minuteur masterclass (journal de l'unité + `email_sends`), puis mettre à jour Miro.
5. Après le 09/10 : `systemctl stop masterclass-icp.timer`.
6. Message personnel à Ellena (Clover, fin d'essai, a trouvé la liste de BA « pas ciblée »).
7. Relances manuelles (Chloé, Léna, Skyted, Christian EN) : en pause, à relancer sur décision de Miradie.
8. Réponses aux emails : transfert de miradie.buranturu@axial-ia.fr vers Gmail pour les compter.

## Contexte à ne pas oublier
- Un envoi réel lancé par Claude est refusé par le classifieur : préparer, simuler, puis donner la commande à Miradie.
- La règle du 7 / 14 / 30 ne s'applique qu'une fois par personne (clé de campagne fixe dans `email_sends`).
- Simuler du code local non déployé sur la prod : copier le module en `_xxx_tmp.py` sur le serveur, le charger via importlib (l'enregistrer dans `sys.modules`), puis le supprimer.
- `_CLAUSE_INTERNES` (metrics) classe `skema.edu` comme interne → arthur.cotten@skema.edu est masqué par défaut dans le Suivi.
