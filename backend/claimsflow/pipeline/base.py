"""Pipeline primitives: Stage, StageContext, StageResult.

Each stage is an `async` class with a `process(claim, ctx) -> StageResult`
method. Stages are pure functions of their inputs — they don't mutate the
claim or write to the DB. The orchestrator collects their results, persists
the final Decision, and writes the audit log.

Why no abstract base class: we use a Protocol so stages can be plain
classes (or even module-level functions) without inheritance ceremony.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from claimsflow.models.orm import Claim, Member, Plan, Provider


@dataclass
class StageContext:
    """Everything a stage needs that isn't on the claim itself.

    Carries the resolved Member/Plan/Provider so each stage doesn't re-query.
    `accumulated` lets later stages see earlier stages' results — used by
    DecisionRouter to inspect what everyone else said.
    """

    member: Member
    plan: Plan
    provider: Provider
    accumulated: dict[str, "StageResult"] = field(default_factory=dict)


@dataclass
class StageResult:
    """Uniform stage output. `passed` is the boolean go/no-go signal;
    `data` carries stage-specific payload for the audit trail and the
    final reasoning paragraph."""

    stage: str
    passed: bool
    data: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    short_circuit: bool = False
    """If True, the orchestrator stops here and routes to auto_deny."""


@runtime_checkable
class Stage(Protocol):
    name: str

    async def process(self, claim: Claim, ctx: StageContext) -> StageResult: ...
