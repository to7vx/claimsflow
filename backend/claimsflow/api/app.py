"""FastAPI application factory.

Built as a factory so tests can pass override settings without monkey-
patching globals.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from claimsflow import __version__
from claimsflow.api.middleware import RequestIDMiddleware
from claimsflow.api.routes import claims, demo, health, metrics, providers, queue, webhook
from claimsflow.core.config import get_settings
from claimsflow.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="ClaimsFlow API",
        version=__version__,
        description=(
            "Auto-adjudication API for medical insurance claims. "
            "Supports real-time webhook + batch CLI integration."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )

    # ── Rate limiting ──
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.api_rate_limit_per_minute}/minute"],
    )
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded"},
        ),
    )
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ── Custom middleware ──
    app.add_middleware(RequestIDMiddleware)

    # ── Routers ──
    app.include_router(health.router)
    app.include_router(claims.router)
    app.include_router(queue.router)
    app.include_router(metrics.router)
    app.include_router(providers.router)
    app.include_router(webhook.router)
    app.include_router(demo.router)

    return app


# Default ASGI app for `uvicorn claimsflow.api.app:app`.
app = create_app()
