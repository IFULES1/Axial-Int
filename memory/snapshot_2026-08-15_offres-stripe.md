# Snapshot — 2026-08-15 — Offres € + Stripe (récurrent + PAYG) TESTÉ + onglets branchés

## Fait cette session
### Offres refondues (tout en €)
- Abonnements (`catalog.py` PLANS) : Free Beta 0€/20 crédits · **Pro** (ex-solo_founder) 50€/120/1 siège ·
  **Premium** (ex-startup_pro) 90€/250/2 sièges · Enterprise (devis). **early_backer supprimé.**
  Clés inchangées (solo_founder/startup_pro), seuls les `name` d'affichage changent. `price_usd`→`price_eur`.
- PAYG (`stripe_gateway.py` CREDIT_PACKS) : 50/20€ · 100/40€ · 200/80€.
- Coûts (`CREDIT_COSTS`) : retiré `analyse_approfondie`, ajouté **`run_agent_veille` = 5 crédits**
  (run_watch débite désormais ça, plus l'analysis_type).

### Stripe — branché ET testé de bout en bout
- Backend : `create_checkout_session` (packs, mode=payment) + **`create_subscription_session`** (abos,
  mode=subscription, `price_data recurring` — AUCUN produit Stripe à créer). Endpoints `/billing/checkout` + `/billing/subscribe`.
- Config : `stripe_secret_key` lit via AliasChoices **`STRIPE_TEST_API_KEY` > STRIPE_SECRET_KEY > STRIPE_API_KEY**
  → la clé TEST prime (sécurité dev). Propriété `stripe_test_mode` (prefix sk_test).
- Front : onglet Crédits = solde réel + section **Abonnements** (Pro/Premium/Enterprise, « S'abonner ») + **PAYG** (« Acheter »). Bridge `axCheckout`/`axSubscribe`.
- **TEST RÉEL VALIDÉ** : abonnement Pro payé avec carte test 4242 → webhook `POST /billing/webhook 200`
  → solde founder2 **877 → 997 (+120)**. Le tunnel marche.
- ⚠️ **LIMITE** : on crédite sur `checkout.session.completed` (1er paiement). Les **renouvellements mensuels**
  (`invoice.paid`) ne sont **pas gérés** → à ajouter pour un vrai récurrent complet. + pas de tracking du plan/abo actif.

### Onglets branchés (maquette → réel)
- **Mémoire** : vrai profil founder éditable (`axGetProfile`/`axSaveProfile`) **+ `DocumentsPanel`** (upload/list/delete de docs RAG user via `/documents`).
- **Crédits** : voir ci-dessus.
- **Documentation** = vraie page d'aide statique (RAS, pas une maquette).
- **Paramètres** = surtout équipe/connexions **sans backend** (features à construire). **Partage** = aucun backend.
- **Rendu markdown** (`MarkdownView`) appliqué à l'éditeur Reports + timeline agents.
- **Historique global** : `GET /watches/activity` + modale `ActivityHistory` (bouton dans Agents).

## État courant
- Qdrant 6355 · Backend 8090 (mode test Stripe) · Front 3005 · Worker · `stripe listen` (chez l'utilisateur).
- founder2 : 997 crédits, abonné Pro (test). Secrets Doppler : `STRIPE_TEST_API_KEY`, `STRIPE_WEBHOOK_SECRET` (test) posés.
- 56 tests backend verts.
- Parqué : **Resend DNS** (domaine, attendu). **Supabase Pro** (à prendre).

## Next steps (voir bilan « produit → plateforme » donné en session)
Résumé : le PRODUIT (3 modes + monétisation) est fait et testé. Pour une PLATEFORME de bout en bout, il reste :
déploiement, auth prod Supabase, infra prod (Qdrant/DB/Doppler prd), Stripe live + `invoice.paid`,
Resend DNS, features périphériques (Paramètres/Partage/OCR), sécu/RGPD, tests d'intégration, monitoring, légal.

## Contexte
- Clé test prime tant que `STRIPE_TEST_API_KEY` est dans la config dev → 0 débit réel. Prod = config `prd` sans clé test.
- Snapshots du jour : `_polish-etat`, celui-ci (`_offres-stripe`).
