"""Synthetic data generation for Saudi healthcare context.

Public entry point: `seed_database()` populates an empty DB with a coherent
set of plans, providers, members, and claims.

> [!IMPORTANT]
> Seed data is *synthetic*. Names, IDs, license numbers — all fabricated.
> Do not use any of this for actual claims processing.
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from claimsflow.core.logging import get_logger
from claimsflow.seed.generators import (
    Volume,
    generate_claims,
    generate_members,
    generate_plans,
    generate_providers,
    get_volume,
)

log = get_logger(__name__)


def seed_database(session: Session, mode: str = "small", random_seed: int = 42) -> dict[str, int]:
    """Populate `session` with synthetic data. Returns counts per entity.

    Idempotency note: this function does NOT clear existing rows. Run
    `claimsflow init --reset` first if you want a clean slate.
    """
    volume = get_volume(mode)
    rng = random.Random(random_seed)

    log.info("seed.start", mode=mode, volume=volume.__dict__)

    plans = generate_plans(rng, volume.plans)
    session.add_all(plans)
    session.flush()

    providers = generate_providers(rng, volume.providers)
    session.add_all(providers)
    session.flush()

    members = generate_members(rng, volume.members, plans)
    session.add_all(members)
    session.flush()

    claims = generate_claims(rng, volume.claims, members, providers)
    session.add_all(claims)
    session.flush()

    counts = {
        "plans": len(plans),
        "providers": len(providers),
        "members": len(members),
        "claims": len(claims),
    }
    log.info("seed.complete", **counts)
    return counts


__all__ = ["seed_database", "Volume", "get_volume"]
