"""PostgreSQL pgvector extension bootstrap for Aiven and other Postgres hosts."""

from sqlalchemy import Engine, text


def database_url_is_postgresql(database_url: str) -> bool:
    """Return True when the SQLAlchemy URL targets PostgreSQL (not SQLite)."""
    normalized = database_url.strip().lower()
    return normalized.startswith("postgresql") or normalized.startswith("postgres+")


def ensure_pgvector_extension(engine: Engine) -> None:
    """Enable the pgvector extension if the server is PostgreSQL.

    Aiven PostgreSQL supports the ``vector`` extension; enable it in the service
    console if ``CREATE EXTENSION`` is not permitted for the application role.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
