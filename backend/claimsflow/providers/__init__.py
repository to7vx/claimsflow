"""LLM provider abstraction.

Public API:
- `LLMProvider` — the Protocol every backend implements
- `LLMResponse`, `TokenUsage` — what `reason()` returns
- `get_llm_provider()` — settings-driven provider selection
"""

from claimsflow.providers.base import (
    LLMProvider,
    LLMResponse,
    LLMResponseParseError,
    TokenUsage,
    parse_structured_response,
)
from claimsflow.providers.router import get_llm_provider, reset_provider_cache

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMResponseParseError",
    "TokenUsage",
    "parse_structured_response",
    "get_llm_provider",
    "reset_provider_cache",
]
