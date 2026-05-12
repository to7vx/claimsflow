"""Smoke tests for Module 1 — proves the package imports and settings load."""

from __future__ import annotations

from claimsflow import __version__
from claimsflow.core import get_settings


def test_version_is_set() -> None:
    assert __version__ == "0.1.0"


def test_settings_load_with_defaults(monkeypatch) -> None:
    # Clear the lru_cache so env mutations are visible.
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    s = get_settings()
    assert s.llm_provider == "ollama"
    assert s.database_url == "sqlite:///./test.db"
    assert s.api_port == 8000
    assert "http://localhost:5173" in s.cors_origin_list


def test_cli_hello_command() -> None:
    from click.testing import CliRunner

    from claimsflow.cli.main import cli

    result = CliRunner().invoke(cli, ["hello"])
    assert result.exit_code == 0
    assert "scaffold OK" in result.output
