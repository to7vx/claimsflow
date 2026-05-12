"""Abstract LLM provider interface + shared types.

All three providers (Anthropic / OpenAI / Ollama) implement `LLMProvider.reason`,
which takes a system prompt, a user prompt, and a Pydantic schema describing
the expected response. The provider returns an instance of that schema —
parsing, retry, and provider-specific structured-output mechanics are
hidden behind this contract.

Why a Protocol and not an ABC: callers don't care about inheritance, only
that the call shape matches. Protocols also play better with `pytest`
mocks and `unittest.mock.AsyncMock`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

from claimsflow.core.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class TokenUsage:
    """Token accounting for a single LLM call. All providers should populate."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResponse(Generic[T]):
    """What `reason()` returns. The structured `data` is the main payload;
    `usage` and `latency_ms` are for observability."""

    data: T
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    model: str = ""
    provider: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    """The single method ClaimsFlow asks of any LLM provider."""

    name: str
    model: str

    async def reason(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
    ) -> LLMResponse[T]:
        """Send the two prompts, get back a validated instance of `response_schema`."""
        ...


# ───────────────────────── Helpers ─────────────────────────


class LLMResponseParseError(RuntimeError):
    """The model returned text that didn't parse / validate against the schema."""


def parse_structured_response(raw_text: str, schema: type[T]) -> T:
    """Best-effort: try strict JSON, then extract the first JSON object substring.

    Local models (Ollama) often wrap JSON in prose or markdown fences. This
    helper does the minimum cleanup needed without being clever.
    """
    raw_text = raw_text.strip()

    # Strip ```json ... ``` fences if present.
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if len(lines) >= 2:
            raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        # Fall back: locate the first {...} block by brace matching.
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMResponseParseError(
                f"could not locate JSON in model response: {raw_text[:200]!r}"
            ) from None
        try:
            payload = json.loads(raw_text[start : end + 1])
        except json.JSONDecodeError as e:
            raise LLMResponseParseError(f"JSON decode failed: {e}") from e

    try:
        return schema.model_validate(payload)
    except ValidationError as e:
        raise LLMResponseParseError(
            f"response did not validate against {schema.__name__}: {e}"
        ) from e


async def time_call(fn: Callable[[], Awaitable[Any]], label: str) -> tuple[Any, float]:
    """Measure wall-clock latency of an async call. Returns (result, ms)."""
    t0 = time.perf_counter()
    result = await fn()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    log.debug("llm.call", label=label, latency_ms=round(elapsed_ms, 1))
    return result, elapsed_ms
