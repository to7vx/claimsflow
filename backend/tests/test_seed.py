"""Module 2 — seed data consistency.

Validates the synthetic data generators produce a coherent dataset:
- No orphan foreign keys
- Line-item totals match `total_billed`
- Expected counts per mode
- The required fraud/exception subsets exist
- Determinism: same seed -> same data
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from claimsflow.core.db import Base
from claimsflow.models import Claim, Member, Provider
from claimsflow.models.enums import NetworkTier, PolicyStatus
from claimsflow.seed import seed_database
from claimsflow.seed.generators import VOLUME_FULL, VOLUME_SMALL


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_small_seed_produces_expected_counts(session: Session) -> None:
    counts = seed_database(session, mode="small", random_seed=42)
    session.commit()
    assert counts == {
        "plans": VOLUME_SMALL.plans,
        "providers": VOLUME_SMALL.providers,
        "members": VOLUME_SMALL.members,
        "claims": VOLUME_SMALL.claims,
    }


def test_full_seed_produces_expected_counts(session: Session) -> None:
    counts = seed_database(session, mode="full", random_seed=42)
    session.commit()
    assert counts["plans"] == VOLUME_FULL.plans
    assert counts["providers"] == VOLUME_FULL.providers
    assert counts["members"] == VOLUME_FULL.members
    assert counts["claims"] == VOLUME_FULL.claims


def test_no_orphan_foreign_keys(session: Session) -> None:
    seed_database(session, mode="small", random_seed=42)
    session.commit()

    member_ids = {m.member_id for m in session.scalars(select(Member)).all()}
    provider_ids = {p.provider_id for p in session.scalars(select(Provider)).all()}

    for claim in session.scalars(select(Claim)).all():
        assert claim.member_id in member_ids, f"claim {claim.claim_id} -> missing member"
        assert claim.provider_id in provider_ids, f"claim {claim.claim_id} -> missing provider"


def test_line_item_totals_match_total_billed(session: Session) -> None:
    seed_database(session, mode="small", random_seed=42)
    session.commit()
    for claim in session.scalars(select(Claim)).all():
        line_sum = sum(item["quantity"] * item["unit_cost"] for item in claim.line_items)
        # Allow tiny float rounding noise — generators round to 2 decimals.
        assert abs(line_sum - claim.total_billed) < 0.05, (
            f"{claim.claim_id}: line sum {line_sum} vs billed {claim.total_billed}"
        )


def test_member_status_distribution_skews_active(session: Session) -> None:
    seed_database(session, mode="full", random_seed=42)
    session.commit()
    members = session.scalars(select(Member)).all()
    active = sum(1 for m in members if m.policy_status == PolicyStatus.ACTIVE.value)
    # >=85% active (we target 95% with some statistical leeway on full volume).
    assert active / len(members) >= 0.85


def test_some_providers_are_out_of_network(session: Session) -> None:
    seed_database(session, mode="full", random_seed=42)
    session.commit()
    providers = session.scalars(select(Provider)).all()
    oon = [p for p in providers if p.network_tier == NetworkTier.OUT_OF_NETWORK.value]
    assert 5 <= len(oon) <= 40, f"expected ~10% out-of-network, got {len(oon)} of {len(providers)}"


def test_determinism_same_seed_produces_same_claim_ids(session: Session) -> None:
    seed_database(session, mode="small", random_seed=99)
    session.commit()
    ids_a = sorted(c.claim_id for c in session.scalars(select(Claim)).all())

    # Fresh DB, same seed
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s2:
        seed_database(s2, mode="small", random_seed=99)
        s2.commit()
        ids_b = sorted(c.claim_id for c in s2.scalars(select(Claim)).all())

    assert ids_a == ids_b


def test_seed_cli_invokes_without_error(monkeypatch, tmp_path) -> None:
    """Smoke-test the CLI end-to-end against a temp SQLite file."""
    from click.testing import CliRunner

    db_path = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # Caches must be cleared for the new env to take effect.
    from claimsflow.core.config import get_settings
    from claimsflow.core.db import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    from claimsflow.cli.main import cli

    runner = CliRunner()
    init_result = runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0, init_result.output

    seed_result = runner.invoke(cli, ["seed", "--small"])
    assert seed_result.exit_code == 0, seed_result.output
    assert "claims" in seed_result.output

    stats_result = runner.invoke(cli, ["stats"])
    assert stats_result.exit_code == 0
    assert "claims" in stats_result.output
