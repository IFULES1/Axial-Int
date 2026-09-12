"""Database access: SQLAlchemy 2.0 engine, session factory, and Base.

One engine for the app database. Alembic owns the schema (see alembic/).
Modules declare their ORM models against `Base`; nothing creates tables at
runtime — migrations do.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models across modules."""


_settings = get_settings()


def _normalize_db_url(url: str) -> str:
    """Force the psycopg v3 driver for Postgres URLs.

    Supabase hands out `postgresql://…` (and some tools `postgres://…`), which
    SQLAlchemy maps to psycopg2 by default — but we ship psycopg v3. Rewriting the
    scheme keeps SQLite URLs (dev) untouched.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def _options_de_pool(url: str) -> dict:
    """`pool_size` / `max_overflow` — seulement là où ils ont un sens.

    SQLite (dev, tests) tourne sur un `NullPool` ou un `SingletonThreadPool`
    qui n'acceptent pas ces arguments : les passer partout ferait échouer
    l'import du module. Ils ne concernent de toute façon que le QueuePool de
    PostgreSQL, seul endroit où le nombre de connexions se paie (voir
    `Settings.db_pool_size` : deux connexions par génération suivie).
    """
    if not url.startswith("postgresql"):
        return {}
    return {"pool_size": _settings.db_pool_size,
            "max_overflow": _settings.db_max_overflow}


_url = _normalize_db_url(_settings.database_url)

engine = create_engine(
    _url,
    pool_pre_ping=True,
    future=True,
    **_options_de_pool(_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
