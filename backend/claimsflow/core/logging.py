"""Structured JSON logging via structlog.

All app logs go through this. In dev we render colorized key=value pairs;
in production (`APP_ENV=production`) we emit single-line JSON for log shippers.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from claimsflow.core.config import get_settings


def configure_logging() -> None:
    """Initialize structlog. Idempotent — safe to call multiple times."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_env == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound logger. Pass the calling module's __name__."""
    return structlog.get_logger(name)
