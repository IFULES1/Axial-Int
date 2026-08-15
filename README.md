# Axial Intelligence

Strategic-intelligence platform — a **modular monolith** rebuild of the former
`insight-map` microservices stack. One FastAPI app, one worker, one PII sidecar.

## What it does

Users ask business questions (market, competitors, fundraising, GTM) and get
**sourced, structured reports** combining internal documents (RAG), real-time
web search (Perplexity), and optional enrichers (Pappers, INSEE, Serper, Claude).

Three work modes: **Workspace** (free chat), **Strategic Agents** (Market
Scanner/PESTEL + Competitor Radar/Porter), and **Reports** (PDF archive), over a
transverse **Memory** layer and a **credits** system.

## Architecture

```
Next.js frontend  →  FastAPI API (modular monolith)  →  Postgres + Qdrant
                         │                                  ↑
                         ├─ worker (scheduled agents/watches)
                         └─ PII sidecar (Presidio)
        External: Perplexity · OpenAI embeddings · Stripe · SMTP
```

Modules live under `app/modules/`: `auth`, `analytics`, `documents`, `rag`,
`analysis`, `intelligence`, `billing`, `reports`, `pii`. Shared plumbing under
`app/shared/` (`llm_client`, `health`, …). Schema is owned by Alembic.

## Quickstart

```bash
make install       # create venv + install deps
cp .env.example .env   # then fill in secrets
make up            # start postgres + qdrant (local, localhost-only)
make migrate       # apply DB migrations
make run           # API on http://localhost:8080
```

Health checks: `GET /health` and `GET /health/providers` (real state of every
external dependency).

## Build phases

See `/Users/mirad/.claude/plans/…` (approved plan). P0 socle → P1 auth+analytics
→ P2 documents+RAG → P3 analysis → P4 intelligence → P5 billing+reports →
P6 worker+PII → P7 migration & cutover.

## Conventions

- Config: everything in `app/config.py` (validated at startup, fail-fast).
- Errors: raise `AppError`; never bare `except`.
- Identity: **UUID everywhere** (no legacy integer IDs).
- Security: single public surface (the API); secrets never committed.
