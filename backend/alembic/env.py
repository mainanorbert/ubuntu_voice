"""Alembic migration environment.

The database URL is resolved from env vars (EIVEN_SERVICE_URL or DATABASE_URL)
so no secrets are stored in alembic.ini.  All ORM models are imported through
``src.models`` to ensure Alembic can detect schema changes automatically.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure the project root (containing the ``src`` package) is on sys.path when
# Alembic is invoked from any working directory via ``uv run alembic ...``.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import engine_from_config, pool

from alembic import context

# -----------------------------------------------------------------
# Alembic Config object – provides access to values in alembic.ini
# -----------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -----------------------------------------------------------------
# Inject the database URL from the environment so alembic.ini
# never needs a hard-coded connection string.
# -----------------------------------------------------------------
_db_url = os.environ.get("EIVEN_SERVICE_URL") or os.environ.get("DATABASE_URL")
if _db_url:
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    config.set_main_option("sqlalchemy.url", _db_url)

# -----------------------------------------------------------------
# Import Base and all models so target_metadata is fully populated.
# The ``src.models`` import registers every ORM class on Base.metadata.
# -----------------------------------------------------------------
from src.core.database import Base  # noqa: E402
import src.models  # noqa: E402, F401

target_metadata = Base.metadata


# -----------------------------------------------------------------
# Offline mode: emit SQL to stdout without a live DB connection.
# -----------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations against a URL, emitting SQL without a DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------
# Online mode: run against a live connection.
# -----------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations with a live engine connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
