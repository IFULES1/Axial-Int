# Snapshot — 2026-08-25

## Objectif de la session

Traiter les retours utilisateurs réels (rapport tronqué, marché sous-estimé,
blocage à la carte bancaire), relancer les contactés restés sans compte, et
retirer l'ancienne application du serveur.

## Tâches complétées

- ✓ **Rapport tronqué en plein mot — cause trouvée et corrigée.** Christian
  (`christian@eqonx.com`) a signalé une étude de marché s'arrêtant après 3 pages.
  Le champ `stop_reason` de l'API Anthropic n'était **jamais lu** : un texte
  coupé à `max_tokens` était archivé et facturé comme un texte terminé.
  Trois correctifs dans `app/shared/llm_client/claude.py` et
  `app/modules/analysis/service.py` : reprise automatique (jusqu'à
  `MAX_REPRISES = 3`), garde-fou non facturé si la troncature persiste,
  normalisation du `finishReason: MAX_TOKENS` de Gemini. Tests dans
  `tests/test_troncature.py`.

- ✓ **Sous-estimation de marché — deux causes, deux corrections.**
  Le rapport écrivait *« no GCC-specific L7e-equivalent type-approval pathway is
  confirmed in available sources »* et transformait cette **absence de source en
  décote de marché** (taux de capture ramené à 50-65 %). Ajout des règles 6 et 7
  dans `ANTI_HALLUCINATION` (`prompts.py`) : une absence est un trou de recherche
  à déclarer, jamais une décote ; toute estimation en volume doit nommer son
  dénominateur. Cause profonde : **une seule requête de recherche** partait vers
  les moteurs. Ajout de `search_multi()` dans
  `app/shared/search/orchestrator.py` et de `angles_de_recherche()` dans
  `prompts.py` — un angle par axe de la directive, traduits en anglais si la
  question l'est (`ANGLES_EN`).

- ✓ **Rapport de Christian régénéré** avec les correctifs, sans débit.
  1 740 mots → **8 113 mots**, 35 → **40 sources**, 3 → **11 sections**.
  Les journaux montrent `Sortie tronquée — reprise 1/3` : le correctif a
  fonctionné en conditions réelles. Deux sections nouvelles : le parc de
  deux-roues à remplacer (le dénominateur manquant) et l'homologation par région
  (7.2 GCC pointe vers **GSO**). Rapport `b3fcef9a-…` sur son compte, copie
  `f4737c6a-…` sur `admin@axial.com`, fichier dans `~/Downloads`.

- ✓ **Carte bancaire rendue optionnelle à l'onboarding** (blocage confirmé par
  plusieurs utilisateurs). Lien « Continuer sans carte » dans `OnbStep4`,
  routage `onb4 → onb3`. Parcours testé de bout en bout.

- ✓ **Relance des non-inscrits** : `scripts/relance_non_inscrits.py`, campagne
  `relance_2026_08`, **38 envois** avec prénom personnalisé (source :
  `/opt/axial-intelligence/var/destinataires.json`), pixel de traçage et
  désinscription en un clic.

- ✓ **Ancienne application arrêtée.** 21 conteneurs Docker stoppés,
  **RAM 4 205 Mo → 1 747 Mo**. Redirection 301 de `prometheus.axial-ia.fr` et de
  l'IP vers `app.axial-ia.fr` (chemin conservé) — quelqu'un visitait encore
  l'ancienne URL le jour même. Les 5 volumes de données sont conservés,
  `--restart=no` appliqué.

- ✓ **Sauvegarde Qdrant** : `scripts/sauvegarde_qdrant.sh`, timer systemd
  `axial-sauvegarde.timer` à 3h30, rétention 7 jours. 642 Mo et 79 167 vecteurs
  n'avaient aucune copie.

- ✓ **Faux positif du garde-fou PII corrigé.** En mode shadow, la suite d'années
  `2024 2025 … 2031` était détectée comme un numéro de carte. En mode `enforce`
  les chiffres du rapport auraient été masqués. Clé de Luhn ajoutée dans
  `app/modules/pii/redaction.py` (`_VALIDATEURS`).

- ✓ **Étude personnalisée alignée à 40 crédits** (`synthese_executive`), même
  format que l'étude de marché.

- ✓ Appel dupliqué de `grant_return_bonus` retiré dans `app/modules/auth/router.py`.

## Décisions techniques prises

- **Reprise plutôt que budget plus large.** Augmenter `max_tokens` ne résout
  rien : le thinking adaptatif de Sonnet 5 se décompte du même plafond. La
  reprise fonctionne quel que soit le modèle.
- **Un résultat tronqué n'est ni archivé ni facturé** (`degraded=True` →
  `finalize` retourne `{"charged": 0}`). L'utilisateur voit le texte à l'écran
  mais doit relancer.
- **Redirection avant arrêt.** Couper sec aurait laissé une page morte à des
  visiteurs réels.
- **Presidio ne renvoie que `PERSON`.** Masquer `ORGANIZATION` et `LOCATION`
  détruirait le produit — Axial analyse des marchés et des concurrents.
