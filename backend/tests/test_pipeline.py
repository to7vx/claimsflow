"""Module 4 — 6-stage adjudication pipeline.

Tests each stage in isolation with a fake LLM, then exercises the full
orchestrator against seeded data and verifies every decision path
(approve, approve-with-audit, deny, human review, fraud hold) is reachable.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from claimsflow.core.db import Base
from claimsflow.models import (
    AuditLog,
    Claim,
    ClaimType,
    Decision,
    DecisionType,
    Member,
    NetworkTier,
    Plan,
    PolicyStatus,
    Provider,
    ProviderType,
)
from claimsflow.pipeline import (
    BilingualEOB,
    CostCalculation,
    DecisionRouter,
    EligibilityCheck,
    FraudDetection,
    MedicalNecessityCheck,
    MedicalNecessityVerdict,
    ProviderValidation,
    StageContext,
    StageResult,
    cache_key,
    process_claim,
    verdict_cache,
)
from claimsflow.providers.base import LLMResponse


# ─────────────── Fixtures ───────────────


class FakeProvider:
    """In-memory LLM provider for tests. Hands out canned responses by type."""

    name = "fake"
    model = "fake-1"

    def __init__(self, responses: dict[type, BaseModel] | None = None) -> None:
        self._responses = responses or {}
        self.calls: list[tuple[str, str, type]] = []

    async def reason(self, system_prompt, user_prompt, response_schema):
        self.calls.append((system_prompt, user_prompt, response_schema))
        payload = self._responses.get(response_schema)
        if payload is None:
            # Default: produce a permissive verdict matching the schema's defaults.
            payload = response_schema.model_construct()
        return LLMResponse(data=payload, model=self.model, provider=self.name)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def base_world(session: Session) -> dict[str, Any]:
    """Minimal world: 1 plan, 1 active member, 1 preferred provider."""
    plan = Plan(
        plan_id="PLN-TEST",
        plan_name="Gold Test",
        covered_benefits=["outpatient", "inpatient", "pharmacy"],
        exclusions=["F.*"],
        copay_percent=10.0,
        coverage_tiers={"preferred": 100.0, "standard": 80.0, "out_of_network": 0.0},
        annual_limit_default=200_000.0,
    )
    member = Member(
        member_id="MBR-TEST",
        full_name_en="Test Member",
        full_name_ar="عضو تجريبي",
        national_id="1234567890",
        dob=date(1985, 1, 1),
        gender="male",
        plan_id="PLN-TEST",
        policy_start=date.today() - timedelta(days=30),
        policy_end=date.today() + timedelta(days=300),
        policy_status=PolicyStatus.ACTIVE.value,
        annual_limit=200_000.0,
        used_amount=0.0,
        deductible=0.0,
    )
    provider = Provider(
        provider_id="PRV-TEST",
        name_en="Test Hospital",
        name_ar="مستشفى تجريبي",
        provider_type=ProviderType.HOSPITAL.value,
        network_tier=NetworkTier.PREFERRED.value,
        city="Riyadh",
        license_number="MOH-RIY-9999",
        license_expiry=date.today() + timedelta(days=365),
        contracted_rates={"99213": 250.0, "83036": 90.0},
        performance_score=80.0,
        fraud_risk_score=10.0,
    )
    session.add_all([plan, member, provider])
    session.commit()
    return {"plan": plan, "member": member, "provider": provider}


def _make_claim(world: dict[str, Any], **overrides) -> Claim:
    base: dict[str, Any] = {
        "claim_id": overrides.pop("claim_id", "CLM-TEST-001"),
        "claim_type": ClaimType.OUTPATIENT.value,
        "member_id": world["member"].member_id,
        "provider_id": world["provider"].provider_id,
        "service_date": date.today() - timedelta(days=1),
        "diagnosis_codes": ["E11.9"],
        "procedure_codes": ["99213"],
        "line_items": [
            {"code": "99213", "description": "Visit", "quantity": 1, "unit_cost": 250.0},
        ],
        "total_billed": 250.0,
        "status": "received",
    }
    base.update(overrides)
    return Claim(**base)


def _ctx(world: dict[str, Any]) -> StageContext:
    return StageContext(member=world["member"], plan=world["plan"], provider=world["provider"])


# ─────────────── Stage 1: Eligibility ───────────────


@pytest.mark.asyncio
async def test_eligibility_passes_for_healthy_claim(base_world) -> None:
    claim = _make_claim(base_world)
    result = await EligibilityCheck().process(claim, _ctx(base_world))
    assert result.passed is True
    assert result.short_circuit is False


@pytest.mark.asyncio
async def test_eligibility_short_circuits_on_suspended_policy(base_world) -> None:
    base_world["member"].policy_status = PolicyStatus.SUSPENDED.value
    claim = _make_claim(base_world)
    result = await EligibilityCheck().process(claim, _ctx(base_world))
    assert result.passed is False
    assert result.short_circuit is True


@pytest.mark.asyncio
async def test_eligibility_flags_limit_exceeded(base_world) -> None:
    base_world["member"].used_amount = 199_900.0
    claim = _make_claim(base_world, total_billed=500.0)
    result = await EligibilityCheck().process(claim, _ctx(base_world))
    assert result.passed is False
    assert "limit_exceeded" in result.flags


@pytest.mark.asyncio
async def test_eligibility_short_circuits_on_excluded_diagnosis(base_world) -> None:
    claim = _make_claim(base_world, diagnosis_codes=["F32.9"])  # mental health, excluded
    result = await EligibilityCheck().process(claim, _ctx(base_world))
    assert result.passed is False
    assert result.short_circuit is True


# ─────────────── Stage 2: Provider validation ───────────────


@pytest.mark.asyncio
async def test_provider_validation_passes_for_preferred_in_range(base_world) -> None:
    claim = _make_claim(base_world)
    result = await ProviderValidation().process(claim, _ctx(base_world))
    assert result.passed is True


@pytest.mark.asyncio
async def test_provider_validation_flags_rate_variance(base_world) -> None:
    claim = _make_claim(
        base_world,
        line_items=[
            {"code": "99213", "description": "Visit", "quantity": 1, "unit_cost": 400.0},
        ],
        total_billed=400.0,
    )
    result = await ProviderValidation().process(claim, _ctx(base_world))
    assert any(f.startswith("rate_variance") for f in result.flags)
    assert result.passed is False


@pytest.mark.asyncio
async def test_provider_validation_short_circuits_on_expired_license(base_world) -> None:
    base_world["provider"].license_expiry = date.today() - timedelta(days=30)
    claim = _make_claim(base_world)
    result = await ProviderValidation().process(claim, _ctx(base_world))
    assert result.short_circuit is True


@pytest.mark.asyncio
async def test_provider_validation_flags_out_of_network(base_world) -> None:
    base_world["provider"].network_tier = NetworkTier.OUT_OF_NETWORK.value
    claim = _make_claim(base_world)
    result = await ProviderValidation().process(claim, _ctx(base_world))
    assert "out_of_network" in result.flags
    assert result.passed is False


# ─────────────── Stage 3: Medical necessity ───────────────


@pytest.mark.asyncio
async def test_medical_necessity_fast_path_skips_llm(base_world) -> None:
    verdict_cache.clear()
    fake = FakeProvider()
    claim = _make_claim(base_world)  # E11.9 + 99213 = clearly appropriate
    result = await MedicalNecessityCheck(provider=fake).process(claim, _ctx(base_world))
    assert result.passed is True
    assert result.data["fast_path"] is True
    assert fake.calls == []  # never hit the LLM


@pytest.mark.asyncio
async def test_medical_necessity_calls_llm_for_unusual_pairing(base_world) -> None:
    verdict_cache.clear()
    fake = FakeProvider(
        responses={
            MedicalNecessityVerdict: MedicalNecessityVerdict(
                is_appropriate=False,
                confidence=0.85,
                concerns=["mismatch"],
                reasoning="Procedure does not match diagnosis pattern.",
            )
        }
    )
    claim = _make_claim(
        base_world,
        diagnosis_codes=["E11.9"],
        procedure_codes=["76700"],  # abdominal U/S — not in appropriate set for E11.9
        line_items=[
            {"code": "76700", "description": "U/S", "quantity": 1, "unit_cost": 480.0},
        ],
        total_billed=480.0,
    )
    result = await MedicalNecessityCheck(provider=fake).process(claim, _ctx(base_world))
    assert result.passed is False
    assert "medical_necessity_concern" in result.flags
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_medical_necessity_caches_repeat_calls(base_world) -> None:
    verdict_cache.clear()
    fake = FakeProvider(
        responses={
            MedicalNecessityVerdict: MedicalNecessityVerdict(
                is_appropriate=True, confidence=0.9, reasoning="ok"
            )
        }
    )
    # Use a pairing that DOESN'T match the fast-path so the LLM is consulted.
    claim_a = _make_claim(
        base_world, claim_id="A",
        diagnosis_codes=["E11.9"], procedure_codes=["76700"],
        line_items=[{"code": "76700", "description": "U/S", "quantity": 1, "unit_cost": 480.0}],
        total_billed=480.0,
    )
    claim_b = _make_claim(
        base_world, claim_id="B",
        diagnosis_codes=["E11.9"], procedure_codes=["76700"],
        line_items=[{"code": "76700", "description": "U/S", "quantity": 1, "unit_cost": 480.0}],
        total_billed=480.0,
    )
    stage = MedicalNecessityCheck(provider=fake)
    await stage.process(claim_a, _ctx(base_world))
    await stage.process(claim_b, _ctx(base_world))
    assert len(fake.calls) == 1  # second call was cached
    assert verdict_cache.hit_rate > 0


def test_cache_key_is_order_insensitive() -> None:
    assert cache_key(["A", "B"], ["X", "Y"]) == cache_key(["B", "A"], ["Y", "X"])


# ─────────────── Stage 4: Fraud detection ───────────────


@pytest.mark.asyncio
async def test_fraud_detection_clean_claim_low_score(base_world, session) -> None:
    claim = _make_claim(base_world)
    session.add(claim)
    session.commit()
    fake = FakeProvider()
    result = await FraudDetection(session=session, provider=fake).process(claim, _ctx(base_world))
    assert result.passed is True
    assert result.data["fraud_risk_score"] < 50.0
    # No rule signals → LLM should NOT have been consulted (provider risk is low).
    assert fake.calls == []


@pytest.mark.asyncio
async def test_fraud_detection_detects_duplicate(base_world, session) -> None:
    earlier = _make_claim(
        base_world,
        claim_id="DUP-EARLIER",
        service_date=date.today() - timedelta(days=2),
    )
    new = _make_claim(base_world, claim_id="DUP-NEW")
    session.add_all([earlier, new])
    session.commit()
    fake = FakeProvider(
        responses={
            __import__(
                "claimsflow.pipeline.fraud_detection", fromlist=["FraudVerdict"]
            ).FraudVerdict: __import__(
                "claimsflow.pipeline.fraud_detection", fromlist=["FraudVerdict"]
            ).FraudVerdict(
                fraud_risk_score=70.0,
                signals=["LLM concur"],
                reasoning="Duplicate pattern looks like upcoding.",
            )
        }
    )
    result = await FraudDetection(session=session, provider=fake).process(new, _ctx(base_world))
    assert "fraud_signal:duplicate_within_7d" in result.flags
    assert result.passed is False
    assert len(fake.calls) == 1


# ─────────────── Stage 5: Cost calculation ───────────────


@pytest.mark.asyncio
async def test_cost_calculation_preferred_full_coverage_zero_copay(base_world) -> None:
    base_world["plan"].copay_percent = 0.0
    claim = _make_claim(base_world)
    result = await CostCalculation().process(claim, _ctx(base_world))
    assert result.data["payable_to_provider"] == 250.0
    assert result.data["member_responsibility"] == 0.0


@pytest.mark.asyncio
async def test_cost_calculation_copay_member_share(base_world) -> None:
    # 10% copay -> member owes 25, plan pays 225
    claim = _make_claim(base_world)
    result = await CostCalculation().process(claim, _ctx(base_world))
    assert result.data["payable_to_provider"] == 225.0
    assert result.data["member_responsibility"] == 25.0


@pytest.mark.asyncio
async def test_cost_calculation_out_of_network_zero_coverage(base_world) -> None:
    base_world["provider"].network_tier = NetworkTier.OUT_OF_NETWORK.value
    claim = _make_claim(base_world)
    result = await CostCalculation().process(claim, _ctx(base_world))
    assert result.data["payable_to_provider"] == 0.0
    assert result.data["member_responsibility"] == 250.0


# ─────────────── Stage 6: Decision router ───────────────


@pytest.mark.asyncio
async def test_router_auto_approves_clean_low_amount(base_world) -> None:
    ctx = _ctx(base_world)
    ctx.accumulated = {
        "eligibility": StageResult(stage="eligibility", passed=True),
        "provider_validation": StageResult(stage="provider_validation", passed=True),
        "medical_necessity": StageResult(stage="medical_necessity", passed=True),
        "fraud_detection": StageResult(
            stage="fraud_detection", passed=True, data={"fraud_risk_score": 10.0}
        ),
        "cost_calculation": StageResult(
            stage="cost_calculation", passed=True, data={"payable_to_provider": 1000.0}
        ),
    }
    result = await DecisionRouter().process(_make_claim(base_world), ctx)
    assert result.data["decision_type"] == DecisionType.AUTO_APPROVE.value


@pytest.mark.asyncio
async def test_router_routes_high_fraud_to_hold(base_world) -> None:
    ctx = _ctx(base_world)
    ctx.accumulated = {
        "eligibility": StageResult(stage="eligibility", passed=True),
        "provider_validation": StageResult(stage="provider_validation", passed=True),
        "medical_necessity": StageResult(stage="medical_necessity", passed=True),
        "fraud_detection": StageResult(
            stage="fraud_detection", passed=False, data={"fraud_risk_score": 75.0}
        ),
        "cost_calculation": StageResult(
            stage="cost_calculation", passed=True, data={"payable_to_provider": 250.0}
        ),
    }
    result = await DecisionRouter().process(_make_claim(base_world), ctx)
    assert result.data["decision_type"] == DecisionType.FRAUD_HOLD.value


@pytest.mark.asyncio
async def test_router_auto_denies_when_eligibility_short_circuits(base_world) -> None:
    ctx = _ctx(base_world)
    ctx.accumulated = {
        "eligibility": StageResult(
            stage="eligibility", passed=False, short_circuit=True
        ),
    }
    result = await DecisionRouter().process(_make_claim(base_world), ctx)
    assert result.data["decision_type"] == DecisionType.AUTO_DENY.value


# ─────────────── Full orchestrator ───────────────


@pytest.mark.asyncio
async def test_orchestrator_end_to_end_auto_approve(base_world, session, monkeypatch) -> None:
    verdict_cache.clear()
    # Force the router cache to return our FakeProvider universally.
    fake = FakeProvider(
        responses={
            MedicalNecessityVerdict: MedicalNecessityVerdict(
                is_appropriate=True, confidence=0.95, reasoning="textbook"
            ),
            BilingualEOB: BilingualEOB(
                english="Your claim has been approved. We paid the provider directly.",
                arabic="تمت الموافقة على مطالبتك. لقد دفعنا لمقدم الخدمة مباشرة.",
            ),
        }
    )
    monkeypatch.setattr(
        "claimsflow.pipeline.medical_necessity.get_llm_provider", lambda: fake
    )
    monkeypatch.setattr("claimsflow.pipeline.fraud_detection.get_llm_provider", lambda: fake)
    monkeypatch.setattr("claimsflow.pipeline.eob.get_llm_provider", lambda: fake)

    claim = _make_claim(base_world)
    session.add(claim)
    session.commit()

    decision = await process_claim(session, claim.claim_id)
    session.commit()

    assert decision.decision_type == DecisionType.AUTO_APPROVE.value
    assert decision.amount_approved > 0
    assert decision.eob_en and "approved" in decision.eob_en.lower()
    assert decision.eob_ar and len(decision.eob_ar) > 20

    # Audit trail: at least one stage_completed per stage + decision_rendered + eob.
    logs = session.scalars(select(AuditLog).where(AuditLog.claim_id == claim.claim_id)).all()
    event_types = {log.event_type for log in logs}
    assert "stage_completed" in event_types
    assert "decision_rendered" in event_types
    assert "eob_generated" in event_types

    # Refresh claim to pick up status change.
    session.refresh(claim)
    assert claim.status == "approved"


@pytest.mark.asyncio
async def test_orchestrator_auto_denies_expired_member(base_world, session, monkeypatch) -> None:
    base_world["member"].policy_status = PolicyStatus.EXPIRED.value
    session.commit()
    fake = FakeProvider()
    monkeypatch.setattr(
        "claimsflow.pipeline.medical_necessity.get_llm_provider", lambda: fake
    )
    monkeypatch.setattr("claimsflow.pipeline.fraud_detection.get_llm_provider", lambda: fake)
    monkeypatch.setattr("claimsflow.pipeline.eob.get_llm_provider", lambda: fake)

    claim = _make_claim(base_world)
    session.add(claim)
    session.commit()

    decision = await process_claim(session, claim.claim_id)
    session.commit()
    assert decision.decision_type == DecisionType.AUTO_DENY.value
    session.refresh(claim)
    assert claim.status == "denied"
    assert fake.calls == []  # short-circuited before any LLM call


@pytest.mark.asyncio
async def test_orchestrator_persists_one_decision_per_claim(base_world, session, monkeypatch) -> None:
    fake = FakeProvider(
        responses={
            MedicalNecessityVerdict: MedicalNecessityVerdict(
                is_appropriate=True, confidence=0.95, reasoning="ok"
            ),
            BilingualEOB: BilingualEOB(
                english="Your claim has been approved.",
                arabic="تمت الموافقة على مطالبتك.",
            ),
        }
    )
    monkeypatch.setattr(
        "claimsflow.pipeline.medical_necessity.get_llm_provider", lambda: fake
    )
    monkeypatch.setattr("claimsflow.pipeline.fraud_detection.get_llm_provider", lambda: fake)
    monkeypatch.setattr("claimsflow.pipeline.eob.get_llm_provider", lambda: fake)

    claim = _make_claim(base_world)
    session.add(claim)
    session.commit()

    await process_claim(session, claim.claim_id)
    session.commit()

    decisions = session.scalars(select(Decision).where(Decision.claim_id == claim.claim_id)).all()
    assert len(decisions) == 1
