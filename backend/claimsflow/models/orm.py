"""SQLAlchemy 2.x ORM models.

One file for all entities — they reference each other and are small enough
that splitting per-entity costs more in import ceremony than it saves in
file size. If any of these grow past ~150 lines, split them.

Database-agnostic JSON storage uses `JSON` type which maps to JSONB on
Postgres and to TEXT-encoded JSON on SQLite. Timestamps are UTC and stored
as naive `DateTime` for SQLite compatibility — never store local time.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from claimsflow.core.db import Base


def _utcnow() -> datetime:
    """Naive UTC timestamp — consistent across SQLite and Postgres."""
    return datetime.utcnow()


# ─────────────────────────── Plan ───────────────────────────


class Plan(Base):
    __tablename__ = "plans"

    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False)
    covered_benefits: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    exclusions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    copay_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    coverage_tiers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    annual_limit_default: Mapped[float] = mapped_column(Float, nullable=False, default=100_000.0)

    members: Mapped[list[Member]] = relationship("Member", back_populates="plan")

    def __repr__(self) -> str:
        return f"<Plan {self.plan_id} {self.plan_name!r}>"


# ─────────────────────────── Member ───────────────────────────


class Member(Base):
    __tablename__ = "members"

    member_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    full_name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    full_name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    national_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.plan_id"), nullable=False)
    policy_start: Mapped[date] = mapped_column(Date, nullable=False)
    policy_end: Mapped[date] = mapped_column(Date, nullable=False)
    policy_status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    annual_limit: Mapped[float] = mapped_column(Float, nullable=False, default=100_000.0)
    used_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deductible: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deductible_met: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Self-referential dependents: dependent.primary_member_id -> primary.member_id
    primary_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("members.member_id"), nullable=True
    )

    plan: Mapped[Plan] = relationship("Plan", back_populates="members")
    dependents: Mapped[list[Member]] = relationship(
        "Member",
        backref="primary_member",
        remote_side="Member.member_id",
    )

    @property
    def remaining_limit(self) -> float:
        return max(0.0, self.annual_limit - self.used_amount)

    def __repr__(self) -> str:
        return f"<Member {self.member_id} {self.full_name_en!r}>"


# ─────────────────────────── Provider ───────────────────────────


class Provider(Base):
    __tablename__ = "providers"

    provider_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(16), nullable=False)
    network_tier: Mapped[str] = mapped_column(String(24), nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    license_number: Mapped[str] = mapped_column(String(48), nullable=False)
    license_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    contracted_rates: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    performance_score: Mapped[float] = mapped_column(Float, nullable=False, default=70.0)
    fraud_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)

    def __repr__(self) -> str:
        return f"<Provider {self.provider_id} {self.name_en!r}>"


# ─────────────────────────── Claim ───────────────────────────


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    claim_type: Mapped[str] = mapped_column(String(16), nullable=False)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.member_id"), nullable=False)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.provider_id"), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    submission_date: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    diagnosis_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    procedure_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_billed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="received")

    member: Mapped[Member] = relationship("Member")
    provider: Mapped[Provider] = relationship("Provider")
    decision: Mapped[Decision | None] = relationship(
        "Decision", back_populates="claim", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Claim {self.claim_id} status={self.status} billed={self.total_billed}>"


# ─────────────────────────── Decision ───────────────────────────


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"), nullable=False, unique=True
    )
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    decided_by: Mapped[str] = mapped_column(String(48), nullable=False, default="system")

    amount_approved: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    amount_denied: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    member_responsibility: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    policy_citations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    stage_results: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    eob_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    eob_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    claim: Mapped[Claim] = relationship("Claim", back_populates="decision")

    def __repr__(self) -> str:
        return f"<Decision {self.decision_id} {self.decision_type} confidence={self.confidence_score:.2f}>"


# ─────────────────────────── AuditLog ───────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    actor: Mapped[str] = mapped_column(String(48), nullable=False, default="system")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
