"""Typed settings loaded from environment / .env.

All configuration the app needs lives here. Anything else reads from this
singleton via `get_settings()`. Never read os.environ directly elsewhere.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


LLMProviderName = Literal["ollama", "anthropic", "openai"]


class Settings(BaseSettings):
    """Application settings. Populated from environment + .env (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"
    api_key: str = "dev-local-key-change-me"
    webhook_hmac_secret: str = "dev-hmac-secret-change-me"

    # --- DB ---
    database_url: str = "sqlite:///./claimsflow.db"

    # --- LLM ---
    llm_provider: LLMProviderName = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Optional override — e.g. Gemini's OpenAI-compatible endpoint.
    # Leave blank for the real OpenAI API.
    openai_base_url: str = ""

    # --- Pipeline ---
    auto_approve_amount_ceiling_sar: float = Field(default=50_000.0)
    medical_necessity_cache_ttl: int = 86_400
    api_rate_limit_per_minute: int = 120

    # --- Demo controls ---
    # When true, exposes /api/v1/demo/run and /api/v1/demo/reset so the
    # dashboard's "Run Demo" / "Clear Demo Data" buttons work. Set to false
    # in any real deployment.
    demo_mode: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Call this everywhere; never instantiate Settings directly."""
    return Settings()
