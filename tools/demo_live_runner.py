"""Live-demo batch runner.

Submits 10 mixed claims inside a single Python process so the
dashboard's Live Activity panel can update at a watchable pace.
Pure ADD-ON — does not modify pipeline or API code.

Usage (from repo root):
    backend/.venv/Scripts/python.exe tools/demo_live_runner.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
CLAIMS_DIR = REPO_ROOT / "demo_claims"

# Make backend importable when run from the repo root.
sys.path.insert(0, str(BACKEND))

from claimsflow.core.db import get_session_factory  # noqa: E402
from claimsflow.models import Claim, ClaimStatus, ClaimSubmission  # noqa: E402
from claimsflow.pipeline import process_claim  # noqa: E402

# Sequence: clean → clean variant → mismatch → clean variant → 6× fraud build-up
SEQUENCE: list[tuple[str, str]] = [
    ("Clean approval",          "01_clean_approval.json"),
    ("Clean approval variant",  "01b_clean_approval.json"),
    ("Diagnosis mismatch",      "02_mismatch_human_review.json"),
    ("Clean approval variant",  "01c_clean_approval.json"),
    ("Routine visit",           "03a_fraud_velocity.json"),
    ("Routine visit",           "03b_fraud_velocity.json"),
    ("Routine visit",           "03c_fraud_velocity.json"),
    ("Routine visit",           "03d_fraud_velocity.json"),
    ("Routine visit",           "03e_fraud_velocity.json"),
    ("Routine visit",           "03f_fraud_velocity.json"),
]

GAP_SECONDS = 2.0


def build_claim(payload: ClaimSubmission) -> Claim:
    """Same shape as the CLI process command — kept local to avoid coupling."""
    claim_id = f"CLM-{uuid.uuid4().hex[:10].upper()}"
    total = sum(li.quantity * li.unit_cost for li in payload.line_items)
    return Claim(
        claim_id=claim_id,
        claim_type=payload.claim_type.value,
        member_id=payload.member_id,
        provider_id=payload.provider_id,
        service_date=payload.service_date,
        submission_date=datetime.utcnow(),
        diagnosis_codes=payload.diagnosis_codes,
        procedure_codes=payload.procedure_codes,
        line_items=[li.model_dump() for li in payload.line_items],
        clinical_notes=payload.clinical_notes,
        total_billed=total,
        status=ClaimStatus.RECEIVED.value,
    )


async def submit_one(session, file_path: Path) -> tuple[str, str]:
    payload = ClaimSubmission.model_validate_json(file_path.read_text(encoding="utf-8"))
    claim = build_claim(payload)
    session.add(claim)
    session.flush()
    decision = await process_claim(session, claim.claim_id)
    session.commit()
    return claim.claim_id, decision.decision_type


async def main() -> None:
    print()
    print("=" * 64)
    print("  ClaimsFlow Live Demo")
    print("  Submitting 10 mixed claims (watch the dashboard light up)")
    print("=" * 64)
    print()

    if not CLAIMS_DIR.is_dir():
        print(f"[ERROR] demo_claims directory not found: {CLAIMS_DIR}")
        sys.exit(1)

    session = get_session_factory()()
    results: list[tuple[int, str, str, str]] = []
    t0 = time.perf_counter()
    try:
        for i, (label, fname) in enumerate(SEQUENCE, start=1):
            path = CLAIMS_DIR / fname
            if not path.exists():
                print(f"[{i:>2}/10] SKIP — file not found: {path}")
                continue
            print(f"[{i:>2}/10] {label:<26s} {fname}")
            sys.stdout.flush()
            cid, dt = await submit_one(session, path)
            print(f"        -> {cid}   decision={dt}")
            results.append((i, label, cid, dt))
            if i < len(SEQUENCE):
                await asyncio.sleep(GAP_SECONDS)
    finally:
        session.close()

    elapsed = time.perf_counter() - t0
    print()
    print("=" * 64)
    print(f"  Done. 10 submissions in {elapsed:.1f}s")
    print("=" * 64)
    print()
    print(f"{'#':>3}  {'scenario':<26}  {'claim_id':<18}  decision")
    for i, label, cid, dt in results:
        print(f"{i:>3}  {label:<26}  {cid:<18}  {dt}")


if __name__ == "__main__":
    asyncio.run(main())
