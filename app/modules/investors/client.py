"""Read-only access to the investor database (a separate Supabase project).

The whole dataset is ~10k rows across ten small tables, so rather than issuing
a dozen filtered queries per request we load it once and keep it in memory with
a TTL. A mapping request then costs zero network round-trips in the common case.

Strictly read-only: this app never writes to the investor database.
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

from app.config import get_settings
from app.errors import AppError

logger = logging.getLogger("axial.investors")

CACHE_TTL_SECONDS = 3600
_PAGE = 1000  # PostgREST caps a single response at 1000 rows

_TABLES = {
    "secteur": "id,nom,secteur_parent_id",
    "stade": "id,nom,ordre",
    "zone_geographique": "id,nom",
    "investisseur": "id,nom,type",
    "fonds": "investisseur_id,societe_gestion_id",
    "societe_gestion": "id,nom,site_web",
    "personne_morale_investisseur": "investisseur_id,nature",
    "investisseur_secteur": "investisseur_id,secteur_id",
    "investisseur_stade": "investisseur_id,stade_id",
    "investisseur_zone": "investisseur_id,zone_id",
}

_cache: dict | None = None
_cache_at: float = 0.0
_lock = threading.Lock()


def configured() -> bool:
    s = get_settings()
    return bool(s.investor_db_url and s.investor_db_key)


def _fetch_all(table: str, select: str) -> list[dict]:
    """Page through PostgREST (it returns at most 1000 rows per call)."""
    s = get_settings()
    base = s.investor_db_url.rstrip("/")
    headers = {"Authorization": f"Bearer {s.investor_db_key}", "apikey": s.investor_db_key}
    rows: list[dict] = []
    offset = 0
    with httpx.Client(timeout=30.0) as client:
        while True:
            r = client.get(
                f"{base}/rest/v1/{table}",
                params={"select": select, "limit": _PAGE, "offset": offset},
                headers=headers,
            )
            r.raise_for_status()
            page = r.json()
            rows.extend(page)
            if len(page) < _PAGE:
                return rows
            offset += _PAGE


def dataset(force: bool = False) -> dict:
    """The full investor dataset, cached in process for CACHE_TTL_SECONDS."""
    global _cache, _cache_at

    if not configured():
        raise AppError("Base investisseurs non configurée.", 503,
                       code="investors_unconfigured")

    with _lock:
        fresh = _cache is not None and (time.time() - _cache_at) < CACHE_TTL_SECONDS
        if fresh and not force:
            return _cache

        started = time.time()
        try:
            data = {t: _fetch_all(t, sel) for t, sel in _TABLES.items()}
        except Exception as e:
            if _cache is not None:
                # Serve slightly stale data rather than failing the request.
                logger.warning("Investor DB unreachable, serving cached data: %s", e)
                return _cache
            raise AppError("Base investisseurs injoignable.", 503,
                           code="investors_unavailable") from e

        _cache, _cache_at = data, time.time()
        logger.info("Investor dataset loaded in %.1fs (%d investisseurs, %d SGP)",
                    time.time() - started, len(data["investisseur"]),
                    len(data["societe_gestion"]))
        return _cache
