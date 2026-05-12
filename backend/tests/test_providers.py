"""Module 3 — LLM provider abstraction.

Mocked unit tests cover all three providers + the parser + the router.
Real-network integration tests are marked `@pytest.mark.integration` and
skipped unless the respective env var is set.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import BaseModel

from claimsflow.providers import (
    LLMProvider,
    LLMResponseParseError,
    TokenUsage,
    parse_structured_response,
)
from claimsflow.providers.router import get_llm_provider, reset_provider_cache


# ─────────────── Shared fixture schema ───────────────


class Verdict(BaseModel):
    is_appropriate: bool
    confidence: float
    reasoning: str


# ─────────────── parse_structured_response ───────────────


def test_parser_accepts_plain_json() -> None:
    out = parse_structured_response(
        '{"is_appropriate": true, "confidence": 0.9, "reasoning": "fine"}', Verdict
    )
    assert out.is_appropriate is True
    assert out.confidence == 0.9


def test_parser_strips_markdown_fences() -> None:
    raw = '```json\n{"is_appropriate": false, "confidence": 0.4, "reasoning": "x"}\n```'
    out = parse_structured_response(raw, Verdict)
    assert out.is_appropriate is False


def test_parser_extracts_from_surrounding_prose() -> None:
    raw = 'Sure, here you go: {"is_appropriate": true, "confidence": 0.7, "reasoning": "ok"} done.'
    out = parse_structured_response(raw, Verdict)
    assert out.confidence == 0.7


def test_parser_raises_when_no_json_found() -> None:
    with pytest.raises(LLMResponseParseError):
        parse_structured_response("Nope, no JSON here at all.", Verdict)


def test_parser_raises_when_schema_mismatches() -> None:
    raw = '{"foo": "bar"}'
    with pytest.raises(LLMResponseParseError):
        parse_structured_response(raw, Verdict)


# ─────────────── AnthropicProvider (mocked) ───────────────


@pytest.mark.asyncio
async def test_anthropic_provider_returns_structured_output(monkeypatch) -> None:
    from claimsflow.providers.anthropic_provider import AnthropicProvider

    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = {
        "is_appropriate": True,
        "confidence": 0.92,
        "reasoning": "matches diagnosis",
    }
    fake_result = MagicMock()
    fake_result.content = [tool_use_block]
    fake_result.usage = MagicMock(input_tokens=120, output_tokens=45)

    provider = AnthropicProvider(api_key="sk-test", model="claude-haiku-4-5")
    provider._client.messages.create = AsyncMock(return_value=fake_result)

    response = await provider.reason("system", "user", Verdict)

    assert response.data.is_appropriate is True
    assert response.data.confidence == 0.92
    assert response.usage.input_tokens == 120
    assert response.provider == "anthropic"
    assert response.latency_ms >= 0


def test_anthropic_requires_api_key() -> None:
    from claimsflow.providers.anthropic_provider import AnthropicProvider

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(api_key="", model="claude-haiku-4-5")


@pytest.mark.asyncio
async def test_anthropic_raises_when_no_tool_use_block() -> None:
    from claimsflow.providers.anthropic_provider import AnthropicProvider

    text_block = MagicMock()
    text_block.type = "text"
    fake_result = MagicMock()
    fake_result.content = [text_block]
    fake_result.usage = MagicMock(input_tokens=10, output_tokens=5)

    provider = AnthropicProvider(api_key="sk-test", model="claude-haiku-4-5")
    provider._client.messages.create = AsyncMock(return_value=fake_result)

    with pytest.raises(LLMResponseParseError):
        await provider.reason("system", "user", Verdict)


# ─────────────── OpenAIProvider (mocked) ───────────────


@pytest.mark.asyncio
async def test_openai_provider_returns_structured_output() -> None:
    from claimsflow.providers.openai_provider import OpenAIProvider

    fake_choice = MagicMock()
    fake_choice.message.content = json.dumps(
        {"is_appropriate": False, "confidence": 0.3, "reasoning": "mismatch"}
    )
    fake_result = MagicMock()
    fake_result.choices = [fake_choice]
    fake_result.usage = MagicMock(prompt_tokens=80, completion_tokens=20)

    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
    provider._client.chat.completions.create = AsyncMock(return_value=fake_result)

    response = await provider.reason("system", "user", Verdict)

    assert response.data.is_appropriate is False
    assert response.data.confidence == 0.3
    assert response.usage.output_tokens == 20
    assert response.provider == "openai"


def test_openai_requires_api_key() -> None:
    from claimsflow.providers.openai_provider import OpenAIProvider

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key="", model="gpt-4o-mini")


# ─────────────── OllamaProvider (mocked) ───────────────


@pytest.mark.asyncio
async def test_ollama_provider_parses_json_response(monkeypatch) -> None:
    from claimsflow.providers.ollama_provider import OllamaProvider

    fake_body = {
        "message": {
            "content": json.dumps(
                {"is_appropriate": True, "confidence": 0.88, "reasoning": "looks good"}
            )
        },
        "prompt_eval_count": 200,
        "eval_count": 50,
    }
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(return_value=fake_body)

    async_post = AsyncMock(return_value=fake_response)

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return await async_post(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: FakeClient())

    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1:8b")
    response = await provider.reason("system", "user", Verdict)

    assert response.data.is_appropriate is True
    assert response.data.confidence == 0.88
    assert response.usage.input_tokens == 200
    assert response.usage.output_tokens == 50
    assert response.provider == "ollama"


# ─────────────── Router ───────────────


def _reset_caches() -> None:
    from claimsflow.core.config import get_settings

    get_settings.cache_clear()
    reset_provider_cache()


def test_router_returns_ollama_by_default(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    _reset_caches()
    from claimsflow.providers.ollama_provider import OllamaProvider

    assert isinstance(get_llm_provider(), OllamaProvider)


def test_router_returns_anthropic_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    _reset_caches()
    from claimsflow.providers.anthropic_provider import AnthropicProvider

    assert isinstance(get_llm_provider(), AnthropicProvider)


def test_router_returns_openai_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _reset_caches()
    from claimsflow.providers.openai_provider import OpenAIProvider

    assert isinstance(get_llm_provider(), OpenAIProvider)


def test_router_satisfies_protocol(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    _reset_caches()
    assert isinstance(get_llm_provider(), LLMProvider)


# ─────────────── Token usage helpers ───────────────


def test_token_usage_total() -> None:
    u = TokenUsage(input_tokens=100, output_tokens=42)
    assert u.total == 142


# ─────────────── Opt-in integration ───────────────


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
async def test_anthropic_live_call() -> None:  # pragma: no cover
    from claimsflow.providers.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
    )
    response = await provider.reason(
        system_prompt="You are a medical claims reviewer.",
        user_prompt="Is procedure 99213 appropriate for diagnosis E11.9?",
        response_schema=Verdict,
    )
    assert response.data.confidence >= 0
    assert response.usage.input_tokens > 0
