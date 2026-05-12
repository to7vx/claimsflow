"""Pipeline orchestrator — runs all 6 stages, persists the Decision.

Public entrypoint: `process_claim(session, claim_id) -> Decision`.

The orchestrator:
1. Loads the claim + its member, plan, provider in one trip
2. Marks the claim PROCESSING
3. Runs each stage in order; if a stage short-circuits, jumps to the router
4. Builds a Decision row with the merged reasoning + EOB
5. Writes one AuditLog entry per stage + a terminal DECISION_RENDERED event
6. Commits

This is where the business value happens — keep this file focused on
orchestration, never put rule logic here.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import Session

from claimsflow.core.logging import get_logger
from claimsflow.models.enums import (
    AuditEventType,
    ClaimStatus,
    DecisionType,
)
from claimsflow.models.orm import AuditLog, Claim, Decision, Member, Plan, Provider
from claimsflow.pipeline.base import Stage, StageContext, StageResult
from claimsflow.pipeline.cost_calculation import CostCalculation
from claimsflow.pipeline.decision_router import DecisionRouter
from claimsflow.pipeline.eligibility import EligibilityCheck
from claimsflow.pipeline.eob import generate_eob
from claimsflow.pipeline.fraud_detection import FraudDetection
from claimsflow.pipeline.medical_necessity import MedicalNecessityCheck
from claimsflow.pipeline.provider_validation import ProviderValidation

log = get_logger(__name__)


# Decision-type → claim status mapping. Keeps the status column in sync.
DECISION_TO_STATUS: dict[str, str] = {
    DecisionType.AUTO_APPROVE.value: ClaimStatus.APPROVED.value,
    DecisionType.AUTO_APPROVE_WITH_AUDIT.value: ClaimStatus.APPROVED.value,
    DecisionType.AUTO_DENY.value: ClaimStatus.DENIED.value,
    DecisionType.HUMAN_REVIEW.value: ClaimStatus.REVIEW.value,
    DecisionType.FRAUD_HOLD.value: ClaimStatus.FRAUD_HOLD.value,
}


async def process_claim(session: Session, claim_id: str) -> Decision:
    """End-to-end adjudication for one claim. Returns the persisted Decision."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ValueError(f"claim {claim_id} not found")
    member = session.get(Member, claim.member_id)
    if member is None:
        raise ValueError(f"member {claim.member_id} not found for claim {claim_id}")
    plan = session.get(Plan, member.plan_id)
    if plan is None:
        raise ValueError(f"plan {member.plan_id} not found for member {member.member_id}")
    provider = session.get(Provider, claim.provider_id)
    if provider is None:
        raise ValueError(f"provider {claim.provider_id} not found for claim {claim_id}")

    claim.status = ClaimStatus.PROCESSING.value
    session.add(AuditLog(
        claim_id=claim_id,
        event_type=AuditEventType.CLAIM_RECEIVED.value,
        event_data={"claim_type": claim.claim_type, "amount": claim.total_billed},
    ))

    ctx = StageContext(member=member, plan=plan, provider=provider)

    stages: list[Stage] = [
        EligibilityCheck(),
        ProviderValidation(),
        MedicalNecessityCheck(),
        FraudDetection(session=session),
        CostCalculation(),
    ]
    router = DecisionRouter()

    pipeline_t0 = time.perf_counter()
    short_circuited = False
    for stage in stages:
        result = await _run_stage(stage, claim, ctx, session)
        ctx.accumulated[stage.name] = result
        if result.short_circuit:
            short_circuited = True
            log.info("pipeline.short_circuit", stage=stage.name, claim=claim_id)
            break

    # If we short-circuited, fill in empty results for stages we skipped so
    # the router has a complete picture.
    for stage in stages:
        ctx.accumulated.setdefault(
            stage.name, StageResult(stage=stage.name, passed=False, data={"skipped": True})
        )

    router_result = await router.process(claim, ctx)
    ctx.accumulated[router.name] = router_result
    pipeline_ms = (time.perf_counter() - pipeline_t0) * 1000.0

    decision = _build_decision(claim, ctx, router_result, short_circuited)
    claim.status = DECISION_TO_STATUS[decision.decision_type]
    session.add(decision)

    # Bilingual EOB for approvals.
    if decision.decision_type in (
        DecisionType.AUTO_APPROVE.value,
        DecisionType.AUTO_APPROVE_WITH_AUDIT.value,
    ):
        cost_data = ctx.accumulated["cost_calculation"].data
        eob = await generate_eob(claim, member, cost_data, provider.name_en)
        decision.eob_en = eob.english
        decision.eob_ar = eob.arabic
        session.add(AuditLog(
            claim_id=claim_id,
            event_type=AuditEventType.EOB_GENERATED.value,
            event_data={"languages": ["en", "ar"]},
        ))

    session.add(AuditLog(
        claim_id=claim_id,
        event_type=AuditEventType.DECISION_RENDERED.value,
        event_data={
            "decision_type": decision.decision_type,
            "confidence": decision.confidence_score,
            "pipeline_ms": round(pipeline_ms, 1),
        },
    ))

    if decision.decision_type == DecisionType.FRAUD_HOLD.value:
        session.add(AuditLog(
            claim_id=claim_id,
            event_type=AuditEventType.FRAUD_FLAGGED.value,
            event_data={"signals": ctx.accumulated["fraud_detection"].data.get("signals", [])},
        ))

    session.flush()
    log.info(
        "pipeline.complete",
        claim=claim_id,
        decision=decision.decision_type,
        pipeline_ms=round(pipeline_ms, 1),
    )
    return decision