- **Angles de recherche traduits à la main** (`ANGLES_EN`) plutôt que par appel
  LLM : jeu fermé, pas de latence ni de point de panne supplémentaire.

## État courant du système

```
Comptes réels        : 7  (miradie×2, admin, tiphanie, soumeya, christian, s.gorjux)
Tunnel               : 43 contactés → 7 comptes → 1 actif → 0 récurrent
Emails               : migration 43 · relance 38 · cycle_* 2
Qdrant (port 6355)   : knowledge_base 79 078 vecteurs · documents 89
VPS                  : 1 747 Mo / 7 940 Mo de RAM · 25 Go / 96 Go de disque
Services systemd     : axial-backend, -frontend, -worker, -qdrant, -presidio,
                       -sauvegarde.timer
Tests                : 70 verts · ruff propre
Interrupteurs Doppler: EMAIL_SEQUENCES_ACTIVES=true · PII_GUARD_MODE=shadow
```

Prix des rapports : `etude_marche` 40 · `synthese_executive` 40 ·
`cartographie_investisseurs` 30 · les trois autres 25.

## Problèmes résolus

- Rapport coupé en plein mot → `stop_reason` lu + reprise automatique.
- Marché sous-estimé → absence de source ne peut plus devenir une décote.
- Recherche à une seule requête → 5 angles (300 bruts → 130 dédupliqués).
- Carte obligatoire → passage optionnel.
- `2024 2025 …` masqué comme carte bancaire → clé de Luhn.
- Ancienne app consommant 2,9 Go → arrêtée avec redirection.

## Prochaines étapes

1. **Débloquer l'essai de `christian@eqonx.com`** — expire le **5 septembre**
   avec `cancel_at_period_end = true`. Il a été bloqué le 22 parce qu'il
   n'utilisait pas l'app ; ce n'est plus vrai. Sans déblocage il perd l'accès.
2. **Message personnel à `s.gorjux@skyted.io`** (Skyted). Inscrit le 25/08 à
   13h30 après la relance, profil rempli, 50 crédits, **0 question** — il a
   frappé l'écran carte obligatoire, retiré à 14h04. Première conversion de la
   relance, arrêtée sur le mur qui vient d'être supprimé.
3. **Arbitrer les crédits de bienvenue.** Un utilisateur sans carte a 20 crédits ;
   le rapport le moins cher en coûte 25. Le blocage est déplacé, pas supprimé.
   Décision de prix : passer à 40 ou laisser tel quel.
4. Suivre les ouvertures de `relance_2026_08` (les vraies lectures sont les
   `open_count >= 3`, pas les ouvertures uniques).
5. Tableau de bord de suivi des relances — prompt rédigé pour une discussion
   dédiée ; le trou principal est que **les relances manuelles ne sont tracées
   nulle part**.
6. Dettes restantes : 12 secteurs non tagués, mentions légales (SIREN),
   régénération de la clé `service_role` de DB-investisseur.

## Contexte à ne pas oublier

- **Accès production** : `ssh hostinger`, `/opt/axial-intelligence`, toute
  commande base passe par
  `PYTHONPATH=/opt/axial-intelligence doppler run --config prd -- .venv/bin/python`.
- **Deux Qdrant sur le serveur** : le bon est le **6355** (service systemd) ;
  le 6333 était le conteneur de l'ancienne app, désormais arrêté. `app/config.py`
  a `6333` en valeur par défaut mais Doppler impose `QDRANT_URL=…:6355`.
- **Les valeurs de profil restent en français en base** (secteur, stade, défi) :
  elles alimentent la correspondance de la cartographie investisseurs. Seul
  l'affichage est traduit, via `libelle()` et `LABELS_EN` dans `App.jsx`.
- **Vérifier l'onboarding depuis un compte neuf, jamais connecté.** Deux fois
  cette semaine, un balayage fait en étant connecté a raté des écrans entiers du
  tunnel d'inscription — c'est le seul parcours qu'un compte connecté ne revoit
  jamais.
- **Toujours lancer la simulation avant un envoi d'emails** :
  `scripts/sequences_emails.py` sans `--envoyer` reflète exactement l'envoi réel
  (désinscrits et déjà-envoyés compris).
- **Prénoms douteux partis dans la relance** : Arthur pour `calebmeinerad@`,
  Di pour `steveny1989@`, Pellero pour `v.pellero@`, Tiph pour
  `tiphanie.doye@trinity-asia.com`. Trois `Henry Tran` distincts ont reçu le
  message sur trois adresses.
- **Sauvegarde des comptes de test supprimés** :
  `/opt/axial-intelligence/sauvegarde-comptes-test-2026-08-24.json`.
- **Ancienne configuration nginx** :
  `/root/insight-mvp.nginx.avant-arret-2026-08-24`.
- Artifacts de la session : séquences email
  `https://claude.ai/code/artifact/fc77ca80-d838-4ffd-900e-93163b6f8cf4` ·
  arbitrage Google Cloud
  `https://claude.ai/code/artifact/41f6147b-e53b-4438-82ff-6ff173ad5d9b`.
