"""FastAPI dependency providers."""

from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from openai import AsyncOpenAI
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import Settings
from src.core.database import create_database_engine, create_session_factory
from src.services.openrouter_agent import create_openrouter_async_client


@lru_cache
def get_settings() -> Settings:
    """Return process-wide settings (env-backed, cached)."""
    return Settings()


@lru_cache
def get_database_engine(database_url: str) -> Engine:
    """Return the singleton SQLAlchemy engine, cached by URL."""
    return create_database_engine(database_url)


@lru_cache
def _get_session_factory(database_url: str) -> sessionmaker[Session]:
    """Return the singleton session factory, cached by URL."""
    engine = get_database_engine(database_url)
    return create_session_factory(engine)


def clear_database_caches() -> None:
    """Clear LRU caches used by database and settings singletons (for tests)."""
    get_settings.cache_clear()
    get_database_engine.cache_clear()
    _get_session_factory.cache_clear()


def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Generator[Session, None, None]:
    """Yield a request-scoped database session, closed when the request completes."""
    factory = _get_session_factory(settings.database_url)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_openrouter_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncOpenAI:
    """Return an AsyncOpenAI client configured for OpenRouter."""
    return create_openrouter_async_client(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
