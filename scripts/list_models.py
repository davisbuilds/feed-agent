"""List available models for the configured LLM provider."""

from src.config import get_settings


def main() -> int:
    """List models for provider if supported."""
    settings = get_settings()

    if settings.llm_provider != "gemini":
        print(
            "Model listing is currently implemented only for gemini; "
            f"current provider is {settings.llm_provider}."
        )
        return 1

    try:
        from google import genai
    except ImportError as exc:
        print(
            "Gemini model listing requires the gemini dependency. "
            "Install it with: uv sync --extra gemini"
        )
        print(f"Import error: {exc}")
        return 1

    client = genai.Client(api_key=settings.llm_api_key)
    print("Available models:")
    for model in client.models.list():
        if "generateContent" in model.supported_generation_methods:
            print(f"- {model.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
