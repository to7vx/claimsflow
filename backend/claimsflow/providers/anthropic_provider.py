"""Anthropic Claude provider.

Uses tool-use to coerce structured output: we register a single "tool" whose
input_schema is the Pydantic schema's JSON schema, then force the model to
call it. The tool's input is the structured answer.

This is more reliable than asking for JSON in the prompt and parsing it,
and works across Claude model families.
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from claimsflow.core.logging import get_logger
from claimsflow.providers.base import (
    LLMProvider,
    LLMResponse,
    LLMResponseParseError,
    TokenUsage,
)

T = TypeVar("T", bound=BaseModel)

log = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for AnthropicProvider")
        # Import locally so unconfigured installs (no anthropic key) don't pay
        # the import cost.
        from anthropic import AsyncAnthropic

        self.model = model
        self._client = AsyncAnthropic(api_key=api_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def reason(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
    ) -> LLMResponse[T]:
        tool_name = "submit_decision"
        tool: dict[str, Any] = {
            "name": tool_name,
            "description": f"Submit a structured {response_schema.__name__} response.",
            "input_schema": response_schema.model_json_schema(),
        }

        t0 = time.perf_counter()
        result = await self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user_prompt}],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        tool_use = next((b for b in result.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise LLMResponseParseError(
                "Anthropic response contained no tool_use block — model refused or errored."
            )

        return LLMResponse(
            data=response_schema.model_validate(tool_use.input),
            usage=TokenUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            ),
            latency_ms=round(elapsed_ms, 1),
            model=self.model,
            provider=self.name,
        )
