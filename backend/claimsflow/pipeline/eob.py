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
    prompt = (
        f"Claim ID: {claim.claim_id}\n"
        f"Member: {member.full_name_en}\n"
        f"Service date: {claim.service_date}\n"
        f"Provider: {provider_name}\n"
        f"Diagnoses: {', '.join(claim.diagnosis_codes)}\n"
        f"Total billed (SAR): {cost_breakdown.get('billed', 0):.2f}\n"
        f"Paid to provider (SAR): {cost_breakdown.get('payable_to_provider', 0):.2f}\n"
        f"Member responsibility (SAR): {cost_breakdown.get('member_responsibility', 0):.2f}\n"
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
    paid = cost.get("payable_to_provider", 0)
    owed = cost.get("member_responsibility", 0)
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
