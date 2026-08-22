# Snapshot — 22/08/2026 — Campagne de migration, réinitialisation, bugs recensés

## Contexte
Suite de la session du 20/08 (backlog clos). Chantiers du jour validés par Miradie :
⑤ vérif rapports → ① streaming → ③ DB-investisseur → ② migration → ④ MCP.
**⑤, ①, ③, ② sont livrés. ④ (MCP Notion/Google) reste entier.**

## Livré depuis le dernier snapshot

### Chantier ③ — Base investisseurs connectée
- Module `app/modules/investors/` (lecture seule, cache 1 h) — secrets `INVESTOR_DB_URL/KEY` posés par Miradie.
- Scoring **porté à l'identique** de `rechercher_investisseurs.py` (vérifié : mêmes SGP, mêmes scores, même ordre).
- 6e type de rapport `cartographie_investisseurs` (30 crédits) — validé bout en bout : 3 418 mots, 16 sources de la base + 10 web, aucun fonds inventé.
- **Échelle d'élargissement** : secteur exact → parent → voisins → proches peuplés, annoncée au lecteur (12 secteurs sur 35 n'ont aucun investisseur tagué).

### Chantier ② — Migration des utilisateurs
- `legacy_reports` (migration 0011) : 107 rapports de 18 utilisateurs parqués par email, restaurés à l'inscription.
- **Bonus retour de 30 crédits** (total 50) idempotent, tracé `retour_migration`.
- Exception à la règle « email professionnel » pour les adresses de l'ancienne plateforme (42 % des utilisateurs à récupérer sont en adresse perso).
- **Campagne envoyée le 22/08 à 07:21** : 42 destinataires, **40 livrés, 2 rebonds** (`marie.dudicourt@inria.fr`, `serge@es2ka.com`), 0 plainte.
- Suivi d'ouverture **maison** (`email_sends` + pixel `/track/{token}.gif`, migration 0012) — le réglage Resend ne s'appliquait pas.
- Liste d'exclusion (`email_suppressions`, migration 0013) — Isaia retiré à la demande de Miradie.
- **Réinitialisation de mot de passe** (migration 0014) : jetons hachés SHA-256, usage unique, 1 h, email via Resend, écran dédié `?reinit=TOKEN`. Cycle complet testé (ancien mot de passe invalidé, jeton non réutilisable).
- Les adresses de l'ancienne plateforme **sans compte** reçoivent une invitation à en créer un plutôt qu'un silence.

## Résultats mesurés (22/08 ~09:40, ~2 h après l'envoi)
- **1 inscription** : `soumeya@optimpharma.fr` — **22 rapports restaurés**, 50 crédits. La chaîne email → inscription → restauration → crédits fonctionne sans intervention.
- **30 emails ouverts**, dont **9 ouverts plusieurs fois** (les seules ouvertures fiables ; les 30 incluent les pré-chargements Gmail/Apple).
- 7 comptes « réels » sur la nouvelle app, dont 3 appartiennent à Miradie.

## Bugs trouvés ET corrigés aujourd'hui
1. **Rapports vides** — le thinking adaptatif de Sonnet 5 se décompte de `max_tokens` ; 4 000 partaient en réflexion. Budget porté à 32 000 + garde « texte vide = pas de facturation ».
2. **Crash de l'app** (`ReportsEditor is not defined`) — ma réécriture de la cinématique avait supprimé 4 composants. Restaurés depuis git.
3. **Double numérotation `[N]`** — web et RAG numérotés séparément dans le même prompt ; les documents internes n'apparaissaient jamais dans les sources. Pool unifié (`app/shared/grounding.py`).
4. **Réponse LLM tronquée** (`Agritech / Food`) — même cause que le bug 1, sur le mapping de profil. Budget élargi + appariement tolérant.
5. **Lien de réinitialisation inutilisable** — l'effet sortait avant traitement si aucune session (or celui qui clique n'est jamais connecté). Repéré avant déploiement.
6. **« Tes 1 rapports »** et **accord au masculin** (« tu n'es pas passé ») pour la moitié des destinataires — repérés par le rendu réel, corrigés avant l'envoi.
7. **« Pas de carte bancaire »** affiché à l'inscription alors que l'onboarding l'exige.
8. **Lien « Mot de passe oublié ? »** = `href="#"` mort depuis toujours.

## Bugs / dettes CONNUS et NON corrigés
- **12 secteurs sur 35 sans aucun investisseur tagué** dans DB-investisseur (Marketplace en tête, sans parent) → correction de fond côté base, chantier data de Miradie.
- **169+ descriptions illisibles** dans DB-investisseur (cf. [[project_description_bruit]]).
- **Garde PII désactivé** en prod (`PII_GUARD_MODE=off`, sidecar Presidio éteint) alors que le code existe.
- **6e type d'analyse `analyse_reglementaire`** de l'ancienne app toujours absent (lot C de l'audit rapports).
- **Comptes de test en prod** : `legacy-test@axial-qa.fr`, `legacy-perso-test@gmail.com`, `revenant-test@axial-qa.fr`, `smoketest-*@axial-qa.fr` — à supprimer sur accord de Miradie.
- **`tiphanie.doye@axial-ial.fr`** — compte créé sur un domaine mal orthographié (`axial-ial`).
- **Registre FR incohérent** : l'app vouvoie, les messages d'erreur et les emails tutoient.
- **2 rebonds** à re-joindre autrement : `marie.dudicourt@inria.fr` (11 rapports), `serge@es2ka.com` (9 rapports).
- **Clé `service_role` de DB-investisseur exposée** dans un transcript le 20/08 → à régénérer + créer un rôle lecture seule.

## Reste à faire
1. **④ MCP Notion + Google** — dernier chantier des cinq.
2. **Internationalisation des contenus produits** (nouveau chantier du 22/08) : le sélecteur EN ne traduit que l'interface ; rapports, veilles, conversations et emails restent en français.
3. **Séquences email automatiques** — temps forts identifiés le 22/08 ; recommandé de commencer par **J-3 avant fin d'essai** (premiers essais à échéance le 01/09).
4. Retour de Miradie sur le **fond** des rapports (chantier ⑤ laissé ouvert).

## État technique
- Prod : app.axial-ia.fr · alembic **0014** · 63/63 tests · GitHub `main` = `79b35e4`.
- Resend : domaine `axial-ia.fr` **vérifié**, expéditeur `"Miradie @Axial" <miradie.buranturu@axial-ia.fr>`.
- Déploiement : scp → alembic si migration → `systemctl restart axial-*` → rebuild front avec `NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api`.
