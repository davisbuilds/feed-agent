"""Test the analysis pipeline with real articles."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyze import run_analysis
from src.config import get_settings
from src.logging_config import setup_logging
from src.storage.db import Database


def main() -> None:
    """Run a test analysis."""
    setup_logging("INFO")
    settings = get_settings()
    
    print("=" * 60)
    print("Testing Analysis Pipeline")
    print("=" * 60)
    
    # Use the same database as ingestion
    db_path = settings.data_dir / "test_articles.db"
    
    if not db_path.exists():
        print(f"\n❌ Database not found: {db_path}")
        print("Run test_ingest.py first to populate the database.")
        return
    
    db = Database(db_path)
    
    # Check for pending articles
    pending = db.get_pending_articles()
    print(f"\nFound {len(pending)} pending articles")
    
    if not pending:
        print("No pending articles. Run scripts/test_ingest.py first to fetch new articles.")
        return
    
    print("\nArticles to analyze:")
    for article in pending[:5]:
        print(f"  • {article.title[:50]}...")
    if len(pending) > 5:
        print(f"  ... and {len(pending) - 5} more")
    
    print("\n" + "-" * 60)
    print("Starting analysis (this uses the configured LLM API)...")
    print("-" * 60 + "\n")
    
    result = run_analysis(db=db)
    
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Articles analyzed: {result.articles_analyzed}")
    print(f"Tokens used:       {result.tokens_used:,}")
    print(f"Estimated cost:    ${result.cost_estimate_usd:.4f}")
    print(f"Duration:          {result.duration_seconds:.2f}s")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  ✗ {error}")
    
    if result.digest:
        print("\n" + "-" * 60)
        print("Digest Preview")
        print("-" * 60)
        
        print(f"\n📅 {result.digest.date.strftime('%B %d, %Y')}")
        print(f"📊 {result.digest.total_articles} articles from {result.digest.total_feeds} feeds")
        
        if result.digest.overall_themes:
            print("\n🎯 Overall Themes:")
            for theme in result.digest.overall_themes:
                print(f"   • {theme}")
        
        for cat in result.digest.categories:
            print(f"\n📁 {cat.name} ({cat.article_count} articles)")
            print(f"   {cat.synthesis}")
            
            if cat.top_takeaways:
                print("\n   Key takeaways:")
                for takeaway in cat.top_takeaways[:3]:
                    print(f"   • {takeaway}")
            
            print("\n   Articles:")
            for article in cat.articles[:3]:
                print(f"   • {article.title[:40]}...")
                if article.summary:
                    print(f"     {article.summary[:100]}...")


if __name__ == "__main__":
    main()
