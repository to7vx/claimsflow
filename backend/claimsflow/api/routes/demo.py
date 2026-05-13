"""Demo-control endpoints: kick off a live batch and reset to seed state.

Gated by Settings.demo_mode — every handler 403s when demo_mode is false.
Both jobs share an in-process status registry so the dashboard can poll
GET /api/v1/demo/status to drive the "Running… N/10" button states.

ADD-ONLY: no pipeline or schema changes. Reuses process_claim() and
seed_database() exactly as the CLI does.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from claimsflow.core.config import get_settings
from claimsflow.core.db import Base, get_engine, get_session_factory
from claimsflow.core.logging import get_logger
from claimsflow.models import Claim, ClaimStatus, ClaimSubmission
from claimsflow.pipeline import process_claim
from claimsflow.seed import seed_database

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

DEMO_CLAIMS_DIR = Path(__file__).resolve().parents[4] / "demo_claims"

LIVE_SEQUENCE: list[tuple[str, str]] = [
    ("Clean approval", "01_clean_approval.json"),
    ("Clean approval variant", "01b_clean_approval.json"),
    ("Diagnosis mismatch", "02_mismatch_human_review.json"),
    ("Clean approval variant", "01c_clean_approval.json"),
    ("Routine visit", "03a_fraud_velocity.json"),
    ("Routine visit", "03b_fraud_velocity.json"),
    ("Routine visit", "03c_fraud_velocity.json"),
    ("Routine visit", "03d_fraud_velocity.json"),
    ("Routine visit", "03e_fraud_velocity.json"),
    ("Routine visit", "03f_fraud_velocity.json"),
]


# ── Shared job registry ───────────────────────────────────────────────

JobKind = Literal["run", "reset"]


class JobState(BaseModel):
    job_id: str
    kind: JobKind
    started_at: datetime
    finished_at: datetime | None = None
    total: int
    current: int = 0
    error: str | None = None

    @property
    def is_running(self) -> bool:
        return self.finished_at is None and self.error is None


_lock = Lock()
_current_job: JobState | None = None


def _set_job(job: JobState) -> None:
    global _current_job
    with _lock:
        _current_job = job


def _update_job(**kwargs: object) -> None:
    global _current_job
    with _lock:
        if _current_job is None:
            return
        for k, v in kwargs.items():
            setattr(_current_job, k, v)


def _finish_job(error: str | None = None) -> None:
    _update_job(finished_at=datetime.utcnow(), error=error)


# ── Guards ────────────────────────────────────────────────────────────


def require_demo_mode() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is disabled. Set DEMO_MODE=true to enable.",
        )


def require_idle() -> None:
    with _lock:
        if _current_job is not None and _current_job.is_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A {_current_job.kind} job is already in progress.",
            )


# ── Job bodies ────────────────────────────────────────────────────────


def _build_claim_from_payload(payload: ClaimSubmission) -> Claim:
    claim_id = f"CLM-{uuid.uuid4().hex[:10].upper()}"
    total = sum(li.quantity * li.unit_cost for li in payload.line_items)
    return Claim(
        claim_id=claim_id,
        claim_type=payload.claim_type.value,
        member_id=payload.member_id,
        provider_id=payload.provider_id,
        service_date=payload.service_date,
        submission_date=datetime.utcnow(),
        diagnosis_codes=payload.diagnosis_codes,
        procedure_codes=payload.procedure_codes,
        line_items=[li.model_dump() for li in payload.line_items],
        clinical_notes=payload.clinical_notes,
        total_billed=total,
        status=ClaimStatus.RECEIVED.value,
    )


async def _do_run_demo() -> None:
    """Submit the 10-claim live sequence with 2s gaps."""
    session = get_session_factory()()
    try:
        for i, (_, fname) in enumerate(LIVE_SEQUENCE, start=1):
            _update_job(current=i)
            path = DEMO_CLAIMS_DIR / fname
            if not path.exists():
                log.warning("demo.run.missing_file", file=str(path))
                continue
            payload = ClaimSubmission.model_validate_json(path.read_text(encoding="utf-8"))
            claim = _build_claim_from_payload(payload)
            session.add(claim)
            session.flush()
            try:
                await process_claim(session, claim.claim_id)
                session.commit()
            except Exception as exc:
                session.rollback()
                log.error("demo.run.claim_failure", claim_id=claim.claim_id, error=str(exc))
            if i < len(LIVE_SEQUENCE):
                await asyncio.sleep(2.0)
    finally:
        session.close()
    _finish_job()


async def _do_reset() -> None:
    """Drop + recreate tables, re-seed, adjudicate 25 sample claims.

    This is the in-process equivalent of:
        claimsflow init --reset && claimsflow seed --small && claimsflow demo --count 25
    """
    # Step 1: drop + recreate
    _update_job(current=1)
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    # Step 2: seed
    _update_job(current=2)
    session = get_session_factory()()
    try:
        seed_database(session, mode="small", random_seed=42)
        session.commit()
    finally:
        session.close()

    # Step 3: adjudicate 25 claims so the dashboard has decisions to show
    _update_job(current=3)
    session = get_session_factory()()
    try:
        claims = session.scalars(
            select(Claim).where(Claim.status == ClaimStatus.RECEIVED.value).limit(25)
        ).all()
        for c in claims:
            try:
                await process_claim(session, c.claim_id)
                session.commit()
            except Exception as exc:
                session.rollback()
                log.error("demo.reset.adjudicate_failure", claim_id=c.claim_id, error=str(exc))
    finally:
        session.close()
    _update_job(current=4)
    _finish_job()


# ── Endpoints ─────────────────────────────────────────────────────────


class StartResponse(BaseModel):
    job_id: str
    kind: JobKind


@router.post(
    "/run",
    response_model=StartResponse,
    dependencies=[Depends(require_demo_mode), Depends(require_idle)],
)
async def run_demo(background_tasks: BackgroundTasks) -> StartResponse:
    """Kick off the 10-claim live demo batch in the background."""
    job = JobState(
        job_id=uuid.uuid4().hex[:10],
        kind="run",
        started_at=datetime.utcnow(),
        total=len(LIVE_SEQUENCE),
    )
    _set_job(job)
    background_tasks.add_task(_run_with_guard, _do_run_demo)
    return StartResponse(job_id=job.job_id, kind="run")


@router.post(
    "/reset",
    response_model=StartResponse,
    dependencies=[Depends(require_demo_mode), Depends(require_idle)],
)
async def reset_demo(background_tasks: BackgroundTasks) -> StartResponse:
    """Drop tables, re-seed, adjudicate 25 sample claims — async."""
    job = JobState(
        job_id=uuid.uuid4().hex[:10],
        kind="reset",
        started_at=datetime.utcnow(),
        # 4 phases: drop/recreate, seed, adjudicate, done
        total=4,
    )
    _set_job(job)
    background_tasks.add_task(_run_with_guard, _do_reset)
    return StartResponse(job_id=job.job_id, kind="reset")


@router.get("/status", response_model=JobState | None, dependencies=[Depends(require_demo_mode)])
def demo_status() -> JobState | None:
    """Latest demo-control job state. Null if no job has run since startup."""
    with _lock:
        return _current_job


async def _run_with_guard(coro_fn) -> None:
    t0 = time.perf_counter()
    try:
        await coro_fn()
    except Exception as exc:  # pragma: no cover — defensive
        log.exception("demo.job_failed", error=str(exc))
        _finish_job(error=str(exc))
    finally:
        log.info("demo.job_complete", elapsed_s=round(time.perf_counter() - t0, 2))
