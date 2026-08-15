# Snapshot de session — 2026-08-10 (récap complet)

Récap consolidé de toute la session. Détails par jalon dans les snapshots
horodatés (17-59, 18-10, 18-30).

## Objectif global de la session
Reprendre la main sur Axial Intelligence (ex insight-map), stabiliser la prod,
puis démarrer la reconstruction from scratch en monolithe modulaire. Réflexe
demandé : snapshots réguliers.

## Fil de la session (chronologique)
1. **Accès VPS rétabli** — clé SSH `~/.ssh/hostinger_vps` + raccourci `ssh hostinger`
   (root@72.62.25.156, srv1195764). L'utilisateur a ajouté la clé publique via hPanel.
2. **Audit sécurité VPS** — pare-feu Hostinger amont OK (DB/Qdrant/services filtrés
   depuis internet ; ouverts : 22/80/443/8000/8080/8443). À durcir (NON fait) :
   SSH root+password + brute-force actif + pas de fail2ban ; `.env` en 644 ; `.env.bak`.
3. **Bug "API Anthropic KO" résolu en prod** — modèle `claude-sonnet-4-20250514` périmé
   (EOL 15/06/2026 → 404). Remplacé par `claude-sonnet-5` dans `/opt/insight-map/.env`
   + `docker-compose.axial.yml`, conteneurs **recréés** (up -d --force-recreate, pas restart).
4. **Bug "recherche web via Claude indispo" diagnostiqué** — vraie cause = clé Perplexity
   `pplx-C3R...` en **quota dépassé (401)** ; fuite dans 10 .md du repo. Utilisateur gère.
5. **Plan de reconstruction approuvé** — `/Users/mirad/.claude/plans/propose-un-plan-pour-snoopy-meteor.md`.
6. **Build P0 → P2** du nouveau monolithe `/Users/mirad/axial-intelligence` (voir ci-dessous).

## Décisions verrouillées
- Nom = **Axial Intelligence**.
- Archi = **monolithe modulaire** (1 API FastAPI + 1 worker + 1 sidecar PII), remplace 11 microservices.
- Auth = `POST /auth/register {email,password}`, **freemail + onboarding conservés**, **UUID partout** (fin du double id).
- Données existantes **conservées** (reconnexion sans reset) → migration en P7.
- **Nouveau projet Supabase analytics** (first/last seen, quota, KPI JSONB, RLS) — hébergement DIFFÉRÉ.
- Stack = FastAPI + SQLAlchemy 2.0 + Alembic + pydantic-settings + Next.js ; `llm_client` provider-agnostique.
- UX **mobile responsive** obligatoire.
- Spec produit V1 (3 modes Workspace/Agents PESTEL+Porter/Rapports + Mémoire + Crédits 5 plans) = contrat fonctionnel.

## Build livré : P0 + P1 + P2 (dans ~/axial-intelligence)
- **P0 Socle** : structure modules, config pydantic-settings (fail-fast), db SQLAlchemy 2.0 + Alembic,
  errors (AppError + handler global), health + /health/providers, Makefile, docker-compose (localhost only),
  .env.example, .gitignore, README. venv Python 3.13.
- **P1 Auth + Analytics** : module auth (freemail porté, JWT HS256 local, register/login/me, identité UUID) ;
  module analytics (client fire-and-forget no-op si non configuré + schema.sql tables+RLS) ; scripts/seed_users.py.
- **P2 Documents + RAG** : module documents (upload/extract PDF/chunk 1000-200/cascade delete) ;
  module rag (embeddings OpenAI 1536 avec 503 si pas de clé, Qdrant COSINE, search filtré user) ;
  migration alembic 0001_documents.

## État vérifiable
- `cd ~/axial-intelligence && .venv/bin/pytest -q` → **10 passed**.
- `.venv/bin/ruff check app worker tests scripts` → clean.
- `.venv/bin/alembic history` → `<base> -> 0001_documents (head)`.
- Endpoints : /health, /health/providers, /auth/{register,login,me}, /documents{,/upload,/{id}}, /rag/search.

## ⚠️ SUJETS OUVERTS — NE PAS CLORE (rappel utilisateur)
- Hébergement analytics (co-localisation schéma / Pro ~25$ / pause projet).
- Brancher un Supabase de dev pour tester auth + ingestion e2e.
- Périmètre/choix du rebuild restent discutables.

## Important : le RAG livré est VIDE
Aucun document seedé/pré-chargé. Corpus alimenté uniquement par upload utilisateur.
Les documents de la prod (Qdrant du VPS) NE sont PAS migrés → relève de P7.
Aucune ingestion lancée cette session (Docker était indispo).

## Prochaines étapes
1. **P3 — Analysis + llm_client** (cœur "faire tourner l'algo") : run_analysis unique, provider LLM
   abstrait (Perplexity web + Claude enrich), enrichisseurs optionnels à dégradation propre, SSE,
   portage templates (insight-map: rag-service/app/prompts/templates.py + backend-service call_perplexity).
2. Docker up → `make up && make migrate` → tests ingestion e2e avec vraies clés.
3. Trancher les sujets ouverts.
4. (Prod, séparé) durcir SSH + chmod 600 .env + révoquer clé Perplexity fuitée.

## Rappels techniques
- Prod : `ssh hostinger`. Après modif .env : `docker compose up -d --force-recreate <svc>` (restart ne relit pas .env).
  agent-service dans docker-compose.axial.yml (recréer avec -f docker-compose.yml -f docker-compose.axial.yml).
- Modèles Claude valides testés : claude-sonnet-5 / claude-opus-4-8 / claude-haiku-4-5-20251001.
- Supabase org id : ruoxgzvfqdhnuzkvmymg (limite 2 projets actifs gratuits atteinte).
