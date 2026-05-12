"""Stage 2: Provider validation — pure rules, no LLM.

Confirms the provider is real, licensed for this service date, and the
billed amounts are within tolerance of the contracted rates.
"""

from __future__ import annotations

from claimsflow.models.enums import NetworkTier
from claimsflow.models.orm import Claim
from claimsflow.pipeline.base import Stage, StageContext, StageResult

# Above this multiplier of contracted rate, claim is flagged for review.
RATE_VARIANCE_FLAG_THRESHOLD = 1.20


class ProviderValidation(Stage):
    name = "provider_validation"

    async def process(self, claim: Claim, ctx: StageContext) -> StageResult:
        flags: list[str] = []
        passed = True
        short_circuit = False

        # 1. License still valid on service date
        if ctx.provider.license_expiry < claim.service_date:
            flags.append("expired_license")
            passed = False
            short_circuit = True

        # 2. Rate variance vs contracted rates
        variances: list[float] = []
        for item in claim.line_items:
            code = item.get("code")
            unit_cost = float(item.get("unit_cost", 0))
            contracted = ctx.provider.contracted_rates.get(code)
            if contracted and contracted > 0:
                variance = unit_cost / contracted
                variances.append(variance)
                if variance > RATE_VARIANCE_FLAG_THRESHOLD:
                    flags.append(f"rate_variance:{code}")

        avg_variance = sum(variances) / len(variances) if variances else 1.0
        if any(f.startswith("rate_variance") for f in flags):
            # Variance flags don't fail the stage — they raise it to human review.
            passed = False

        # 3. Out-of-network surcharge flag
        if ctx.provider.network_tier == NetworkTier.OUT_OF_NETWORK.value:
            flags.append("out_of_network")
            passed = False  # routes to human_review

        return StageResult(
            stage=self.name,
            passed=passed,
            data={
                "valid": True,  # provider exists; that's "valid"
                "network_tier": ctx.provider.network_tier,
                "rate_variance": round(avg_variance, 3),
                "license_valid": ctx.provider.license_expiry >= claim.service_date,
            },
            flags=flags,
            short_circuit=short_circuit,
        )
