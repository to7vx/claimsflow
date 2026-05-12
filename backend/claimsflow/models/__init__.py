"""Domain models — ORM (`orm`) and API schemas (`schemas`), with shared `enums`.

Importing this package registers all ORM classes with `Base.metadata`, which is
what Alembic autogenerate sees. Always import from here, not the submodules
directly, when you want metadata to be populated.
"""

from claimsflow.models import enums, orm, schemas
from claimsflow.models.enums import (
    AuditEventType,
    ClaimStatus,
    ClaimType,
    DecisionType,
    Gender,
    NetworkTier,
    PolicyStatus,
    ProviderType,
)
from claimsflow.models.orm import (
    AuditLog,
    Claim,
    Decision,
    Member,
    Plan,
    Provider,
)
from claimsflow.models.schemas import (
    ClaimSchema,
    ClaimSubmission,
    ClaimWithDecision,
    DecisionSchema,
    LineItem,
    MemberSchema,
    PlanSchema,
    ProviderSchema,
)

__all__ = [
    # submodules
    "enums",
    "orm",
    "schemas",
    # enums
    "AuditEventType",
    "ClaimStatus",
    "ClaimType",
    "DecisionType",
    "Gender",
    "NetworkTier",
    "PolicyStatus",
    "ProviderType",
    # ORM
    "AuditLog",
    "Claim",
    "Decision",
    "Member",
    "Plan",
    "Provider",
    # schemas
    "ClaimSchema",
    "ClaimSubmission",
    "ClaimWithDecision",
    "DecisionSchema",
    "LineItem",
    "MemberSchema",
    "PlanSchema",
    "ProviderSchema",
]
