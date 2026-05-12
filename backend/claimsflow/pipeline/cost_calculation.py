"""Stage 5: Cost calculation — pure rules, no LLM.

Applies contracted rates, deductible, copay, and the remaining annual
limit to compute what's covered, what the member owes, and what gets
paid to the provider.

This stage always runs even on flagged/denied claims so the audit trail
shows the financial impact of the decision.
"""

from __future__ import annotations

from claimsflow.models.enums import NetworkTier
from claimsflow.models.orm import Claim
from claimsflow.pipeline.base import Stage, StageContext, StageResult


class CostCalculation(Stage):
    name = "cost_calculation"

    async def process(self, claim: Claim, ctx: StageContext) -> StageResult:
        # 1. Start from contracted rates where we have them, else use the
        #    billed amount (provider has no contract for this code).
        contracted_total = 0.0
        for item in claim.line_items:
            code = item.get("code")
            qty = float(item.get("quantity", 1))
            billed_unit = float(item.get("unit_cost", 0))
            contracted_unit = ctx.provider.contracted_rates.get(code, billed_unit)
            contracted_total += qty * min(billed_unit, contracted_unit)

        # 2. Apply network-tier coverage percentage from the plan.
        tier_coverage = float(
            ctx.plan.coverage_tiers.get(ctx.provider.network_tier, 0.0)
        ) / 100.0
        if ctx.provider.network_tier == NetworkTier.OUT_OF_NETWORK.value:
            tier_coverage = 0.0
        covered_before_copay = contracted_total * tier_coverage

        # 3. Apply deductible (the member pays this first).
        remaining_deductible = max(0.0, ctx.member.deductible - ctx.member.deductible_met)
        deductible_applied = min(remaining_deductible, covered_before_copay)
        covered_after_deductible = covered_before_copay - deductible_applied

        # 4. Apply copay percentage (member's share of what's covered).
        copay_amount = covered_after_deductible * (ctx.plan.copay_percent / 100.0)
        payable_to_provider = covered_after_deductible - copay_amount

        # 5. Cap at remaining annual limit.
        payable_to_provider = min(payable_to_provider, ctx.member.remaining_limit)

        member_responsibility = (
            deductible_applied + copay_amount + (contracted_total - covered_before_copay)
        )
        # Member also owes anything billed above contracted rate.
        billed_above_contracted = claim.total_billed - contracted_total
        if billed_above_contracted > 0:
            member_responsibility += billed_above_contracted

        return StageResult(
            stage=self.name,
            passed=True,
            data={
                "billed": round(claim.total_billed, 2),
                "contracted_total": round(contracted_total, 2),
                "tier_coverage_percent": round(tier_coverage * 100, 1),
                "deductible_applied": round(deductible_applied, 2),
                "copay_amount": round(copay_amount, 2),
                "payable_to_provider": round(max(0.0, payable_to_provider), 2),
                "member_responsibility": round(max(0.0, member_responsibility), 2),
            },
        )
