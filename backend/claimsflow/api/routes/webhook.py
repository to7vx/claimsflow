"""n8n webhook entry point.

Authenticates the inbound webhook with HMAC SHA-256 over the raw body
(`X-ClaimsFlow-Signature: <hex>`). On success, hands off to the same
processing path as the regular submit endpoint.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from claimsflow.api.deps import db_session
from claimsflow.api.routes.claims import _process_in_background
from claimsflow.core.config import Settings, get_settings
from claimsflow.core.logging import get_logger
from claimsflow.models import Claim, ClaimStatus, ClaimSubmission

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])


class WebhookAccepted(BaseModel):
    claim_id: str
    accepted: bool


def _verify_hmac(raw_body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


@router.post("/n8n", response_model=WebhookAccepted)
async def n8n_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(db_session),
    settings: Settings = Depends(get_settings),
    x_claimsflow_signature: str | None = Header(default=None, alias="X-ClaimsFlow-Signature"),
) -> WebhookAccepted:
    raw_body = await request.body()
    if not _verify_hmac(raw_body, x_claimsflow_signature, settings.webhook_hmac_secret):
        log.warning("webhook.signature_invalid")
        raise HTTPException(status_code=401, detail="invalid HMAC signature")

    try:
        payload = ClaimSubmission.model_validate_json(raw_body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid payload: {exc}") from exc

    claim_id = f"CLM-{uuid.uuid4().hex[:10].upper()}"
    total_billed = sum(li.quantity * li.unit_cost for li in payload.line_items)
    claim = Claim(
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
        total_billed=total_billed,
        status=ClaimStatus.RECEIVED.value,
    )
    session.add(claim)
    session.flush()

    background_tasks.add_task(_process_in_background, claim_id)
    log.info("webhook.claim_accepted", claim_id=claim_id, source="n8n")
    return WebhookAccepted(claim_id=claim_id, accepted=True)
