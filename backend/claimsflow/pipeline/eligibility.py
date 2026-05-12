"""Stage 1: Eligibility — pure rules, no LLM.

Checks the member can use the policy on this service date and that the
plan covers the kind of care being billed.

Short-circuits to auto_deny on any hard failure (suspended/expired policy,
excluded diagnosis) — those claims never need to see the LLM.
"""

from __future__ import annotations

import re

from claimsflow.models.enums import PolicyStatus
from claimsflow.models.orm import Claim
from claimsflow.pipeline.base import Stage, StageContext, StageResult


class EligibilityCheck(Stage):
    name = "eligibility"

    async def process(self, claim: Claim, ctx: StageContext) -> StageResult:
        reasons: list[str] = []
        flags: list[str] = []
        passed = True
        short_circuit = False

        # 1. Policy status
        if ctx.member.policy_status != PolicyStatus.ACTIVE.value:
            reasons.append(f"Policy status is {ctx.member.policy_status}, not active.")
            passed = False
            short_circuit = True

        # 2. Service date within policy window
        if not (ctx.member.policy_start <= claim.service_date <= ctx.member.policy_end):
            reasons.append(
                f"Service date {claim.service_date} is outside policy window "
                f"{ctx.member.policy_start}..{ctx.member.policy_end}."
            )
            passed = False
            short_circuit = True

        # 3. Annual limit
        remaining = ctx.member.remaining_limit
        if claim.total_billed > remaining:
            reasons.append(
                f"Claim total {claim.total_billed:.2f} exceeds remaining annual "
                f"limit {remaining:.2f}."
            )
            flags.append("limit_exceeded")
            passed = False

        # 4. Benefit category coverage
        if claim.claim_type not in ctx.plan.covered_benefits:
            reasons.append(
                f"Claim type '{claim.claim_type}' not in plan covered benefits "
                f"{ctx.plan.covered_benefits}."
            )
            passed = False
            short_circuit = True

        # 5. Plan-level diagnosis exclusions (regex on ICD-10 prefix)
        for exclusion in ctx.plan.exclusions:
            pattern = re.compile(exclusion.replace(".*", ".*") + ".*")
            for dx in claim.diagnosis_codes:
                if pattern.match(dx):
                    reasons.append(f"Diagnosis {dx} matches plan exclusion {exclusion!r}.")
                    flags.append("excluded_diagnosis")
                    passed = False
                    short_circuit = True
                    break

        return StageResult(
            stage=self.name,
            passed=passed,
            data={
                "eligible": passed,
                "reasons": reasons,
                "remaining_limit": remaining,
            },
            flags=flags,
            short_circuit=short_circuit and not passed,
        )