async def _run_stage(
    stage: Stage, claim: Claim, ctx: StageContext, session: Session
) -> StageResult:
    t0 = time.perf_counter()
    result = await stage.process(claim, ctx)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    session.add(AuditLog(
        claim_id=claim.claim_id,
        event_type=AuditEventType.STAGE_COMPLETED.value,
        event_data={
            "stage": stage.name,
            "passed": result.passed,
            "flags": result.flags,
            "latency_ms": round(elapsed_ms, 1),
        },
        success=result.passed,
    ))
    return result


def _build_decision(
    claim: Claim,
    ctx: StageContext,
    router_result: StageResult,
    short_circuited: bool,
) -> Decision:
    decision_type = router_result.data["decision_type"]
    cost = ctx.accumulated.get("cost_calculation")
    mn = ctx.accumulated.get("medical_necessity")

    payable = (cost.data.get("payable_to_provider", 0.0) if cost else 0.0) or 0.0
    member_resp = (cost.data.get("member_responsibility", 0.0) if cost else 0.0) or 0.0
    amount_denied = max(0.0, claim.total_billed - payable - member_resp)

    confidence = float((mn.data.get("confidence", 0.5)) if mn else 0.5) or 0.5

    flags: list[str] = []
    citations: list[str] = []
    for stage_name, result in ctx.accumulated.items():
        if stage_name == "decision_router":
            continue
        flags.extend(result.flags)
    if ctx.plan.plan_id:
        citations.append(f"Plan {ctx.plan.plan_id} §coverage benefits")
    if ctx.plan.exclusions:
        citations.append(f"Plan {ctx.plan.plan_id} §exclusions list")

    reasoning = _compose_reasoning(claim, ctx, router_result, short_circuited)

    return Decision(
        decision_id=f"DEC-{uuid.uuid4().hex[:10].upper()}",
        claim_id=claim.claim_id,
        decision_type=decision_type,
        decided_by="system",
        amount_approved=round(payable, 2),
        amount_denied=round(amount_denied, 2),
        member_responsibility=round(member_resp, 2),
        confidence_score=round(confidence, 3),
        reasoning=reasoning,
        policy_citations=citations,
        flags=sorted(set(flags)),
        stage_results={
            name: {"passed": r.passed, "flags": r.flags, "data": r.data}
            for name, r in ctx.accumulated.items()
        },
    )


def _compose_reasoning(
    claim: Claim,
    ctx: StageContext,
    router_result: StageResult,
    short_circuited: bool,
) -> str:
    """One-paragraph human-readable rationale shown in the dashboard side panel."""
    parts: list[str] = []
    decision_type = router_result.data["decision_type"]
    parts.append(f"Decision: {decision_type} — {router_result.data['reason']}.")

    elig = ctx.accumulated.get("eligibility")
    if elig and not elig.passed:
        parts.append("Eligibility: " + "; ".join(elig.data.get("reasons", [])) + ".")
    elif elig:
        parts.append(
            f"Eligibility passed (remaining limit {elig.data.get('remaining_limit', 0):.2f} SAR)."
        )

    prov = ctx.accumulated.get("provider_validation")
    if prov:
        parts.append(
            f"Provider validation: tier={prov.data.get('network_tier')}, "
            f"rate variance {prov.data.get('rate_variance')}."
        )

    mn = ctx.accumulated.get("medical_necessity")
    if mn and not short_circuited and "reasoning" in mn.data:
        parts.append(f"Medical necessity: {mn.data['reasoning']}")

    fraud = ctx.accumulated.get("fraud_detection")
    if fraud and fraud.data.get("signals"):
        parts.append(
            f"Fraud signals: {', '.join(fraud.data['signals'])} "
            f"(score {fraud.data.get('fraud_risk_score', 0):.1f})."
        )

    return " ".join(parts)
