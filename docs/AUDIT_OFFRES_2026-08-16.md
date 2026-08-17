# Audit de cohérence — Offres & facturation vs implémentation

**Date :** 2026-08-16 · **Périmètre :** écarts entre les décisions de refonte des offres (free_beta 20cr, Pro 50€/120, Premium 90€/250, packs PAYG 50/100/200, coûts crédits, suppression early_backer/analyse_approfondie, tout en €) et l'app réellement déployée sur https://app.axial-ia.fr.

**Méthode :** lecture exhaustive de la chaîne facturation (catalog/service/stripe_gateway/router) + câblage frontend, tests unitaires, test fonctionnel sur la vraie base, vérification du rendu live.

---

## 1. Ce qui était déjà conforme ✅ (aucune correction)

| Élément | Vérifié |
|---|---|
| `/billing/plans` en prod | free_beta 20cr · Pro 50€/120 · Premium 90€/250 · Enterprise · packs 20/40/80€ — identique à la source |
| `CREDIT_COSTS` | `run_agent_veille`=5, `agent_message`=2, étude=40, analyses=25 ; **pas** d'`analyse_approfondie` |
| Facturation veille | `run_agent_veille` (5 cr) câblé sur check + consume dans `watches/service.py` |
| Devise | **0** résidu `$`/`usd`/`price_usd` dans le code |
| Références mortes | **0** occurrence d'`early_backer` ou `analyse_approfondie` |
| Câblage front abonnement/achat | `subscribe(p.key)` / `buy(p.key)` utilisent les clés **dynamiques** de l'API (pas de valeur en dur) |
| Auth ES256 | corrigée ; les questions **débitent bien** les crédits (prouvé : compte test 120→86) |

---

## 2. Écarts trouvés et corrigés 🔧

### 2.1 — Crédits d'inscription : 120 au lieu de 20 🔴 (impact réel, live)
`service.py` attribuait `FREE_BETA_CREDITS = 120` à chaque nouveau compte, alors que ta décision et le catalogue `free_beta` disent **20**. Prouvé en prod (compte test démarré à 120).
**Corrigé :** `FREE_BETA_CREDITS = 20` + docstring + **test garde-fou** (`test_free_beta_grant_matches_catalog`) qui verrouille l'égalité grant = catalogue.

### 2.2 — Crédits d'abonnement qui s'accumulent au lieu de se renouveler 🟠
Le webhook créditait **tout** via `grant_purchased` → `purchased_credits` (n'expirent jamais, s'additionnent). Or l'UI promet « les crédits du plan se renouvellent chaque mois et **ne s'accumulent pas** ». Chaque renouvellement empilait donc les crédits (fuite de valeur).
**Corrigé :** distinction du **type de grant** (`kind`) dans `parse_webhook` → le router route les abonnements vers un nouveau `grant_subscription()` qui **remet à niveau** `free_credits` (renouvellement mensuel, pas de cumul) ; les packs PAYG restent en `grant_purchased` (cumul, sans expiration).
**Testé sur la vraie base :** abo x2 → free reste 120 (pas 240) ; packs +50/+50 → 100. ✅

### 2.3 — Page d'aide « Crédits & Plans » obsolète 🟠 (user-facing)
`DocsCredits` affichait d'anciens plans fictifs **Solo/Founder/Team (0/49/199 €, 500/5000/25000 cr)** + un tableau de coûts inventé (~5, ~150, ~900 cr).
**Corrigé :** plans → **Free Beta / Pro / Premium / Enterprise** (vrais prix, crédits, sièges) ; tableau de coûts → vrais `CREDIT_COSTS` (message 2, run veille 5, analyses 25, étude 40).

### 2.4 — Modale « Crédits insuffisants » obsolète 🟠 (user-facing)
Proposait un plan **« Strateg » 49 €/15 000 cr** + recharge **9 €/500 cr** (inexistants).
**Corrigé :** → **Pro 50 €/120 cr** + packs réels (50/100/200 cr, 20/40/80 €) ; i18n `reports.quota.upgrade` « Passer à Strateg » → « Passer à Pro ».

### 2.5 — Landing : lien « Tarifs » cassé 🟡
Le lien nav `#pricing` pointait vers une **section inexistante** (ancre morte).
**Corrigé :** ajout d'une **vraie section pricing** publique (`#pricing`) avec les 4 offres réelles (rendu vérifié live). Le lien nav `#trust` (également mort, sans rapport avec les offres) a été **retiré**.

### 2.6 — Détails
- Docstring catalogue « 5-tier » → décrit correctement les 4 plans.
- i18n mort `credits.plan.next` « Strateg — 49 €/mois » → « Pro — 50 €/mois ».

---

## 3. Points signalés → tous corrigés le 16/08 ✅

| Point | Détail | Résolution |
|---|---|---|
| **Clés internes des plans** | Restaient `solo_founder`/`startup_pro`. | Renommées **`pro`** / **`premium`** (catalog + test ; front dynamique inchangé). Vérifié en prod. |
| **Pack « Pro » (100 cr)** | Même nom que le plan Pro → collision (aggravée par le renommage ci-dessus). | Clé + label **`pro` → `boost`** (packs : starter/**boost**/scale). Vérifié en prod. |
| **Compte test à 86 cr** | Solde issu de l'ancien grant 120. | **Reset à 20** en base (tous les comptes test). |
| **Barres de quota démo** | Modale (code mort — jamais déclenchée) avec usage fabriqué (2 481/2 500, 1932/348/201). | Section fabriquée **retirée**, remplacée par le message honnête `reports.quota.body`. |
| **Section « Confiance »** | Lien nav mort, pas de contenu. | **Vraie section `#trust`** ajoutée (cloisonnement, pas d'entraînement, hébergement UE, sources traçables) + lien nav restauré et relibellé **« Confiance »** (i18n disait « Sources », incohérent). |

---

## 4. Hors périmètre de cet audit (rappel)

- **Webhook Stripe live** : pointe encore vers l'ancienne app. À recréer vers `https://app.axial-ia.fr/api/billing/webhook` (events `checkout.session.completed` + `invoice.paid`), puis mettre à jour `STRIPE_WEBHOOK_SECRET` en prd. Indépendant des offres.

## Fichiers modifiés
- `app/modules/billing/service.py` (grant 20 + `grant_subscription`)
- `app/modules/billing/stripe_gateway.py` (`kind` pack/subscription)
- `app/modules/billing/router.py` (routage du grant)
- `app/modules/billing/catalog.py` (docstring)
- `tests/test_billing_reports.py` (garde-fou 20)
- `frontend/app/_prototype/App.jsx` (DocsCredits, modale quota, section pricing landing, i18n)

**Déployé et vérifié en prod** (backend redémarré, front rebuild, 5/5 tests verts, sémantique grants testée sur la vraie base).
