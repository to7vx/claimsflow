"""Ollama (local) provider — the BYOK-free default.

Talks to a local Ollama server over HTTP. Ollama supports a `format: json`
mode that constrains output to valid JSON; we additionally embed the
target schema in the system prompt for stronger adherence.

Token usage from Ollama comes as `prompt_eval_count` / `eval_count`.
"""

from __future__ import annotations

import json
import time
from typing import TypeVar

import httpx
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
    parse_structured_response,
)

T = TypeVar("T", bound=BaseModel)

log = get_logger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_s: float = 120.0) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, LLMResponseParseError)),
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
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
        full_system = (
            f"{system_prompt}\n\n"
            "You MUST respond with valid JSON matching this schema exactly. "
            "Do not include any text outside the JSON.\n\n"
            f"```json\n{schema_json}\n```"
        )

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.1},
        }

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            body = resp.json()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        content = body.get("message", {}).get("content", "")
        if not content:
            raise LLMResponseParseError(f"Ollama returned no content: {body!r}")

        parsed = parse_structured_response(content, response_schema)
        return LLMResponse(
            data=parsed,
            usage=TokenUsage(
                input_tokens=int(body.get("prompt_eval_count", 0)),
                output_tokens=int(body.get("eval_count", 0)),
            ),
            latency_ms=round(elapsed_ms, 1),
            model=self.model,
            provider=self.name,
        )
