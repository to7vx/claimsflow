"""Bilingual Explanation of Benefits generator.

For auto-approved claims we generate a member-facing EOB in English AND
Arabic. We use the LLM for tone/polish but constrain it tightly: the
schema forces both languages to be present and non-empty.

If the LLM call fails (offline, rate-limited), we fall back to a
deterministic template — the dashboard still shows something usable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from claimsflow.core.logging import get_logger
from claimsflow.models.orm import Claim, Member
from claimsflow.providers.base import LLMProvider
from claimsflow.providers.router import get_llm_provider

log = get_logger(__name__)

EOB_SYSTEM_PROMPT = """\
You write member-facing Explanation of Benefits letters for a Saudi
medical insurer. Be polite, clear, and concise. Itemize what was
covered and what the member owes. Never use technical jargon.

The letter MUST open by stating the claim was APPROVED — even when the
member's out-of-pocket share is 100% because the cost went toward their
annual deductible. In that "deductible applied" case, explicitly explain
that the amount was applied to the member's annual deductible and that
future eligible claims will be paid by the plan once that deductible is
met. Never let an approved claim read like a denial.

Always return BOTH the English and Arabic versions. The Arabic must be
in proper Arabic script (not transliterated). Keep each version to 4–6
short sentences.
"""


class BilingualEOB(BaseModel):
    english: str = Field(min_length=20)
    arabic: str = Field(min_length=20)


async def generate_eob(
    claim: Claim,
    member: Member,
    cost_breakdown: dict,
    provider_name: str,
    llm_provider: LLMProvider | None = None,
) -> BilingualEOB:
    """Build a bilingual EOB. Falls back to a template on LLM failure."""
    deductible_applied = float(cost_breakdown.get("deductible_applied", 0) or 0)
    payable = float(cost_breakdown.get("payable_to_provider", 0) or 0)
    is_deductible_case = deductible_applied > 0 and payable == 0
    deductible_remaining = max(
        0.0, float(member.deductible) - float(member.deductible_met) - deductible_applied
    )

    context_line = (
        "Case: APPROVED CLAIM, fully applied to the member's annual deductible. "
        f"After this claim, the deductible remaining is {deductible_remaining:.2f} SAR. "
        "The letter must (1) state the claim was approved, (2) explain that the "
        "amount was applied to the deductible (not denied), and (3) reassure the "
        "member that future eligible claims will be paid by the plan once the "
        "deductible is fully met."
        if is_deductible_case
        else "Case: APPROVED CLAIM with normal coverage split (plan paid the provider; "
        "member share is copay/coinsurance)."
    )

    prompt = (
        f"Claim ID: {claim.claim_id}\n"
        f"Member: {member.full_name_en}\n"
        f"Service date: {claim.service_date}\n"
        f"Provider: {provider_name}\n"
        f"Diagnoses: {', '.join(claim.diagnosis_codes)}\n"
        f"Total billed (SAR): {cost_breakdown.get('billed', 0):.2f}\n"
        f"Paid to provider (SAR): {payable:.2f}\n"
        f"Applied to annual deductible (SAR): {deductible_applied:.2f}\n"
        f"Member responsibility (SAR): {cost_breakdown.get('member_responsibility', 0):.2f}\n"
        f"\n{context_line}\n"
        f"\nWrite the EOB in English and Arabic, addressed to {member.full_name_en}."
    )
    provider = llm_provider or get_llm_provider()
    try:
        response = await provider.reason(
            system_prompt=EOB_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=BilingualEOB,
        )
        return response.data
    except Exception as exc:
        log.warning("eob.llm_failure", error=str(exc))
        return _template_fallback(claim, member, cost_breakdown, provider_name)


def _template_fallback(
    claim: Claim, member: Member, cost: dict, provider_name: str
) -> BilingualEOB:
    paid = float(cost.get("payable_to_provider", 0) or 0)
    owed = float(cost.get("member_responsibility", 0) or 0)
    deductible_applied = float(cost.get("deductible_applied", 0) or 0)
    is_deductible_case = deductible_applied > 0 and paid == 0
    deductible_remaining = max(
        0.0, float(member.deductible) - float(member.deductible_met) - deductible_applied
    )

    if is_deductible_case:
        english = (
            f"Dear {member.full_name_en},\n\n"
            f"Your claim {claim.claim_id} for services on {claim.service_date} at "
            f"{provider_name} has been APPROVED. The amount of {deductible_applied:.2f} SAR "
            f"was applied to your annual deductible rather than paid to the provider, "
            f"so your share for this claim is {owed:.2f} SAR. "
            f"You have {deductible_remaining:.2f} SAR remaining on your deductible; "
            f"once it is fully met, the plan will start paying eligible claims directly. "
            f"Thank you for choosing us."
        )
        arabic = (
            f"عزيزي/عزيزتي {member.full_name_ar}،\n\n"
            f"تمت الموافقة على مطالبتك رقم {claim.claim_id} للخدمات المقدمة بتاريخ "
            f"{claim.service_date} في {provider_name}. تم تطبيق مبلغ {deductible_applied:.2f} ريال "
            f"على الخصم السنوي الخاص بك بدلاً من دفعه لمقدم الخدمة، لذا فإن حصتك من هذه المطالبة "
            f"هي {owed:.2f} ريال. لا يزال هناك {deductible_remaining:.2f} ريال متبقٍّ من الخصم السنوي؛ "
            f"بمجرد استيفائه بالكامل، ستبدأ الشركة بدفع المطالبات المؤهلة مباشرة. "
            f"شكراً لاختيارك لنا."
        )
    else:
        english = (
            f"Dear {member.full_name_en},\n\n"
            f"Your claim {claim.claim_id} for services on {claim.service_date} at "
            f"{provider_name} has been approved. We paid {paid:.2f} SAR directly to "
            f"the provider. Your share is {owed:.2f} SAR. Thank you for choosing us."
        )
        arabic = (
            f"عزيزي/عزيزتي {member.full_name_ar}،\n\n"
            f"تمت الموافقة على مطالبتك رقم {claim.claim_id} للخدمات المقدمة بتاريخ "
            f"{claim.service_date} في {provider_name}. لقد دفعنا {paid:.2f} ريال "
            f"مباشرة إلى مقدم الخدمة. حصتك هي {owed:.2f} ريال. شكراً لاختيارك لنا."
        )
    return BilingualEOB(english=english, arabic=arabic)
