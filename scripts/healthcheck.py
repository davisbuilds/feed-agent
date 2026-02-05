"""Simple healthcheck script for local/cron monitoring."""

import sys
from datetime import datetime

from src.config import get_settings
from src.storage.db import Database


def main() -> int:
    """Run healthcheck and return exit code."""
    settings = get_settings()

    issues: list[str] = []

    db_path = settings.data_dir / "articles.db"
    if not db_path.exists():
        issues.append("Database not found")
    else:
        db = Database(db_path)
        with db._connection() as conn:
            last_article = conn.execute(
                """
                SELECT MAX(created_at) FROM articles
                """
            ).fetchone()[0]

            if last_article:
                last_time = datetime.fromisoformat(last_article)
                age_hours = (datetime.now() - last_time).total_seconds() / 3600
                if age_hours > 48:
                    issues.append(f"No new articles in {age_hours:.0f} hours")
            else:
                issues.append("No articles in database")

    if not settings.llm_api_key:
        issues.append("Missing LLM API key")

    if not settings.resend_api_key:
        issues.append("Missing Resend API key")

    if issues:
        print("UNHEALTHY")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("HEALTHY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
