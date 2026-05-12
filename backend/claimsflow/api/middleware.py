"""Custom middleware: request-id propagation + structured access logging."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from claimsflow.core.logging import get_logger


log = get_logger("claimsflow.api")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Stamp every request with a UUID (read X-Request-ID if the client sent one).

    The ID is bound into structlog's contextvars so every log line emitted
    during the request includes it. The same ID echoes back in the response
    header so the dashboard / n8n can correlate.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id

        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request.error", path=request.url.path, method=request.method)
            raise
        finally:
            structlog.contextvars.clear_contextvars()

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request.complete",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=round(elapsed_ms, 1),
            request_id=request_id,
        )
        return response
