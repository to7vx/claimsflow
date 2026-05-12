"""Provider insights — top providers by volume or fraud risk."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from claimsflow.api.deps import db_session
from claimsflow.models import Claim, Provider

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


class ProviderInsight(BaseModel):
    provider_id: str
    name_en: str
    city: str
    network_tier: str
    fraud_risk_score: float
    claim_count: int
    total_billed: float


@router.get("/top", response_model=list[ProviderInsight])
def top_providers(
    session: Session = Depends(db_session),
    metric: Literal["volume", "risk"] = Query(default="volume"),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[ProviderInsight]:
    counts_stmt = (
        select(
            Claim.provider_id,
            func.count().label("n"),
            func.coalesce(func.sum(Claim.total_billed), 0).label("billed"),
        )
        .group_by(Claim.provider_id)
    )
    aggregates = {pid: (n, billed) for pid, n, billed in session.execute(counts_stmt).all()}

    providers = session.scalars(select(Provider)).all()
    rows: list[ProviderInsight] = []
    for p in providers:
        n, billed = aggregates.get(p.provider_id, (0, 0.0))
        rows.append(ProviderInsight(
            provider_id=p.provider_id,
            name_en=p.name_en,
            city=p.city,
            network_tier=p.network_tier,
            fraud_risk_score=p.fraud_risk_score,
            claim_count=int(n),
            total_billed=float(billed),
        ))

    if metric == "risk":
        rows.sort(key=lambda r: r.fraud_risk_score, reverse=True)
    else:
        rows.sort(key=lambda r: r.claim_count, reverse=True)
    return rows[:limit]
