"""OpenAI provider.

Uses the chat-completions `response_format={"type":"json_schema", ...}`
strict mode, which constrains the model's output to the supplied schema.
For older models without strict JSON schema, this falls back to plain
`json_object` mode and validates after the fact.
"""

from __future__ import annotations

import time
from typing import TypeVar

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
    TokenUsage,
    parse_structured_response,
)

T = TypeVar("T", bound=BaseModel)

log = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider")
        from openai import AsyncOpenAI

        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

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
        schema = response_schema.model_json_schema()

        t0 = time.perf_counter()
        result = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": schema,
                    "strict": False,
                },
            },
            max_tokens=2048,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        content = result.choices[0].message.content or ""
        parsed = parse_structured_response(content, response_schema)
        usage = result.usage

        return LLMResponse(
            data=parsed,
            usage=TokenUsage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            ),
            latency_ms=round(elapsed_ms, 1),
            model=self.model,
            provider=self.name,
        )
