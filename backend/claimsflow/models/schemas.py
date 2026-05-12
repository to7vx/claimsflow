"""Pydantic schemas — API request/response shapes.

These mirror the ORM models but exist independently. Two reasons:
1. The wire format and storage format diverge over time; pinning them
   together is a long-term mistake.
2. Pydantic v2 validates input at the boundary; ORM models trust their
   data because it already passed through here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from claimsflow.models.enums import (
    ClaimStatus,
    ClaimType,
    DecisionType,
    Gender,
    NetworkTier,
    PolicyStatus,
    ProviderType,
)


class _BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# ─────────────────────────── Plan ───────────────────────────


class PlanSchema(_BaseSchema):
    plan_id: str
    plan_name: str
    covered_benefits: list[str]
    exclusions: list[str]
    copay_percent: float
    coverage_tiers: dict[str, Any]
    annual_limit_default: float


# ─────────────────────────── Member ───────────────────────────


class MemberSchema(_BaseSchema):
    member_id: str
    full_name_en: str
    full_name_ar: str
    national_id: str
    dob: date
    gender: Gender
    plan_id: str
    policy_start: date
    policy_end: date
    policy_status: PolicyStatus
    annual_limit: float
    used_amount: float
    deductible: float
    deductible_met: float
    primary_member_id: str | None = None


# ─────────────────────────── Provider ───────────────────────────


class ProviderSchema(_BaseSchema):
    provider_id: str
    name_en: str
    name_ar: str
    provider_type: ProviderType
    network_tier: NetworkTier
    city: str
    license_number: str
    license_expiry: date
    contracted_rates: dict[str, float]
    performance_score: float
    fraud_risk_score: float


# ─────────────────────────── Claim ───────────────────────────


class LineItem(BaseModel):
    code: str
    description: str
    quantity: int = Field(ge=1, default=1)
    unit_cost: float = Field(ge=0)

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_cost


class ClaimSubmission(BaseModel):
    """Request body for POST /claims/submit. Claim ID is server-assigned."""

    claim_type: ClaimType
    member_id: str
    provider_id: str
    service_date: date
    diagnosis_codes: list[str] = Field(min_length=1)
    procedure_codes: list[str] = Field(min_length=1)
    line_items: list[LineItem] = Field(min_length=1)
    clinical_notes: str | None = None


class ClaimSchema(_BaseSchema):
    claim_id: str
    claim_type: ClaimType
    member_id: str
    provider_id: str
    service_date: date
    submission_date: datetime
    diagnosis_codes: list[str]
    procedure_codes: list[str]
    line_items: list[dict[str, Any]]
    clinical_notes: str | None = None
    total_billed: float
    status: ClaimStatus


# ─────────────────────────── Decision ───────────────────────────


class DecisionSchema(_BaseSchema):
    decision_id: str
    claim_id: str
    decision_type: DecisionType
    decided_at: datetime
    decided_by: str
    amount_approved: float
    amount_denied: float
    member_responsibility: float
    confidence_score: float
    reasoning: str
    policy_citations: list[str]
    flags: list[str]
    stage_results: dict[str, Any]
    eob_en: str | None = None
    eob_ar: str | None = None


class ClaimWithDecision(BaseModel):
    """Combined response for GET /claims/{id}."""

    claim: ClaimSchema
    decision: DecisionSchema | None
