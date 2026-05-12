"""Health + version endpoints. Kept dead simple — they're polled by docker
healthchecks and uptime monitors, not by humans."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from claimsflow import __version__
from claimsflow.api.deps import db_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/healthz/db")
def healthz_db(session: Session = Depends(db_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"db": "ok"}
