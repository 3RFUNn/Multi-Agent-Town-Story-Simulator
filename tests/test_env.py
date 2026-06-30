"""Tests for the stdlib .env loader + API-key resolution."""

import os

import pytest

from matss.config import find_dotenv, load_dotenv, parse_dotenv, resolve_api_key
from matss.cognition.llm import OpenRouterProvider, OpenAIProvider


def test_parse_dotenv_handles_comments_quotes_export():
    text = (
        "# a comment\n"
        "\n"
        "export OPENROUTER_API_KEY=sk-or-v1-abc\n"
        'API_KEY="quoted-value"\n'
        "OTHER='single'\n"
        "NOEQ line without equals\n"
    )
    parsed = parse_dotenv(text)
    assert parsed["OPENROUTER_API_KEY"] == "sk-or-v1-abc"
    assert parsed["API_KEY"] == "quoted-value"
    assert parsed["OTHER"] == "single"
    assert "NOEQ" not in parsed


def test_load_dotenv_sets_env_without_override(tmp_path, monkeypatch):
    # load_dotenv writes os.environ directly (not via monkeypatch), so register
    # cleanup to keep the write from leaking into other tests.
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    import matss.config.env as envmod
    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=from-file\nOPENROUTER_API_KEY=sk-or-v1-xyz\n")
    try:
        load_dotenv(str(env_file), override=True)
        assert os.environ["API_KEY"] == "from-file"
        assert os.environ["OPENROUTER_API_KEY"] == "sk-or-v1-xyz"

        # Existing env var is NOT overridden by default.
        monkeypatch.setenv("API_KEY", "already-set")
        load_dotenv(str(env_file), override=False)
        assert os.environ["API_KEY"] == "already-set"
    finally:
        os.environ.pop("API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        envmod._LOADED.discard(str(env_file))


def test_resolve_api_key_precedence(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    # explicit wins
    assert resolve_api_key("explicit", ["OPENROUTER_API_KEY", "API_KEY"], load=False) == "explicit"
    # specific var beats generic
    monkeypatch.setenv("API_KEY", "generic")
    monkeypatch.setenv("OPENROUTER_API_KEY", "specific")
    assert resolve_api_key(None, ["OPENROUTER_API_KEY", "API_KEY"], load=False) == "specific"
    # falls back to generic API_KEY
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert resolve_api_key(None, ["OPENROUTER_API_KEY", "API_KEY"], load=False) == "generic"
    # none set -> None
    monkeypatch.delenv("API_KEY", raising=False)
    assert resolve_api_key(None, ["OPENROUTER_API_KEY", "API_KEY"], load=False) is None


def test_provider_reads_generic_api_key_from_env(monkeypatch):
    # A single generic API_KEY satisfies whichever provider is selected.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "sk-shared-123")
    assert OpenRouterProvider().api_key == "sk-shared-123"
    assert OpenAIProvider().api_key == "sk-shared-123"


def test_provider_prefers_specific_over_generic(monkeypatch):
    monkeypatch.setenv("API_KEY", "generic")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-specific")
    assert OpenRouterProvider().api_key == "sk-or-v1-specific"


def test_find_dotenv_stops_at_project_root():
    # Discovery returns a path string or None; must not raise from the repo tree.
    result = find_dotenv()
    assert result is None or result.endswith(".env")
