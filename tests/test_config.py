"""Tests for settings model and env aliases."""

from src import config
from src.config import Settings


def test_settings_supports_legacy_google_api_key_alias(monkeypatch) -> None:
    """GOOGLE_API_KEY should still populate llm_api_key."""
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "resend-key")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")

    settings = Settings()

    assert settings.llm_api_key == "legacy-key"
    assert settings.google_api_key == "legacy-key"


def test_settings_applies_provider_default_model(monkeypatch) -> None:
    """Provider default model should be applied when LLM_MODEL is omitted."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "resend-key")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")

    settings = Settings()

    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-4o-mini"


def test_get_settings_singleton_uses_new_fields(monkeypatch) -> None:
    """Singleton loader should return settings with llm fields configured."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "singleton-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-3-flash-preview")
    monkeypatch.setenv("RESEND_API_KEY", "resend-key")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")

    config._settings = None
    settings = config.get_settings()

    assert settings.llm_provider == "gemini"
    assert settings.llm_api_key == "singleton-key"
    assert settings.llm_model == "gemini-3-flash-preview"


def test_ignores_legacy_gemini_model_for_non_gemini_provider(monkeypatch) -> None:
    """Legacy GEMINI_MODEL should not override non-Gemini provider defaults."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    monkeypatch.setenv("RESEND_API_KEY", "resend-key")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")

    settings = Settings()

    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-4o-mini"
