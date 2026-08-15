"""Unified error handling.

A single exception type (`AppError`) for expected, client-facing failures and
one global handler that turns any unhandled exception into a clean JSON error
without leaking internals. No bare `except:` anywhere in the codebase.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("axial")


class AppError(Exception):
    """Expected, user-facing error. Carries an HTTP status and safe message."""

    def __init__(self, message: str, status_code: int = 400, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or "app_error"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback server-side; return an opaque message to clients.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Erreur interne."}},
        )
