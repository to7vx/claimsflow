"""Stage 6: Decision router — pure rules.

Looks at every prior stage's result and the configured amount ceiling,
then picks one of:

- auto_approve            (everything passed, amount low, low fraud risk)
- auto_approve_with_audit (everything passed, amount >= ceiling)
- human_review            (any soft flag)
- fraud_hold              (high fraud risk)
- auto_deny               (eligibility short-circuited)
"""

from __future__ import annotations

from claimsflow.core.config import get_settings
from claimsflow.models.enums import DecisionType
from claimsflow.models.orm import Claim
from claimsflow.pipeline.base import Stage, StageContext, StageResult

HIGH_FRAUD_SCORE = 50.0


class DecisionRouter(Stage):
    name = "decision_router"

    async def process(self, claim: Claim, ctx: StageContext) -> StageResult:
        settings = get_settings()
        eligibility = ctx.accumulated.get("eligibility")
        provider_validation = ctx.accumulated.get("provider_validation")
        medical_necessity = ctx.accumulated.get("medical_necessity")
        fraud = ctx.accumulated.get("fraud_detection")
        cost = ctx.accumulated.get("cost_calculation")

        # Auto-deny if eligibility short-circuited (members shouldn't be billed
        # for care they aren't covered for).
        if eligibility and eligibility.short_circuit and not eligibility.passed:
            return _verdict(DecisionType.AUTO_DENY, "eligibility failed (short-circuit)")

        fraud_score = (fraud.data.get("fraud_risk_score", 0) if fraud else 0) or 0
        if fraud_score >= HIGH_FRAUD_SCORE:
            return _verdict(
                DecisionType.FRAUD_HOLD,
                f"fraud risk score {fraud_score:.1f} >= {HIGH_FRAUD_SCORE}",
            )

        all_passed = all(
            r.passed
            for r in (eligibility, provider_validation, medical_necessity, fraud)
            if r is not None
        )
        amount = (cost.data.get("payable_to_provider", 0) if cost else claim.total_billed) or 0

        if all_passed and amount < settings.auto_approve_amount_ceiling_sar:
            return _verdict(DecisionType.AUTO_APPROVE, "all checks passed, amount below ceiling")
        if all_passed and amount >= settings.auto_approve_amount_ceiling_sar:
            return _verdict(
                DecisionType.AUTO_APPROVE_WITH_AUDIT,
                f"all checks passed but amount {amount:.0f} ≥ "
                f"{settings.auto_approve_amount_ceiling_sar:.0f} SAR ceiling",
            )

        # Otherwise: human review with a reason summary.
        reasons: list[str] = []
        for r in (eligibility, provider_validation, medical_necessity, fraud):
            if r is None or r.passed:
                continue
            reasons.append(f"{r.stage} flagged: {', '.join(r.flags) or 'see data'}")
        return _verdict(DecisionType.HUMAN_REVIEW, "; ".join(reasons) or "soft flags raised")


def _verdict(decision_type: DecisionType, reason: str) -> StageResult:
    return StageResult(
        stage="decision_router",
        passed=True,
        data={"decision_type": decision_type.value, "reason": reason},
    )
