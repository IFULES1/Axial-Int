"""Axial Intelligence — application entrypoint.

A single modular-monolith FastAPI app. Each business capability lives in its own
module under app/modules/ and exposes an APIRouter that is mounted here. The
same codebase runs the API and (via worker/) the scheduled jobs.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.shared.health import providers_summary

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="Axial Intelligence API",
    version="1.0.0",
    description="Strategic intelligence platform — modular monolith.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "axial-intelligence", "version": app.version}


@app.get("/health/providers", tags=["health"])
def health_providers() -> dict:
    """Real configuration state of every external dependency."""
    return providers_summary()


# --- Module routers ------------------------------------------------------
# Each module is mounted as it is implemented across the build phases (P1..P6).
# Importing here keeps a single, readable wiring point.
def _mount_routers() -> None:
    from app.modules.analysis.router import router as analysis_router
    from app.modules.auth.router import router as auth_router
    from app.modules.billing.router import router as billing_router
    from app.modules.documents.router import router as documents_router
    from app.modules.intelligence.router import router as intelligence_router
    from app.modules.memory.router import router as memory_router
    from app.modules.rag.router import router as rag_router
    from app.modules.reports.router import router as reports_router
    from app.modules.watches.router import router as watches_router
    from app.modules.investors.router import router as investors_router

    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(rag_router)
    app.include_router(analysis_router)
    app.include_router(intelligence_router)
    app.include_router(billing_router)
    app.include_router(reports_router)
    app.include_router(memory_router)
    app.include_router(watches_router)
    app.include_router(investors_router)


_mount_routers()
