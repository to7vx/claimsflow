"""Module 2 — smoke tests for domain models.

Proves:
1. All ORM classes import and register with Base.metadata
2. The metadata produces a valid SQL schema on an in-memory SQLite DB
3. Pydantic schemas accept canonical example data
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from claimsflow.core.db import Base
from claimsflow.models import (
    AuditEventType,
    AuditLog,
    Claim,
    ClaimSubmission,
    ClaimType,
    Decision,
    DecisionType,
    Gender,
    LineItem,
    Member,
    NetworkTier,
    Plan,
    PolicyStatus,
    Provider,
    ProviderType,
)


@pytest.fixture()
def in_memory_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_metadata_contains_all_tables() -> None:
    expected = {"plans", "members", "providers", "claims", "decisions", "audit_logs"}
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_can_persist_full_claim_chain(in_memory_session: Session) -> None:
    session = in_memory_session

    plan = Plan(
        plan_id="P001",
        plan_name="Gold Family",
        covered_benefits=["outpatient", "inpatient"],
        exclusions=["F.*"],  # mental health exclusion example
        copay_percent=10.0,
        coverage_tiers={"preferred": 100, "standard": 80},
        annual_limit_default=200_000.0,
    )
    member = Member(
        member_id="M0001",
        full_name_en="Mohammed Al-Saud",
        full_name_ar="محمد آل سعود",
        national_id="1234567890",
        dob=date(1985, 3, 14),
        gender=Gender.MALE.value,
        plan_id="P001",
        policy_start=date(2026, 1, 1),
        policy_end=date(2026, 12, 31),
        policy_status=PolicyStatus.ACTIVE.value,
        annual_limit=200_000.0,
    )
    provider = Provider(
        provider_id="PR001",
        name_en="Riyadh Specialist Hospital",
        name_ar="مستشفى الرياض التخصصي",
        provider_type=ProviderType.HOSPITAL.value,
        network_tier=NetworkTier.PREFERRED.value,
        city="Riyadh",
        license_number="MOH-RHU-001",
        license_expiry=date(2027, 6, 30),
        contracted_rates={"99213": 250.0, "80050": 180.0},
    )
    claim = Claim(
        claim_id="C00001",
        claim_type=ClaimType.OUTPATIENT.value,
        member_id="M0001",
        provider_id="PR001",
        service_date=date(2026, 5, 1),
        diagnosis_codes=["E11.9"],
        procedure_codes=["99213", "80050"],
        line_items=[
            {"code": "99213", "description": "Office visit", "quantity": 1, "unit_cost": 250.0},
            {"code": "80050", "description": "General health panel", "quantity": 1, "unit_cost": 180.0},
        ],
        total_billed=430.0,
    )
    decision = Decision(
        decision_id="D00001",
        claim_id="C00001",
        decision_type=DecisionType.AUTO_APPROVE.value,
        amount_approved=387.0,
        member_responsibility=43.0,
        confidence_score=0.94,
        reasoning="All checks passed. Procedure set is clinically appropriate for E11.9.",
        policy_citations=["Plan P001 §4.2 outpatient coverage"],
        flags=[],
    )
    audit = AuditLog(
        claim_id="C00001",
        event_type=AuditEventType.DECISION_RENDERED.value,
        event_data={"decision_type": "auto_approve"},
    )

    session.add_all([plan, member, provider, claim, decision, audit])
    session.commit()

    fetched = session.get(Claim, "C00001")
    assert fetched is not None
    assert fetched.decision is not None
    assert fetched.decision.decision_type == DecisionType.AUTO_APPROVE.value
    assert fetched.member.full_name_ar == "محمد آل سعود"
    assert fetched.member.remaining_limit == 200_000.0


def test_pydantic_claim_submission_validates() -> None:
    submission = ClaimSubmission(
        claim_type=ClaimType.OUTPATIENT,
        member_id="M0001",
        provider_id="PR001",
        service_date=date(2026, 5, 1),
        diagnosis_codes=["E11.9"],
        procedure_codes=["99213"],
        line_items=[
            LineItem(code="99213", description="Office visit", quantity=1, unit_cost=250.0),
        ],
    )
    assert submission.line_items[0].line_total == 250.0
    assert submission.claim_type == ClaimType.OUTPATIENT.value


def test_pydantic_rejects_empty_line_items() -> None:
    with pytest.raises(ValueError):
        ClaimSubmission(
            claim_type=ClaimType.OUTPATIENT,
            member_id="M0001",
            provider_id="PR001",
            service_date=date(2026, 5, 1),
            diagnosis_codes=["E11.9"],
            procedure_codes=["99213"],
            line_items=[],
        )


def test_decision_repr_includes_confidence() -> None:
    d = Decision(
        decision_id="D1",
        claim_id="C1",
        decision_type=DecisionType.HUMAN_REVIEW.value,
        confidence_score=0.72,
    )
    assert "0.72" in repr(d)
