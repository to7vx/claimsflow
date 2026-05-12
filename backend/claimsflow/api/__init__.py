"""FastAPI application.

Public entry point:
- `app` — the ASGI application instance
- `create_app()` — factory used by tests
"""

from claimsflow.api.app import app, create_app

__all__ = ["app", "create_app"]
