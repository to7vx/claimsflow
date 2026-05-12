"""SQLAlchemy engine + session factory.

Single source of truth for the database connection. The engine is lazily
constructed so tests can override DATABASE_URL before it materializes.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from claimsflow.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    connect_args: dict[str, object] = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, future=True, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def session_scope() -> Iterator[Session]:
    """FastAPI / CLI dependency. Yields a session, commits on success, rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
