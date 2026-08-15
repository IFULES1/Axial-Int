"""Alembic environment.

Pulls the database URL from validated app settings and uses the shared
`Base.metadata` for autogenerate. Model modules are imported here so their
tables are registered before autogenerate runs.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import Base

# Import model modules so they register on Base.metadata.
# (Added as each module defines its models across the build phases.)
from app.modules.auth import models as _auth_models  # noqa: E402, F401
from app.modules.billing import models as _billing_models  # noqa: E402, F401
from app.modules.documents import models as _documents_models  # noqa: E402, F401
from app.modules.intelligence import models as _intelligence_models  # noqa: E402, F401
from app.modules.memory import models as _memory_models  # noqa: E402, F401
from app.modules.reports import models as _reports_models  # noqa: E402, F401
from app.modules.watches import models as _watches_models  # noqa: E402, F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
