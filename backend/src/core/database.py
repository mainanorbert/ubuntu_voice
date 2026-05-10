"""Database engine, session factory, and declarative base."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def create_database_engine(database_url: str) -> Engine:
    """Create the shared SQLAlchemy engine for the application."""
    return create_engine(database_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the session factory used by request-scoped dependencies."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
