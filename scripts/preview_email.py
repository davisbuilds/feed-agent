"""Preview email template in browser without sending."""

import sys
import webbrowser
from pathlib import Path
from tempfile import NamedTemporaryFile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from src.deliver import EmailRenderer
from src.models import Article, CategoryDigest, DailyDigest


def create_sample_digest() -> DailyDigest:
    """Create a sample digest with realistic data."""
    articles = [
        Article(
            id="1",
            url="https://stratechery.com/2024/example",
            title="The Future of AI in Content Creation: A Deep Dive",
            author="Ben Thompson",
            feed_name="Stratechery",
            feed_url="https://stratechery.com/feed",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=2500,
            category="Tech Strategy",
            summary="AI is revolutionizing content creation, enabling personalized experiences at scale while raising fundamental questions about authenticity, creative ownership, and the economics of digital media.",
            key_takeaways=[
                "AI tools can now generate human-quality content in seconds",
                "Authenticity verification becoming crucial for maintaining trust",
                "Creative professionals shifting to curation and editing roles",
            ],
            action_items=["Audit your content workflow for AI augmentation opportunities"],
        ),
        Article(
            id="2",
            url="https://simonwillison.net/2024/example",
            title="Building with LLMs: Lessons from the Trenches",
            author="Simon Willison",
            feed_name="Simon Willison's Blog",
            feed_url="https://simonwillison.net/atom/everything/",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=1800,
            category="AI & Development",
            summary="Practical insights from building production applications with modern LLMs, including prompt engineering patterns, error handling strategies, and cost optimization techniques.",
            key_takeaways=[
                "Structured output dramatically improves reliability",
                "Temperature 0 for deterministic tasks, 0.7 for creative",
                "Caching can reduce costs by 60-80%",
            ],
            action_items=["Implement response caching for repeated queries"],
        ),
        Article(
            id="3",
            url="https://example.com/article3",
            title="Remote Work: Three Years Later - What the Data Shows",
            author="Bob Johnson",
            feed_name="Workplace Weekly",
            feed_url="https://workplace.substack.com/feed",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=1200,
            category="Business",
            summary="Comprehensive analysis of remote work trends reveals hybrid arrangements as the dominant model, with surprising insights about productivity and culture.",
            key_takeaways=[
                "Productivity remains stable in hybrid arrangements",
                "Company culture requires intentional, scheduled effort",
                "Junior employees show strongest preference for office time",
            ],
            action_items=[],
        ),
    ]
    
    categories = [
        CategoryDigest(
            name="Tech Strategy",
            article_count=1,
            articles=[articles[0]],
            synthesis="Today's strategic analysis examines how AI is fundamentally reshaping content economics and creative workflows.",
            top_takeaways=[
                "AI content generation has reached quality parity with human writers for many use cases",
                "The competitive moat is shifting from creation to curation and distribution",
            ],
        ),
        CategoryDigest(
            name="AI & Development",
            article_count=1,
            articles=[articles[1]],
            synthesis="Practical engineering insights for working with large language models in production environments.",
            top_takeaways=[
                "Structured output patterns significantly improve application reliability",
                "Cost optimization remains a key consideration for scaling AI applications",
            ],
        ),
        CategoryDigest(
            name="Business",
            article_count=1,
            articles=[articles[2]],
            synthesis="Workplace trends continue to evolve as organizations find stable patterns three years into the remote work era.",
            top_takeaways=[
                "Hybrid work has emerged as the sustainable middle ground",
                "Intentional culture-building is non-negotiable for distributed teams",
            ],
        ),
    ]
    
    return DailyDigest(
        id="preview-001",
        date=datetime.now(timezone.utc),
        categories=categories,
        total_articles=3,
        total_feeds=3,
        processing_time_seconds=4.2,
        overall_themes=[
            "AI transforming knowledge work at every level",
            "Organizational adaptation to distributed models",
            "Quality and authenticity as differentiators",
        ],
        must_read=["https://stratechery.com/2024/example"],
    )


def main() -> None:
    """Preview email in browser."""
    print("Generating email preview...")
    
    renderer = EmailRenderer()
    digest = create_sample_digest()
    
    subject = f"📬 Your Daily Digest - {digest.date.strftime('%B %d, %Y')}"
    html, text = renderer.render(digest, subject)
    
    # Write to temp file and open
    with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html)
        filepath = f.name
    
    print(f"Opening preview: {filepath}")
    webbrowser.open(f"file://{filepath}")
    
    print("\nPlain text version:")
    print("-" * 60)
    print(text)


if __name__ == "__main__":
    main()
