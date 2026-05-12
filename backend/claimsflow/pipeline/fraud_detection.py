"""Stage 4: Fraud detection — rules + LLM.

Three pure-rule signals run first (duplicate, velocity, amount anomaly).
If any rule fires OR the provider's baseline fraud-risk score is high,
we additionally ask the LLM to review the claim narrative and surface
anything qualitative the rules missed.

This stage never short-circuits — even high-fraud claims continue
through cost calculation so we can quantify the financial impact for
the audit log.
"""

from __future__ import annotations

import statistics
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from claimsflow.core.logging import get_logger
from claimsflow.models.orm import Claim
from claimsflow.pipeline.base import Stage, StageContext, StageResult
from claimsflow.providers.base import LLMProvider
from claimsflow.providers.router import get_llm_provider

log = get_logger(__name__)


DUPLICATE_WINDOW_DAYS = 7
VELOCITY_HOUR_THRESHOLD = 5  # claims/hour from same provider for same proc
HIGH_FRAUD_PROVIDER_THRESHOLD = 50.0

FRAUD_SYSTEM_PROMPT = """\
You are a fraud-investigation analyst at a Saudi medical insurer.
Given a single claim and the rule signals already detected, decide if
the claim looks suspicious enough to hold for human investigation.

Return a structured verdict. Be skeptical but specific: name concrete
patterns ("amount 2× peer average", "diagnosis pediatric, member 71 years
old"). Avoid generic phrases like "unusual" or "anomalous" with no detail.
"""


class FraudVerdict(BaseModel):
    fraud_risk_score: float = Field(ge=0.0, le=100.0)
    signals: list[str] = Field(default_factory=list)
    reasoning: str = Field(description="One paragraph explaining the score.")


class FraudDetection(Stage):
    name = "fraud_detection"

    def __init__(
        self,
        session: Session,
        provider: LLMProvider | None = None,
    ) -> None:
        self._session = session
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        return self._provider or get_llm_provider()

    async def process(self, claim: Claim, ctx: StageContext) -> StageResult:
        signals = self._rule_signals(claim, ctx)
        base_risk = ctx.provider.fraud_risk_score
        score = base_risk + 15.0 * len(signals)

        # If any rule fires or provider baseline is high, ask the LLM.
        should_consult_llm = bool(signals) or base_risk >= HIGH_FRAUD_PROVIDER_THRESHOLD
        llm_verdict: FraudVerdict | None = None
        if should_consult_llm:
            try:
                response = await self.provider.reason(
                    system_prompt=FRAUD_SYSTEM_PROMPT,
                    user_prompt=_build_fraud_prompt(claim, ctx, signals),
                    response_schema=FraudVerdict,
                )
                llm_verdict = response.data
                # Blend LLM score with rule score: 60/40 weighted toward LLM.
                score = 0.4 * score + 0.6 * llm_verdict.fraud_risk_score
                signals.extend(s for s in llm_verdict.signals if s not in signals)
            except Exception as exc:
                log.warning("fraud_detection.llm_failure", error=str(exc))

        score = max(0.0, min(100.0, score))
        passed = score < 50.0
        flags = [f"fraud_signal:{s}" for s in signals] + (
            ["high_fraud_risk"] if not passed else []
        )

        return StageResult(
            stage=self.name,
            passed=passed,
            data={
                "fraud_risk_score": round(score, 2),
                "signals": signals,
                "llm_reasoning": llm_verdict.reasoning if llm_verdict else None,
                "provider_baseline_risk": base_risk,
            },
            flags=flags,
        )

    # ── Rule signals ───────────────────────────────────────────

    def _rule_signals(self, claim: Claim, ctx: StageContext) -> list[str]:
        signals: list[str] = []
        if self._is_duplicate(claim):
            signals.append("duplicate_within_7d")
        if self._is_velocity_breach(claim):
            signals.append("provider_velocity")
        if self._is_amount_anomaly(claim):
            signals.append("amount_anomaly")
        # Demographic mismatch: pediatric-only diagnoses on adult members.
        age = (claim.service_date - ctx.member.dob).days // 365
        pediatric_only = {"H66.90", "A09", "Z00.121"}
        if age >= 18 and any(dx in pediatric_only for dx in claim.diagnosis_codes):
            signals.append("pediatric_diagnosis_on_adult")
        return signals

    def _is_duplicate(self, claim: Claim) -> bool:
        cutoff = claim.service_date - timedelta(days=DUPLICATE_WINDOW_DAYS)
        stmt = select(Claim).where(
            and_(
                Claim.claim_id != claim.claim_id,
                Claim.member_id == claim.member_id,
                Claim.provider_id == claim.provider_id,
                Claim.service_date >= cutoff,
                Claim.service_date <= claim.service_date,
            )
        )
        return self._session.scalars(stmt).first() is not None

    def _is_velocity_breach(self, claim: Claim) -> bool:
        # Same provider, same procedure code, same service date — count > threshold.
        stmt = select(Claim).where(
            and_(
                Claim.provider_id == claim.provider_id,
                Claim.service_date == claim.service_date,
            )
        )
        same_day = self._session.scalars(stmt).all()
        if len(same_day) <= VELOCITY_HOUR_THRESHOLD:
            return False
        # Overlapping procedure codes?
        target = set(claim.procedure_codes)
        overlapping = sum(1 for c in same_day if set(c.procedure_codes) & target)
        return overlapping > VELOCITY_HOUR_THRESHOLD

    def _is_amount_anomaly(self, claim: Claim) -> bool:
        # Compare against the provider's own historical billed amounts for
        # the same procedure set. Skip if too few prior claims.
        target_codes = set(claim.procedure_codes)
        stmt = select(Claim).where(
            and_(
                Claim.provider_id == claim.provider_id,
                Claim.claim_id != claim.claim_id,
            )
        )
        history = [
            c.total_billed
            for c in self._session.scalars(stmt).all()
            if set(c.procedure_codes) == target_codes
        ]
        if len(history) < 5:
            return False
        mean = statistics.fmean(history)
        sd = statistics.pstdev(history) or 1.0
        return (claim.total_billed - mean) / sd > 3.0


def _build_fraud_prompt(claim: Claim, ctx: StageContext, signals: list[str]) -> str:
    age = (claim.service_date - ctx.member.dob).days // 365
    return (
        f"Claim: {claim.claim_id}\n"
        f"Member: {ctx.member.full_name_en} (age {age}, policy {ctx.member.policy_status})\n"
        f"Provider: {ctx.provider.name_en} "
        f"(tier {ctx.provider.network_tier}, baseline risk {ctx.provider.fraud_risk_score})\n"
        f"Diagnoses: {', '.join(claim.diagnosis_codes)}\n"
        f"Procedures: {', '.join(claim.procedure_codes)}\n"
        f"Total billed: {claim.total_billed:.2f} SAR\n"
        f"Rule signals already detected: {', '.join(signals) or 'none'}\n"
        f"Clinical notes: {claim.clinical_notes or 'none'}\n"
    )
