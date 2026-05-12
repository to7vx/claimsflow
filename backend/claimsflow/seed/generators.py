"""Synthetic data generators for ClaimsFlow.

Each `generate_*` function returns a list of ORM instances (not yet attached
to a session). The caller wires them up and commits. Determinism is
controlled by a single `random.Random(seed)` — pass the same seed to get
the same dataset, useful for tests and benchmarks.

Volume modes:
- `small`: 5 plans / 20 providers / 50 members / 100 claims (fast smoke tests)
- `full`:  50 / 200 / 500 / 1000 (per the build spec)

Realism rules:
- 95% of members have ACTIVE policies; 4% SUSPENDED, 1% EXPIRED.
- 5% of claims are fraud-pattern (duplicates, velocity, amount anomalies).
- ~15% are exception cases (out-of-network, soft flags).
- Pediatric diagnoses appear on ~20% of claims, modelling family plans.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from claimsflow.models.enums import (
    ClaimStatus,
    ClaimType,
    Gender,
    NetworkTier,
    PolicyStatus,
    ProviderType,
)
from claimsflow.models.orm import Claim, Member, Plan, Provider
from claimsflow.seed.reference_data import (
    APPROPRIATE_PROCEDURES,
    CPT_COMMON,
    FAMILY_NAMES_AR,
    FAMILY_NAMES_EN,
    FEMALE_NAMES_AR,
    FEMALE_NAMES_EN,
    ICD10_COMMON,
    ICD10_PEDIATRIC,
    MALE_NAMES_AR,
    MALE_NAMES_EN,
    PLAN_TEMPLATES,
    PROVIDER_NAME_PREFIXES_AR,
    PROVIDER_NAME_PREFIXES_EN,
    SAUDI_CITIES,
)


# ─────────────────────────── Volume profile ───────────────────────────


@dataclass(frozen=True)
class Volume:
    plans: int
    providers: int
    members: int
    claims: int


VOLUME_SMALL = Volume(plans=5, providers=20, members=50, claims=100)
VOLUME_FULL = Volume(plans=50, providers=200, members=500, claims=1000)


def get_volume(mode: str) -> Volume:
    if mode == "small":
        return VOLUME_SMALL
    if mode == "full":
        return VOLUME_FULL
    raise ValueError(f"unknown seed volume mode: {mode!r} (expected 'small' or 'full')")


# ─────────────────────────── Plans ───────────────────────────


def generate_plans(rng: random.Random, n: int) -> list[Plan]:
    """Cycles through the 4 plan templates, varying annual limits ±20%."""
    plans: list[Plan] = []
    for i in range(n):
        template = PLAN_TEMPLATES[i % len(PLAN_TEMPLATES)]
        jitter = rng.uniform(0.8, 1.2)
        plan = Plan(
            plan_id=f"PLN-{i + 1:04d}",
            plan_name=f"{template['name_en']} {chr(65 + (i // len(PLAN_TEMPLATES)))}",
            covered_benefits=list(template["covered"]),
            exclusions=list(template["exclusions"]),
            copay_percent=template["copay_percent"],
            coverage_tiers={
                "preferred": 100.0,
                "standard": 80.0,
                "out_of_network": 0.0,
            },
            annual_limit_default=round(template["annual_limit"] * jitter, 2),
        )
        plans.append(plan)
    return plans


# ─────────────────────────── Providers ───────────────────────────


def _provider_name(rng: random.Random, city: str) -> tuple[str, str]:
    idx = rng.randrange(len(PROVIDER_NAME_PREFIXES_EN))
    return (
        f"{city} {PROVIDER_NAME_PREFIXES_EN[idx]} Medical Center",
        f"مركز {city} {PROVIDER_NAME_PREFIXES_AR[idx]} الطبي",
    )


def generate_providers(rng: random.Random, n: int) -> list[Provider]:
    providers: list[Provider] = []
    tier_weights = [
        (NetworkTier.PREFERRED.value, 0.55),
        (NetworkTier.STANDARD.value, 0.35),
        (NetworkTier.OUT_OF_NETWORK.value, 0.10),
    ]
    for i in range(n):
        city = rng.choice(SAUDI_CITIES)
        name_en, name_ar = _provider_name(rng, city)
        ptype = rng.choices(
            [pt.value for pt in ProviderType],
            weights=[0.4, 0.4, 0.1, 0.1],
        )[0]
        tier = rng.choices([t for t, _ in tier_weights], weights=[w for _, w in tier_weights])[0]

        # Contracted rates: vary ±15% off the canonical CPT rate.
        rates = {
            code: round(price * rng.uniform(0.85, 1.15), 2)
            for code, (_, price) in CPT_COMMON.items()
        }
        # Suspicious providers (5%) get a high baseline fraud risk score.
        fraud_risk = rng.gauss(15, 8) if rng.random() > 0.05 else rng.uniform(60, 85)
        fraud_risk = max(0.0, min(100.0, fraud_risk))

        providers.append(
            Provider(
                provider_id=f"PRV-{i + 1:04d}",
                name_en=name_en,
                name_ar=name_ar,
                provider_type=ptype,
                network_tier=tier,
                city=city,
                license_number=f"MOH-{city[:3].upper()}-{rng.randint(1000, 9999)}",
                license_expiry=date.today() + timedelta(days=rng.randint(-30, 1200)),
                contracted_rates=rates,
                performance_score=max(0.0, min(100.0, rng.gauss(75, 12))),
                fraud_risk_score=round(fraud_risk, 2),
            )
        )
    return providers


# ─────────────────────────── Members ───────────────────────────


def _arabic_name(rng: random.Random, gender: str) -> tuple[str, str]:
    if gender == Gender.MALE.value:
        first_ar = rng.choice(MALE_NAMES_AR)
        first_en = MALE_NAMES_EN[MALE_NAMES_AR.index(first_ar)]
    else:
        first_ar = rng.choice(FEMALE_NAMES_AR)
        first_en = FEMALE_NAMES_EN[FEMALE_NAMES_AR.index(first_ar)]
    fam_idx = rng.randrange(len(FAMILY_NAMES_AR))
    family_ar, family_en = FAMILY_NAMES_AR[fam_idx], FAMILY_NAMES_EN[fam_idx]
    return f"{first_ar} {family_ar}", f"{first_en} {family_en}"


def generate_members(rng: random.Random, n: int, plans: list[Plan]) -> list[Member]:
    """Members across active/suspended/expired statuses, with realistic ages."""
    members: list[Member] = []
    today = date.today()
    for i in range(n):
        gender = rng.choices(
            [Gender.MALE.value, Gender.FEMALE.value],
            weights=[0.52, 0.48],
        )[0]
        name_ar, name_en = _arabic_name(rng, gender)
        age = rng.choices(
            [rng.randint(0, 17), rng.randint(18, 64), rng.randint(65, 85)],
            weights=[0.25, 0.65, 0.10],
        )[0]
        dob = today - timedelta(days=age * 365 + rng.randint(0, 364))

        plan = rng.choice(plans)
        status = rng.choices(
            [PolicyStatus.ACTIVE.value, PolicyStatus.SUSPENDED.value, PolicyStatus.EXPIRED.value],
            weights=[0.95, 0.04, 0.01],
        )[0]
        if status == PolicyStatus.EXPIRED.value:
            policy_start = today - timedelta(days=rng.randint(800, 1500))
            policy_end = today - timedelta(days=rng.randint(30, 200))
        else:
            policy_start = today - timedelta(days=rng.randint(30, 365))
            policy_end = policy_start + timedelta(days=365)

        used = round(rng.uniform(0, plan.annual_limit_default * 0.6), 2)
        deductible = 0.0 if plan.copay_percent == 0 else rng.choice([0.0, 500.0, 1000.0, 3000.0])

        members.append(
            Member(
                member_id=f"MBR-{i + 1:05d}",
                full_name_en=name_en,
                full_name_ar=name_ar,
                national_id=f"1{rng.randint(10**9, 10**10 - 1)}"[:10],
                dob=dob,
                gender=gender,
                plan_id=plan.plan_id,
                policy_start=policy_start,
                policy_end=policy_end,
                policy_status=status,
                annual_limit=plan.annual_limit_default,
                used_amount=used,
                deductible=deductible,
                deductible_met=round(rng.uniform(0, deductible), 2) if deductible else 0.0,
            )
        )
    return members


# ─────────────────────────── Claims ───────────────────────────


def _line_items_for(
    rng: random.Random, diagnosis: str, fraud_amount_inflation: float = 1.0
) -> tuple[list[dict], list[str], float]:
    """Build line items matched to the diagnosis (or mismatched on purpose for fraud)."""
    candidates = APPROPRIATE_PROCEDURES.get(diagnosis, ["99213"])
    n_items = rng.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
    chosen = rng.sample(candidates, k=min(n_items, len(candidates)))

    line_items: list[dict] = []
    total = 0.0
    for code in chosen:
        desc, base_price = CPT_COMMON.get(code, (f"Procedure {code}", 200.0))
        qty = 1
        unit_cost = round(base_price * rng.uniform(0.9, 1.2) * fraud_amount_inflation, 2)
        total += qty * unit_cost
        line_items.append(
            {"code": code, "description": desc, "quantity": qty, "unit_cost": unit_cost}
        )
    return line_items, chosen, round(total, 2)


def generate_claims(
    rng: random.Random,
    n: int,
    members: list[Member],
    providers: list[Provider],
) -> list[Claim]:
    """Generate a mix of routine + fraud + exception claims.

    Distribution (per build spec):
    - ~5% fraud patterns  (50 of 1000)
    - ~15% exception cases (150 of 1000)
    - ~80% routine
    """
    fraud_n = max(1, n // 20)
    exception_n = max(1, n * 15 // 100)
    routine_n = n - fraud_n - exception_n

    claims: list[Claim] = []
    today = date.today()

    # ── Routine claims ──────────────────────────────────────────
    for _ in range(routine_n):
        member = rng.choice([m for m in members if m.policy_status == PolicyStatus.ACTIVE.value])
        provider = rng.choices(
            providers,
            weights=[3 if p.network_tier == NetworkTier.PREFERRED.value else 1 for p in providers],
        )[0]
        # Pediatric pull for child members.
        is_pediatric = (today.year - member.dob.year) < 18
        dx_pool = ICD10_PEDIATRIC if is_pediatric else ICD10_COMMON
        diagnosis = rng.choice([d for d in dx_pool if d != "F32.9"])  # exclude depression here
        line_items, procs, total = _line_items_for(rng, diagnosis)
        claims.append(
            _build_claim(
                rng,
                member,
                provider,
                diagnosis,
                procs,
                line_items,
                total,
                service_date=today - timedelta(days=rng.randint(0, 120)),
            )
        )

    # ── Exception claims (out-of-network, soft flags) ──────────
    for _ in range(exception_n):
        member = rng.choice(members)
        # Force out-of-network provider OR suspended member
        if rng.random() < 0.5:
            oon = [p for p in providers if p.network_tier == NetworkTier.OUT_OF_NETWORK.value]
            provider = rng.choice(oon) if oon else rng.choice(providers)
        else:
            provider = rng.choice(providers)
        diagnosis = rng.choice(list(ICD10_COMMON.keys()))
        line_items, procs, total = _line_items_for(rng, diagnosis, fraud_amount_inflation=1.4)
        claims.append(
            _build_claim(
                rng,
                member,
                provider,
                diagnosis,
                procs,
                line_items,
                total,
                service_date=today - timedelta(days=rng.randint(0, 60)),
            )
        )

    # ── Fraud claims ──────────────────────────────────────────
    # Mix of patterns: duplicate-style (same member+provider+date), velocity
    # (one provider blasting many claims same hour), and procedure-diagnosis
    # mismatch.
    fraud_provider = max(providers, key=lambda p: p.fraud_risk_score)
    velocity_member = rng.choice(
        [m for m in members if m.policy_status == PolicyStatus.ACTIVE.value]
    )
    velocity_date = today - timedelta(days=rng.randint(0, 7))
    for i in range(fraud_n):
        pattern = i % 3
        if pattern == 0:
            # Velocity: same provider, same day, many distinct members
            member = rng.choice(members)
            provider = fraud_provider
            diagnosis = rng.choice(list(ICD10_COMMON.keys()))
            line_items, procs, total = _line_items_for(rng, diagnosis, fraud_amount_inflation=1.8)
            service_date = velocity_date
        elif pattern == 1:
            # Duplicate-style: same member-provider-procedure within 7 days
            member = velocity_member
            provider = fraud_provider
            diagnosis = "E11.9"
            line_items, procs, total = _line_items_for(rng, diagnosis, fraud_amount_inflation=2.0)
            service_date = today - timedelta(days=rng.randint(0, 6))
        else:
            # Mismatch: pediatric diagnosis on an elderly member
            elderly = [
                m for m in members if (today.year - m.dob.year) > 60
            ] or members
            member = rng.choice(elderly)
            provider = fraud_provider
            diagnosis = rng.choice(list(ICD10_PEDIATRIC.keys()))
            line_items, procs, total = _line_items_for(rng, diagnosis, fraud_amount_inflation=2.2)
            service_date = today - timedelta(days=rng.randint(0, 5))

        claims.append(
            _build_claim(
                rng, member, provider, diagnosis, procs, line_items, total, service_date,
                flagged_fraud=True,
            )
        )

    rng.shuffle(claims)
    return claims


def _build_claim(
    rng: random.Random,
    member: Member,
    provider: Provider,
    diagnosis: str,
    procedure_codes: list[str],
    line_items: list[dict],
    total: float,
    service_date: date,
    flagged_fraud: bool = False,
) -> Claim:
    claim_type = rng.choices(
        [ClaimType.OUTPATIENT.value, ClaimType.INPATIENT.value, ClaimType.PHARMACY.value],
        weights=[0.75, 0.15, 0.10],
    )[0]
    # Deterministic claim id: 10 hex chars drawn from the seeded RNG so the
    # same seed always reproduces the same dataset. Collision space is 16**10
    # which is large enough for 1000-row test datasets.
    claim_suffix = "".join(rng.choice("0123456789ABCDEF") for _ in range(10))
    return Claim(
        claim_id=f"CLM-{claim_suffix}",
        claim_type=claim_type,
        member_id=member.member_id,
        provider_id=provider.provider_id,
        service_date=service_date,
        submission_date=datetime.utcnow(),
        diagnosis_codes=[diagnosis],
        procedure_codes=procedure_codes,
        line_items=line_items,
        clinical_notes=(
            f"Patient presented with symptoms consistent with {diagnosis}."
            + (" (flagged: anomaly pattern)" if flagged_fraud else "")
        ),
        total_billed=total,
        status=ClaimStatus.RECEIVED.value,
    )
