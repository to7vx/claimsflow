"""Module 6 — CLI commands (process / status / demo).

Smoke-tests the new commands against an in-memory SQLite. The pipeline
LLM is patched out with a fake; we just verify the CLI plumbing works.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from click.testing import CliRunner

from claimsflow.core.db import Base
from claimsflow.models import (
    Claim,
    ClaimStatus,
    Member,
    NetworkTier,
    Plan,
    PolicyStatus,
    Provider,
    ProviderType,
)
from claimsflow.pipeline import BilingualEOB, MedicalNecessityVerdict
from claimsflow.pipeline.fraud_detection import FraudVerdict
from claimsflow.providers.base import LLMResponse


class _FakeProv:
    name = "fake"
    model = "fake-1"

    async def reason(self, system_prompt, user_prompt, response_schema):
        if response_schema is MedicalNecessityVerdict:
            data = MedicalNecessityVerdict(is_appropriate=True, confidence=0.92, reasoning="ok")
        elif response_schema is BilingualEOB:
            data = BilingualEOB(english="Approved.", arabic="تمت الموافقة.")
        elif response_schema is FraudVerdict:
            data = FraudVerdict(fraud_risk_score=5.0, signals=[], reasoning="clean")
        else:
            data = response_schema.model_construct()
        return LLMResponse(data=data, model=self.model, provider=self.name)


@pytest.fixture()
def cli_env(monkeypatch, tmp_path):
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    from claimsflow.core.config import get_settings
    from claimsflow.core.db import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    monkeypatch.setattr("claimsflow.pipeline.medical_necessity.get_llm_provider", lambda: _FakeProv())
    monkeypatch.setattr("claimsflow.pipeline.fraud_detection.get_llm_provider", lambda: _FakeProv())
    monkeypatch.setattr("claimsflow.pipeline.eob.get_llm_provider", lambda: _FakeProv())

    engine = get_engine()
    Base.metadata.create_all(engine)

    session = get_session_factory()()
    session.add_all([
        Plan(
            plan_id="PLN-CLI", plan_name="Gold CLI",
            covered_benefits=["outpatient"], exclusions=["F.*"],
            copay_percent=10.0,
            coverage_tiers={"preferred": 100.0, "standard": 80.0, "out_of_network": 0.0},
            annual_limit_default=200_000.0,
        ),
        Member(
            member_id="MBR-CLI", full_name_en="Test", full_name_ar="تجريبي",
            national_id="1234567890", dob=date(1985, 1, 1), gender="male",
            plan_id="PLN-CLI",
            policy_start=date.today() - timedelta(days=30),
            policy_end=date.today() + timedelta(days=300),
            policy_status=PolicyStatus.ACTIVE.value,
            annual_limit=200_000.0,
        ),
        Provider(
            provider_id="PRV-CLI", name_en="H", name_ar="م",
            provider_type=ProviderType.HOSPITAL.value,
            network_tier=NetworkTier.PREFERRED.value, city="Riyadh",
            license_number="MOH-RIY-1", license_expiry=date.today() + timedelta(days=365),
            contracted_rates={"99213": 250.0},
            fraud_risk_score=10.0,
        ),
    ])
    session.commit()
    session.close()

    return tmp_path


def test_cli_hello(cli_env) -> None:
    from claimsflow.cli.main import cli
    result = CliRunner().invoke(cli, ["hello"])
    assert result.exit_code == 0
    assert "scaffold OK" in result.output


def test_cli_stats_after_seed(cli_env) -> None:
    from claimsflow.cli.main import cli
    runner = CliRunner()
    r = runner.invoke(cli, ["stats"])
    assert r.exit_code == 0
    assert "plans" in r.output


def test_cli_process_single_file(cli_env, tmp_path) -> None:
    from claimsflow.cli.main import cli

    payload = {
        "claim_type": "outpatient",
        "member_id": "MBR-CLI",
        "provider_id": "PRV-CLI",
        "service_date": date.today().isoformat(),
        "diagnosis_codes": ["E11.9"],
        "procedure_codes": ["99213"],
        "line_items": [{"code": "99213", "description": "Visit", "quantity": 1, "unit_cost": 250.0}],
    }
    claim_file = tmp_path / "one.json"
    claim_file.write_text(json.dumps(payload))

    runner = CliRunner()
    r = runner.invoke(cli, ["process", str(claim_file)])
    assert r.exit_code == 0, r.output
    assert "Batch processing complete" in r.output


def test_cli_status_for_unknown_claim(cli_env) -> None:
    from claimsflow.cli.main import cli
    r = CliRunner().invoke(cli, ["status", "CLM-NOPE"])
    assert r.exit_code == 0
    assert "not found" in r.output


def test_cli_status_for_existing_claim(cli_env, tmp_path) -> None:
    from claimsflow.cli.main import cli

    # First process a claim so it exists.
    payload = {
        "claim_type": "outpatient",
        "member_id": "MBR-CLI",
        "provider_id": "PRV-CLI",
        "service_date": date.today().isoformat(),
        "diagnosis_codes": ["E11.9"],
        "procedure_codes": ["99213"],
        "line_items": [{"code": "99213", "description": "V", "quantity": 1, "unit_cost": 250.0}],
    }
    claim_file = tmp_path / "x.json"
    claim_file.write_text(json.dumps(payload))

    runner = CliRunner()
    proc = runner.invoke(cli, ["process", str(claim_file)])
    assert proc.exit_code == 0, proc.output

    # Grab the claim_id from output line "CLM-XXXXXXX"
    import re
    match = re.search(r"CLM-[A-F0-9]+", proc.output)
    assert match, proc.output
    claim_id = match.group(0)

    r = runner.invoke(cli, ["status", claim_id])
    assert r.exit_code == 0
    assert "Decision" in r.output
