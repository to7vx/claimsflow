"""Stage 3: Medical-necessity reasoning — LLM-powered.

Asks the configured LLM whether the procedure set is clinically
appropriate for the diagnosis set. The model returns structured output
(`MedicalNecessityVerdict`) that includes a confidence score and concise
reasoning suitable for the audit trail and the dashboard side panel.

Verdicts are cached by the (sorted diagnoses, sorted procedures) tuple —
most outpatient claims repeat the same code combinations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from claimsflow.core.logging import get_logger
from claimsflow.models.orm import Claim
from claimsflow.pipeline.base import Stage, StageContext, StageResult
from claimsflow.pipeline.cache import cache_key, verdict_cache
from claimsflow.providers.base import LLMProvider
from claimsflow.providers.router import get_llm_provider
from claimsflow.seed.reference_data import APPROPRIATE_PROCEDURES

log = get_logger(__name__)


SYSTEM_PROMPT = """\
You are a clinical reviewer for a Saudi medical insurer. Your job is to
judge whether the procedure codes billed on a claim are medically
appropriate for the diagnosis codes presented.

Be conservative: if procedures are clearly off-pattern for the diagnoses
(e.g., adult lab panels billed for a routine pediatric visit, expensive
imaging for self-limiting conditions), flag them. If the pairing is
reasonable, approve with high confidence.

Always respond in the structured schema provided. Keep `reasoning` to one
or two sentences — this text is shown to a human reviewer.
"""


class MedicalNecessityVerdict(BaseModel):
    is_appropriate: bool = Field(description="True if procedures fit the diagnoses.")
    confidence: float = Field(ge=0.0, le=1.0, description="0.0–1.0 confidence in the verdict.")
    concerns: list[str] = Field(default_factory=list, description="Specific concerns, if any.")
    reasoning: str = Field(description="One or two sentence rationale.")


class MedicalNecessityCheck(Stage):
    name = "medical_necessity"

    def __init__(self, provider: LLMProvider | None = None) -> None:
        # Allow injection so tests can pass a mock without env tricks.
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        return self._provider or get_llm_provider()

    async def process(self, claim: Claim, ctx: StageContext) -> StageResult:
        key = cache_key(claim.diagnosis_codes, claim.procedure_codes)
        cached = verdict_cache.get(key)
        if cached is not None:
            verdict: MedicalNecessityVerdict = cached
            return _to_result(verdict, cached=True)

        # Heuristic fast-path: if every procedure is in the appropriate set
        # for at least one of the diagnoses, skip the LLM call entirely.
        if _all_procedures_clearly_appropriate(claim.diagnosis_codes, claim.procedure_codes):
            verdict = MedicalNecessityVerdict(
                is_appropriate=True,
                confidence=0.97,
                concerns=[],
                reasoning="Procedure codes appear in the appropriate-procedure set for the diagnoses.",
            )
            verdict_cache.set(key, verdict)
            return _to_result(verdict, cached=False, fast_path=True)

        user_prompt = _build_user_prompt(claim)
        try:
            response = await self.provider.reason(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_schema=MedicalNecessityVerdict,
            )
        except Exception as exc:
            log.warning("medical_necessity.llm_failure", error=str(exc))
            # On LLM failure, fall back to a low-confidence neutral verdict
            # that routes the claim to human review.
            verdict = MedicalNecessityVerdict(
                is_appropriate=False,
                confidence=0.0,
                concerns=[f"LLM call failed: {type(exc).__name__}"],
                reasoning="Medical necessity could not be evaluated; routing to human review.",
            )
            return _to_result(verdict, cached=False, llm_failed=True)

        verdict = response.data
        verdict_cache.set(key, verdict)
        log.info(
            "medical_necessity.verdict",
            appropriate=verdict.is_appropriate,
            confidence=verdict.confidence,
            tokens=response.usage.total,
        )
        return _to_result(verdict, cached=False, latency_ms=response.latency_ms)


def _all_procedures_clearly_appropriate(diagnoses: list[str], procedures: list[str]) -> bool:
    """Heuristic short-circuit that saves an LLM call for textbook claims."""
    appropriate_for_any: set[str] = set()
    for dx in diagnoses:
        appropriate_for_any.update(APPROPRIATE_PROCEDURES.get(dx, []))
    return bool(appropriate_for_any) and all(p in appropriate_for_any for p in procedures)


def _build_user_prompt(claim: Claim) -> str:
    lines = [
        f"Diagnoses (ICD-10): {', '.join(claim.diagnosis_codes)}",
        f"Procedures (CPT): {', '.join(claim.procedure_codes)}",
        f"Claim type: {claim.claim_type}",
        "Line items:",
    ]
    for item in claim.line_items:
        lines.append(
            f"  - {item.get('code')} {item.get('description', '')} "
            f"x{item.get('quantity', 1)} @ {item.get('unit_cost', 0):.2f} SAR"
        )
    if claim.clinical_notes:
        lines.append(f"Clinical notes: {claim.clinical_notes}")
    return "\n".join(lines)


def _to_result(
    verdict: MedicalNecessityVerdict,
    cached: bool = False,
    fast_path: bool = False,
    llm_failed: bool = False,
    latency_ms: float | None = None,
) -> StageResult:
    flags = list(verdict.concerns)
    if not verdict.is_appropriate:
        flags.append("medical_necessity_concern")
    if llm_failed:
        flags.append("llm_failure")

    return StageResult(
        stage="medical_necessity",
        passed=verdict.is_appropriate and verdict.confidence >= 0.5,
        data={
            "is_appropriate": verdict.is_appropriate,
            "confidence": verdict.confidence,
            "concerns": verdict.concerns,
            "reasoning": verdict.reasoning,
            "cached": cached,
            "fast_path": fast_path,
            "llm_failed": llm_failed,
            "latency_ms": latency_ms,
        },
        flags=flags,
    )
