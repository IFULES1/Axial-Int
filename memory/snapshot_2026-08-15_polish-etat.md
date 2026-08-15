# Snapshot — 2026-08-15 — Rendu markdown + historique skills + état projet honnête

## Fait cette session (suite de _veille-finale.md)
- [✓] **Rendu markdown** : nouveau composant `MarkdownView` + `renderInline` (App.jsx) — titres, gras,
  puces, `---`, citations `[N]` en violet. Appliqué à **l'éditeur Reports** ET **la timeline des agents**
  (delta + rapport). Fini le markdown brut (`**`, `-`). Validé à l'écran.
- [✓] **Historique global des skills** : endpoint `GET /watches/activity` (`service.list_activity` — join
  watch_runs × watches) + modale `ActivityHistory` (bouton « Historique » dans l'onglet Agents). Affiche
  tous les runs de tous les agents : skill (badge), agent, date, 🆕/rien de neuf, aperçu delta. Validé à l'écran.
- [✓] **56/56 tests** verts, `ruff` clean.
- [✓] **État projet audité** (branché vs maquette) — voir ci-dessous.

## ⚠️ Découverte importante : écrans encore en MAQUETTE
Le front a plusieurs onglets **non branchés** au backend (données `AXIAL_SURFACES` statiques) :
- 🔴 **Onglet Mémoire** (backend `/memory/profile` existe)
- 🔴 **Onglet Crédits** — plans/achat (backend **checkout Stripe existe** : `billing/router.py`, `stripe_gateway`, CREDIT_PACKS, webhook)
- 🔴 **Onglet Documentation** — upload de docs (backend RAG/ingestion existe)
- 🔴 **Onglet Paramètres** + **Partage (ShareModal)**
- 🟢 Réels : solde crédits (header, `axBalance`), onboarding profil (`axSaveProfile`), auth, les 3 modes.

## État global (rappel)
- **Les 3 modes produit sont FAITS et testés en réel** : Workspace 💬, Agents de veille 🛰️, Reports 📄 (+PDF filigrané).
- Socle : FastAPI modulaire + Next.js, Qdrant natif 6355 (79k vecteurs), Exa/Tavily/Linkup + rerank Cohere,
  Gemini/Claude + failover, PII guard, Doppler, worker autonome.
- founder2@axialtest.com / password123 · ~777 crédits · 30 flux RSS Inoreader · 5 skills veille.
- Services (à relancer après reboot) : `./scripts/start_qdrant.sh` · uvicorn 8090 · npm 3005 · `make worker`.
- ⚠️ Docker occupe 6333/3000/8080 — ne pas toucher. Preview = attacher à l'URL (pas de start Python auto).

## 🔴 NEXT STEPS (priorisés) — à la reprise

### Bloc 1 — Activation (court terme, débloquable vite)
1. **Resend prod** : DNS du domaine en cours (attendu le 15/08). Une fois propagé → `MAIL_FROM="veille@axial-ia.com"` + test d'envoi réel. Cf. `docs/SETUP_RESEND.md`. **← PARQUÉ, reprendre en priorité.**
2. **Tag Inoreader « concurrents [secteur] »** (action utilisateur) → catégorie `concurrence` → comble le seul trou RSS.
3. **Brancher les onglets maquette** : Mémoire, Crédits, Documentation (upload), Paramètres, Partage.

### Bloc 2 — Monétisation & comptes réels
4. **Flux de paiement Stripe** au front (backend checkout prêt) → acheter des crédits.
5. **Auth prod Supabase** (aujourd'hui `dev_users` local).

### Bloc 3 — Production (rien n'est déployé)
6. **Déploiement** (app en local uniquement).
7. **Qdrant sur VPS** + Doppler prod + Supabase prod.
8. **Durcissement sécurité VPS**.
9. Bascule embeddings **B→C** (BGE-m3 → 0 €/RGPD).

### Bloc 4 — Robustesse / extensions
10. OCR + DOCX/XLSX (~8 docs scannés). 11. Tests d'intégration autres modes. 12. Filtrage bruit RSS + déclencheurs événementiels. 13. Capture dataset fine-tuning.

## Où on en est vraiment
Le **cœur produit (3 modes) est construit et marche en réel** — le plus dur est fait. Restent 3 blocs nets :
(a) brancher les écrans périphériques, (b) monétisation Stripe, (c) passer en PROD.
La démo tourne de bout en bout, mais **rien n'est déployé ni monétisable** pour l'instant. Prochain grand jalon
logique : **« rendre l'app utilisable par un vrai utilisateur »** = derniers écrans + Stripe + déploiement.

## Contexte à ne pas oublier
- Rerank veille = par SUJET (`engine._format_sources(query,…)`). Worker : `next_run_time` ≠ None. Filigrane : restart backend après changement du PNG.
- Resend = API native (`RESEND_API_KEY`+`mail_from`), pas SMTP. `mail_from` encore en bac à sable (`onboarding@resend.dev`) → vérifier domaine.
- Snapshots : `_14-45`, `_veille`, `_veille-complete`, `_veille-finale`, celui-ci (`_polish-etat`).
- Récap projet complet donné en session (branché vs maquette + 4 blocs de next steps).
