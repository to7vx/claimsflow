"""Provider selection — single entry point for `get_llm_provider()`.

The pipeline never instantiates providers directly. It calls this function,
which reads settings, picks the right provider, and caches the instance.
This means a test can override `LLM_PROVIDER=ollama` in env and the
pipeline transparently switches.
"""

from __future__ import annotations

from functools import lru_cache

from claimsflow.core.config import get_settings
from claimsflow.providers.base import LLMProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        from claimsflow.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
    if settings.llm_provider == "openai":
        from claimsflow.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    if settings.llm_provider == "ollama":
        from claimsflow.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    raise ValueError(f"unknown LLM_PROVIDER: {settings.llm_provider!r}")


def reset_provider_cache() -> None:
    """Drop the cached provider — call this after mutating env in tests."""
    get_llm_provider.cache_clear()
