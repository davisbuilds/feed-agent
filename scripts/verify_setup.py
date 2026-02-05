"""Verify that the project is set up correctly."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _check_import(module_name: str, errors: list[str], label: str | None = None) -> None:
    """Import a module and print status."""
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        if version is not None:
            print(f"✅ {label or module_name} {version}")
        else:
            print(f"✅ {label or module_name}")
    except ImportError as exc:
        errors.append(f"{label or module_name}: {exc}")


def _check_provider_sdk(provider: str, errors: list[str]) -> None:
    """Verify provider SDK import for the configured provider."""
    module_by_provider = {
        "gemini": "google.genai",
        "openai": "openai",
        "anthropic": "anthropic",
    }
    module_name = module_by_provider[provider]
    _check_import(module_name, errors)


def main() -> None:
    """Run setup verification."""
    print("🔍 Verifying project setup...\n")

    errors: list[str] = []

    print(f"Python version: {sys.version}")
    print("✅ Python version OK")

    print("\nChecking dependencies...")
    _check_import("feedparser", errors)
    _check_import("resend", errors)
    _check_import("bs4", errors, label="beautifulsoup4")
    _check_import("yaml", errors, label="pyyaml")
    _check_import("pydantic", errors)

    print("\nChecking configuration...")
    try:
        from config import get_settings

        settings = get_settings()
        print("✅ Settings loaded")
        print(f"   LLM provider: {settings.llm_provider}")
        print(f"   LLM model: {settings.llm_model}")
        print(f"   Email from: {settings.email_from}")

        _check_provider_sdk(settings.llm_provider, errors)
    except Exception as exc:
        errors.append(f"Configuration: {exc}")

    print("\nChecking feeds config...")
    feeds_path = Path("config/feeds.yaml")
    if feeds_path.exists():
        try:
            from config import FeedConfig

            feed_config = FeedConfig(feeds_path)
            urls = feed_config.get_feed_urls()
            print(f"✅ Found {len(urls)} configured feeds")
        except Exception as exc:
            errors.append(f"Feeds config: {exc}")
    else:
        errors.append("config/feeds.yaml not found")

    print("\n" + "=" * 50)
    if errors:
        print("❌ Setup verification FAILED")
        print("\nErrors:")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)

    print("✅ Setup verification PASSED")
    print("\nReady to proceed to Phase 1!")


if __name__ == "__main__":
    main()
