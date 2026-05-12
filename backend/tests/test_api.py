"""Module 5 — FastAPI integration tests.

Uses FastAPI's TestClient against an in-memory SQLite DB. The pipeline's
LLM provider is replaced with a `FakeProvider` so tests are hermetic.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from claimsflow.api.app import create_app
from claimsflow.api.deps import db_session
from claimsflow.core.db import Base
from claimsflow.models import Claim, Member, Plan, Provider
from claimsflow.models.enums import (
    ClaimStatus,
    DecisionType,
    NetworkTier,
    PolicyStatus,
    ProviderType,
)
from claimsflow.pipeline import BilingualEOB, MedicalNecessityVerdict
from claimsflow.providers.base import LLMResponse


class FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self) -> None:
        self.calls = 0

    async def reason(self, system_prompt, user_prompt, response_schema):
        self.calls += 1
        if response_schema is MedicalNecessityVerdict:
            payload = MedicalNecessityVerdict(
                is_appropriate=True, confidence=0.94, reasoning="ok"
            )
        elif response_schema is BilingualEOB:
            payload = BilingualEOB(
                english="Your claim is approved.",
                arabic="تمت الموافقة على مطالبتك.",
            )
        else:
            # Fraud verdict etc.: produce something benign
            from claimsflow.pipeline.fraud_detection import FraudVerdict

            if response_schema is FraudVerdict:
                payload = FraudVerdict(fraud_risk_score=5.0, signals=[], reasoning="clean")
            else:
                payload = response_schema.model_construct()
        return LLMResponse(data=payload, model=self.model, provider=self.name)


@pytest.fixture()
def app_and_client(monkeypatch):
    # StaticPool + in-memory: every session shares ONE connection, so the
    # tables we create here are visible to background-task sessions too.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    fake = FakeProvider()
    monkeypatch.setattr("claimsflow.pipeline.medical_necessity.get_llm_provider", lambda: fake)
    monkeypatch.setattr("claimsflow.pipeline.fraud_detection.get_llm_provider", lambda: fake)
    monkeypatch.setattr("claimsflow.pipeline.eob.get_llm_provider", lambda: fake)
    # Background tasks open their own session via the global factory — point it at the test DB.
    monkeypatch.setattr("claimsflow.api.routes.claims.get_session_factory", lambda: TestingSession)

    app = create_app()

    def override_db():
        session = TestingSession()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[db_session] = override_db

    with TestClient(app) as client:
        # Seed minimal world
        with TestingSession() as s:
            s.add(Plan(
                plan_id="PLN-TEST", plan_name="Gold",
                covered_benefits=["outpatient"], exclusions=["F.*"],
                copay_percent=10.0,
                coverage_tiers={"preferred": 100.0, "standard": 80.0, "out_of_network": 0.0},
                annual_limit_default=200_000.0,
            ))
            s.add(Member(
                member_id="MBR-TEST", full_name_en="Test", full_name_ar="تجريبي",
                national_id="1234567890", dob=date(1985, 1, 1), gender="male",
                plan_id="PLN-TEST",
                policy_start=date.today() - timedelta(days=30),
                policy_end=date.today() + timedelta(days=300),
                policy_status=PolicyStatus.ACTIVE.value,
                annual_limit=200_000.0,
            ))
            s.add(Provider(
                provider_id="PRV-TEST", name_en="Hospital", name_ar="مستشفى",
                provider_type=ProviderType.HOSPITAL.value,
                network_tier=NetworkTier.PREFERRED.value, city="Riyadh",
                license_number="MOH-RIY-1", license_expiry=date.today() + timedelta(days=365),
                contracted_rates={"99213": 250.0},
                fraud_risk_score=10.0,
            ))
            s.commit()

        yield app, client, TestingSession


# ─────────────── Health ───────────────


def test_healthz(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_healthz_db(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/healthz/db")
    assert r.status_code == 200
    assert r.json() == {"db": "ok"}


def test_request_id_header_present(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/healthz")
    assert "x-request-id" in {k.lower() for k in r.headers}


# ─────────────── Auth ───────────────


def test_submit_requires_api_key(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.post("/api/v1/claims/submit", json=_valid_submission())
    assert r.status_code == 401


def test_submit_with_valid_key_accepted(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.post(
        "/api/v1/claims/submit",
        json=_valid_submission(),
        headers={"X-API-Key": "dev-local-key-change-me"},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["claim_id"].startswith("CLM-")
    assert body["status"] == "processing"


# ─────────────── Get/list ───────────────


def test_get_claim_404_when_unknown(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/api/v1/claims/CLM-DOES-NOT-EXIST")
    assert r.status_code == 404


def test_get_existing_claim(app_and_client) -> None:
    _, client, S = app_and_client
    with S() as s:
        s.add(Claim(
            claim_id="CLM-EXISTING", claim_type="outpatient",
            member_id="MBR-TEST", provider_id="PRV-TEST",
            service_date=date.today(), diagnosis_codes=["E11.9"],
            procedure_codes=["99213"],
            line_items=[{"code": "99213", "description": "v", "quantity": 1, "unit_cost": 250.0}],
            total_billed=250.0, status=ClaimStatus.APPROVED.value,
        ))
        s.commit()

    r = client.get("/api/v1/claims/CLM-EXISTING")
    assert r.status_code == 200
    assert r.json()["claim"]["claim_id"] == "CLM-EXISTING"


def test_list_claims_filters_by_status(app_and_client) -> None:
    _, client, S = app_and_client
    with S() as s:
        for i, status in enumerate([
            ClaimStatus.APPROVED.value, ClaimStatus.REVIEW.value, ClaimStatus.APPROVED.value
        ]):
            s.add(Claim(
                claim_id=f"CLM-LIST-{i}", claim_type="outpatient",
                member_id="MBR-TEST", provider_id="PRV-TEST",
                service_date=date.today(), diagnosis_codes=["E11.9"],
                procedure_codes=["99213"],
                line_items=[{"code": "99213", "description": "v", "quantity": 1, "unit_cost": 250.0}],
                total_billed=250.0, status=status,
            ))
        s.commit()

    r = client.get("/api/v1/claims", params={"status": "approved"})
    assert r.status_code == 200
    body = r.json()
    assert all(item["status"] == "approved" for item in body["items"])


# ─────────────── Override ───────────────


def test_override_requires_api_key(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.post("/api/v1/claims/CLM-WHATEVER/review", json={
        "decision": "approve", "reviewer_id": "u1"
    })
    assert r.status_code == 401


# ─────────────── Queues ───────────────


def test_exception_queue_returns_review_only(app_and_client) -> None:
    _, client, S = app_and_client
    with S() as s:
        s.add(Claim(
            claim_id="CLM-EXC-1", claim_type="outpatient",
            member_id="MBR-TEST", provider_id="PRV-TEST",
            service_date=date.today() - timedelta(days=2),
            diagnosis_codes=["E11.9"], procedure_codes=["99213"],
            line_items=[{"code": "99213", "description": "v", "quantity": 1, "unit_cost": 250.0}],
            total_billed=250.0, status=ClaimStatus.REVIEW.value,
        ))
        s.add(Claim(
            claim_id="CLM-APP-1", claim_type="outpatient",
            member_id="MBR-TEST", provider_id="PRV-TEST",
            service_date=date.today(), diagnosis_codes=["E11.9"], procedure_codes=["99213"],
            line_items=[{"code": "99213", "description": "v", "quantity": 1, "unit_cost": 250.0}],
            total_billed=250.0, status=ClaimStatus.APPROVED.value,
        ))
        s.commit()

    r = client.get("/api/v1/queue/exceptions")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["claim"]["claim_id"] == "CLM-EXC-1"


# ─────────────── Metrics ───────────────


def test_overview_metrics_shape(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/api/v1/metrics/overview")
    assert r.status_code == 200
    body = r.json()
    assert {"total_claims", "auto_adjudication_rate", "pending_exceptions"} <= set(body)


def test_decision_breakdown_empty_ok(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/api/v1/metrics/decisions")
    assert r.status_code == 200
    assert r.json() == []


# ─────────────── Webhook ───────────────


def test_webhook_rejects_bad_signature(app_and_client) -> None:
    _, client, _ = app_and_client
    payload = _valid_submission()
    r = client.post(
        "/api/v1/webhook/n8n",
        content=json.dumps(payload),
        headers={"X-ClaimsFlow-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert r.status_code == 401


def test_webhook_accepts_valid_signature(app_and_client) -> None:
    _, client, _ = app_and_client
    payload = _valid_submission()
    body = json.dumps(payload).encode()
    secret = "dev-hmac-secret-change-me"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    r = client.post(
        "/api/v1/webhook/n8n",
        content=body,
        headers={"X-ClaimsFlow-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is True


# ─────────────── Providers ───────────────


def test_top_providers_by_volume(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/api/v1/providers/top", params={"metric": "volume", "limit": 5})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_top_providers_by_risk(app_and_client) -> None:
    _, client, _ = app_and_client
    r = client.get("/api/v1/providers/top", params={"metric": "risk", "limit": 5})
    assert r.status_code == 200


# ─────────────── Helpers ───────────────


def _valid_submission() -> dict:
    return {
        "claim_type": "outpatient",
        "member_id": "MBR-TEST",
        "provider_id": "PRV-TEST",
        "service_date": date.today().isoformat(),
        "diagnosis_codes": ["E11.9"],
        "procedure_codes": ["99213"],
        "line_items": [
            {"code": "99213", "description": "Visit", "quantity": 1, "unit_cost": 250.0}
        ],
    }
