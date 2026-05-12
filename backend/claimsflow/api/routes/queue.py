"""Exception and fraud queues — the killer pages of the dashboard."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from claimsflow.api.deps import db_session
from claimsflow.models import (
    Claim,
    ClaimSchema,
    ClaimStatus,
    Decision,
    DecisionSchema,
    Member,
    MemberSchema,
    Provider,
    ProviderSchema,
)

router = APIRouter(prefix="/api/v1/queue", tags=["queue"])


class QueueItem(BaseModel):
    claim: ClaimSchema
    decision: DecisionSchema | None
    member: MemberSchema
    provider: ProviderSchema
    sla_age_days: int
    priority: float


def _priority(claim: Claim, decision: Decision | None) -> float:
    """Higher = more urgent. Blend SLA age, amount, and (1 - confidence)."""
    age_days = max(0, (date.today() - claim.service_date).days)
    confidence = decision.confidence_score if decision else 0.5
    amount_weight = min(1.0, claim.total_billed / 50_000)
    return round(0.5 * (age_days / 14) + 0.3 * amount_weight + 0.2 * (1 - confidence), 3)


@router.get("/exceptions", response_model=list[QueueItem])
def exception_queue(
    session: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[QueueItem]:
    stmt = (
        select(Claim, Decision, Member, Provider)
        .join(Decision, Decision.claim_id == Claim.claim_id, isouter=True)
        .join(Member, Member.member_id == Claim.member_id)
        .join(Provider, Provider.provider_id == Claim.provider_id)
        .where(Claim.status == ClaimStatus.REVIEW.value)
    )
    rows = session.execute(stmt).all()
    items = [
        QueueItem(
            claim=ClaimSchema.model_validate(c),
            decision=DecisionSchema.model_validate(d) if d else None,
            member=MemberSchema.model_validate(m),
            provider=ProviderSchema.model_validate(p),
            sla_age_days=(date.today() - c.service_date).days,
            priority=_priority(c, d),
        )
        for c, d, m, p in rows
    ]
    items.sort(key=lambda i: i.priority, reverse=True)
    return items[:limit]


@router.get("/fraud", response_model=list[QueueItem])
def fraud_queue(
    session: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[QueueItem]:
    stmt = (
        select(Claim, Decision, Member, Provider)
        .join(Decision, Decision.claim_id == Claim.claim_id, isouter=True)
        .join(Member, Member.member_id == Claim.member_id)
        .join(Provider, Provider.provider_id == Claim.provider_id)
        .where(Claim.status == ClaimStatus.FRAUD_HOLD.value)
    )
    rows = session.execute(stmt).all()
    items = [
        QueueItem(
            claim=ClaimSchema.model_validate(c),
            decision=DecisionSchema.model_validate(d) if d else None,
            member=MemberSchema.model_validate(m),
            provider=ProviderSchema.model_validate(p),
            sla_age_days=(date.today() - c.service_date).days,
            priority=_priority(c, d),
        )
        for c, d, m, p in rows
    ]
    items.sort(key=lambda i: i.priority, reverse=True)
    return items[:limit]
