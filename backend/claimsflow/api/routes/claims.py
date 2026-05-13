"""Claim submission, lookup, list, and human-review override."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from claimsflow.api.deps import db_session, require_api_key
from claimsflow.core.db import get_session_factory
from claimsflow.core.logging import get_logger
from claimsflow.models import (
    AuditLog,
    Claim,
    ClaimSchema,
    ClaimStatus,
    ClaimSubmission,
    ClaimWithDecision,
    Decision,
    DecisionSchema,
    DecisionType,
)
from claimsflow.models.enums import AuditEventType
from claimsflow.pipeline import process_claim

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


class SubmitResponse(BaseModel):
    claim_id: str
    status: str
    eta_seconds: int


class ReviewRequest(BaseModel):
    decision: str  # "approve" | "deny"
    reviewer_id: str
    notes: str | None = None


class ClaimListResponse(BaseModel):
    items: list[ClaimSchema]
    page: int
    page_size: int
    total: int


class RecentClaimItem(BaseModel):
    """Compact row for the dashboard's Live Activity panel."""

    claim_id: str
    submission_date: datetime
    total_billed: float
    status: str
    decision_type: str | None
    decided_at: datetime | None
    confidence_score: float | None


@router.post(
    "/submit",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
)
def submit_claim(
    payload: ClaimSubmission,
    background_tasks: BackgroundTasks,
    session: Session = Depends(db_session),
) -> SubmitResponse:
    """Accept a new claim, kick off pipeline processing in the background."""
    claim_id = f"CLM-{uuid.uuid4().hex[:10].upper()}"
    total_billed = sum(li.quantity * li.unit_cost for li in payload.line_items)
    claim = Claim(
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
        total_billed=total_billed,
        status=ClaimStatus.RECEIVED.value,
    )
    session.add(claim)
    # Force commit before scheduling background work — the worker opens its own session.
    session.flush()

    background_tasks.add_task(_process_in_background, claim_id)
    log.info("claim.accepted", claim_id=claim_id, billed=total_billed)
    return SubmitResponse(claim_id=claim_id, status="processing", eta_seconds=10)


async def _process_in_background(claim_id: str) -> None:
    """Open a fresh session and run the pipeline. Logs failures but doesn't raise."""
    session = get_session_factory()()
    try:
        await process_claim(session, claim_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        log.error("claim.background_failure", claim_id=claim_id, error=str(exc))
    finally:
        session.close()


@router.get("/recent", response_model=list[RecentClaimItem])
def recent_claims(
    session: Session = Depends(db_session),
    limit: int = Query(default=5, ge=1, le=50),
) -> list[RecentClaimItem]:
    """Most recently submitted claims with their latest decision joined.

    Powers the dashboard's Live Activity panel. Ordered by submission_date desc.
    """
    rows = session.scalars(
        select(Claim).order_by(Claim.submission_date.desc()).limit(limit)
    ).all()
    out: list[RecentClaimItem] = []
    for c in rows:
        dec = session.scalars(
            select(Decision).where(Decision.claim_id == c.claim_id)
        ).one_or_none()
        out.append(
            RecentClaimItem(
                claim_id=c.claim_id,
                submission_date=c.submission_date,
                total_billed=c.total_billed,
                status=c.status,
                decision_type=dec.decision_type if dec else None,
                decided_at=dec.decided_at if dec else None,
                confidence_score=dec.confidence_score if dec else None,
            )
        )
    return out


@router.get("/{claim_id}", response_model=ClaimWithDecision)
def get_claim(claim_id: str, session: Session = Depends(db_session)) -> ClaimWithDecision:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"claim {claim_id} not found")
    decision = session.scalars(
        select(Decision).where(Decision.claim_id == claim_id)
    ).one_or_none()
    return ClaimWithDecision(
        claim=ClaimSchema.model_validate(claim),
        decision=DecisionSchema.model_validate(decision) if decision else None,
    )


@router.get("", response_model=ClaimListResponse)
def list_claims(
    session: Session = Depends(db_session),
    status_filter: str | None = Query(default=None, alias="status"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> ClaimListResponse:
    stmt = select(Claim).order_by(Claim.submission_date.desc())
    if status_filter:
        stmt = stmt.where(Claim.status == status_filter)
    if from_:
        stmt = stmt.where(Claim.submission_date >= from_)
    if to:
        stmt = stmt.where(Claim.submission_date <= to)

    total = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(stmt.subquery()))
    rows = session.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
    return ClaimListResponse(
        items=[ClaimSchema.model_validate(c) for c in rows],
        page=page,
        page_size=limit,
        total=total or 0,
    )


@router.post(
    "/{claim_id}/review",
    response_model=DecisionSchema,
    dependencies=[Depends(require_api_key)],
)
def override_decision(
    claim_id: str,
    payload: ReviewRequest,
    session: Session = Depends(db_session),
) -> DecisionSchema:
    """Human reviewer overrides the AI's decision. Every override is logged."""
    if payload.decision not in ("approve", "deny"):
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'deny'")

    decision = session.scalars(
        select(Decision).where(Decision.claim_id == claim_id)
    ).one_or_none()
    if decision is None:
        raise HTTPException(status_code=404, detail=f"no decision for claim {claim_id}")

    new_type = (
        DecisionType.AUTO_APPROVE.value if payload.decision == "approve"
        else DecisionType.AUTO_DENY.value
    )
    previous = decision.decision_type
    decision.decision_type = new_type
    decision.decided_by = payload.reviewer_id
    decision.decided_at = datetime.utcnow()
    decision.flags = sorted({*decision.flags, "human_override"})

    claim = session.get(Claim, claim_id)
    if claim is not None:
        claim.status = (
            ClaimStatus.APPROVED.value if payload.decision == "approve"
            else ClaimStatus.DENIED.value
        )

    session.add(AuditLog(
        claim_id=claim_id,
        event_type=AuditEventType.HUMAN_OVERRIDE.value,
        actor=payload.reviewer_id,
        event_data={
            "from": previous,
            "to": new_type,
            "notes": payload.notes,
        },
    ))
    log.info("claim.human_override", claim_id=claim_id, reviewer=payload.reviewer_id)
    return DecisionSchema.model_validate(decision)
