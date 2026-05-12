"""The 6-stage adjudication pipeline + orchestrator.

Public API:
- `process_claim(session, claim_id)` — runs the full pipeline, returns Decision
- Stage classes (EligibilityCheck, ProviderValidation, ...) for direct testing
- `verdict_cache` — module-level cache singleton for medical-necessity
- `generate_eob` — bilingual EOB generator (used by the orchestrator)
"""

from claimsflow.pipeline.base import Stage, StageContext, StageResult
from claimsflow.pipeline.cache import VerdictCache, cache_key, verdict_cache
from claimsflow.pipeline.cost_calculation import CostCalculation
from claimsflow.pipeline.decision_router import DecisionRouter
from claimsflow.pipeline.eligibility import EligibilityCheck
from claimsflow.pipeline.eob import BilingualEOB, generate_eob
from claimsflow.pipeline.fraud_detection import FraudDetection, FraudVerdict
from claimsflow.pipeline.medical_necessity import (
    MedicalNecessityCheck,
    MedicalNecessityVerdict,
)
from claimsflow.pipeline.orchestrator import process_claim
from claimsflow.pipeline.provider_validation import ProviderValidation

__all__ = [
    "Stage",
    "StageContext",
    "StageResult",
    "VerdictCache",
    "cache_key",
    "verdict_cache",
    "EligibilityCheck",
    "ProviderValidation",
    "MedicalNecessityCheck",
    "MedicalNecessityVerdict",
    "FraudDetection",
    "FraudVerdict",
    "CostCalculation",
    "DecisionRouter",
    "BilingualEOB",
    "generate_eob",
    "process_claim",
]
