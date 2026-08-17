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


engine = create_engine(
    _normalize_db_url(_settings.database_url),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
