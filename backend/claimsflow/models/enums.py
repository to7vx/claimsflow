"""Domain enums shared across ORM, Pydantic, and pipeline layers.

Kept as plain `StrEnum` so they serialize transparently as strings in JSON
and round-trip cleanly through SQLAlchemy `String` columns.
"""

from __future__ import annotations

from enum import StrEnum


class PolicyStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class ProviderType(StrEnum):
    HOSPITAL = "hospital"
    CLINIC = "clinic"
    LAB = "lab"
    PHARMACY = "pharmacy"


class NetworkTier(StrEnum):
    PREFERRED = "preferred"
    STANDARD = "standard"
    OUT_OF_NETWORK = "out_of_network"


class ClaimType(StrEnum):
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    PHARMACY = "pharmacy"
    DENTAL = "dental"
    OPTICAL = "optical"


class ClaimStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    APPROVED = "approved"
    DENIED = "denied"
    REVIEW = "review"
    FRAUD_HOLD = "fraud_hold"


class DecisionType(StrEnum):
    AUTO_APPROVE = "auto_approve"
    AUTO_APPROVE_WITH_AUDIT = "auto_approve_with_audit"
    AUTO_DENY = "auto_deny"
    HUMAN_REVIEW = "human_review"
    FRAUD_HOLD = "fraud_hold"


class AuditEventType(StrEnum):
    CLAIM_RECEIVED = "claim_received"
    STAGE_COMPLETED = "stage_completed"
    DECISION_RENDERED = "decision_rendered"
    HUMAN_OVERRIDE = "human_override"
    FRAUD_FLAGGED = "fraud_flagged"
    EOB_GENERATED = "eob_generated"
