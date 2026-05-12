"""FastAPI dependencies — session, API key auth, settings.

Keep dependencies thin. Anything that involves real logic belongs in
the route handler or the pipeline, not here.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from claimsflow.core.config import Settings, get_settings
from claimsflow.core.db import get_session_factory


def db_session() -> Iterator[Session]:
    """Per-request DB session. Commits on success; rolls back on exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Guard write endpoints. Read endpoints stay public for the demo."""
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )
