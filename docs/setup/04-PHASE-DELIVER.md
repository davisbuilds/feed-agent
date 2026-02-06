# Phase 3: Email Delivery

**Goal**: Create a beautiful, responsive email digest using Resend and thoughtfully designed templates. The email is the product—make it something worth opening.

**Estimated Time**: 3-4 hours

**Dependencies**: Phase 2 completed (analysis working)

---

## Overview

The delivery layer transforms the DailyDigest into a beautifully formatted email. This is what users actually see, so design matters enormously.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Delivery Pipeline                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐         │
│  │    Digest    │────▶│   Render     │────▶│    Send      │         │
│  │   (model)    │     │  (Jinja2)    │     │   (Resend)   │         │
│  └──────────────┘     └──────────────┘     └──────────────┘         │
│                              │                                       │
│                              ▼                                       │
│                       ┌──────────────┐                              │
│                       │    HTML      │                              │
│                       │   + Text     │                              │
│                       └──────────────┘                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Mobile First**: 70%+ of emails are read on mobile
2. **Scannable**: Headers, whitespace, visual hierarchy
3. **Fast Loading**: No images, minimal CSS
4. **Accessible**: Plain text fallback, semantic structure
5. **Beautiful**: Typography and spacing that feels premium

---

## Tasks

### 3.1 Email Templates Directory

Create the templates structure:

```bash
mkdir -p src/deliver/templates
touch src/deliver/templates/base.html
touch src/deliver/templates/digest.html
touch src/deliver/templates/digest.txt
```

- [ ] Create template directories

### 3.2 Base HTML Template

Create `src/deliver/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{{ subject }}</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {font-family: Arial, Helvetica, sans-serif !important;}
    </style>
    <![endif]-->
    <style type="text/css">
        /* Reset */
        body, table, td, p, a, li { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
        table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
        img { -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }
        
        /* Base */
        body {
            margin: 0 !important;
            padding: 0 !important;
            background-color: #f4f4f5;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        
        /* Container */
        .email-container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        /* Typography */
        h1 { font-size: 28px; line-height: 1.3; font-weight: 700; margin: 0 0 16px 0; color: #18181b; }
        h2 { font-size: 20px; line-height: 1.4; font-weight: 600; margin: 32px 0 12px 0; color: #18181b; }
        h3 { font-size: 16px; line-height: 1.5; font-weight: 600; margin: 24px 0 8px 0; color: #3f3f46; }
        p { font-size: 16px; line-height: 1.6; margin: 0 0 16px 0; color: #3f3f46; }
        a { color: #2563eb; text-decoration: none; }
        a:hover { text-decoration: underline; }
        
        /* Components */
        .header {
            background-color: #18181b;
            padding: 32px 24px;
            text-align: center;
        }
        .header h1 { color: #ffffff; font-size: 24px; margin: 0; }
        .header .date { color: #a1a1aa; font-size: 14px; margin-top: 8px; }
        
        .content {
            background-color: #ffffff;
            padding: 32px 24px;
        }
        
        .summary-box {
            background-color: #f4f4f5;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .summary-box p { margin-bottom: 0; }
        
        .category {
            border-top: 1px solid #e4e4e7;
            padding-top: 24px;
            margin-top: 24px;
        }
        .category:first-child {
            border-top: none;
            padding-top: 0;
            margin-top: 0;
        }
        
        .category-header {
            display: flex;
            align-items: center;
            margin-bottom: 16px;
        }
        .category-badge {
            background-color: #e4e4e7;
            color: #3f3f46;
            font-size: 12px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .article {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #f4f4f5;
        }
        .article:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        .article-title {
            font-size: 16px;
            font-weight: 600;
            color: #18181b;
            margin-bottom: 4px;
        }
        .article-meta {
            font-size: 13px;
            color: #71717a;
            margin-bottom: 8px;
        }
        .article-summary {
            font-size: 15px;
            color: #3f3f46;
            margin-bottom: 8px;
        }
        .article-takeaways {
            font-size: 14px;
            color: #52525b;
            padding-left: 16px;
            margin: 8px 0 0 0;
        }
        .article-takeaways li {
            margin-bottom: 4px;
        }
        
        .read-link {
            font-size: 14px;
            font-weight: 500;
            color: #2563eb;
        }
        
        .footer {
            background-color: #f4f4f5;
            padding: 24px;
            text-align: center;
        }
        .footer p {
            font-size: 13px;
            color: #71717a;
            margin: 0;
        }
        
        /* Responsive */
        @media screen and (max-width: 600px) {
            .email-container { width: 100% !important; }
            .content { padding: 24px 16px !important; }
            h1 { font-size: 24px !important; }
            h2 { font-size: 18px !important; }
        }
    </style>
</head>
<body>
    <center>
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f4f4f5;">
            <tr>
                <td style="padding: 20px 0;">
                    {% block content %}{% endblock %}
                </td>
            </tr>
        </table>
    </center>
</body>
</html>
```

- [ ] Create `base.html` template

### 3.3 Digest HTML Template

Create `src/deliver/templates/digest.html`:

```html
{% extends "base.html" %}

{% block content %}
<table class="email-container" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="margin: 0 auto;">
    <!-- Header -->
    <tr>
        <td class="header">
            <h1>📬 Your Daily Digest</h1>
            <div class="date">{{ digest.date.strftime('%A, %B %d, %Y') }}</div>
        </td>
    </tr>
    
    <!-- Content -->
    <tr>
        <td class="content">
            <!-- Stats -->
            <p style="font-size: 14px; color: #71717a; text-align: center; margin-bottom: 24px;">
                {{ digest.total_articles }} articles from {{ digest.total_feeds }} sources
            </p>
            
            <!-- Overall Themes -->
            {% if digest.overall_themes %}
            <div class="summary-box">
                <h3 style="margin-top: 0; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: #71717a;">Today's Themes</h3>
                <p style="font-size: 16px; color: #18181b;">
                    {% for theme in digest.overall_themes %}
                    {{ theme }}{% if not loop.last %} • {% endif %}
                    {% endfor %}
                </p>
            </div>
            {% endif %}
            
            <!-- Categories -->
            {% for category in digest.categories %}
            <div class="category">
                <div class="category-header">
                    <span class="category-badge">{{ category.name }}</span>
                    <span style="margin-left: 8px; font-size: 13px; color: #71717a;">{{ category.article_count }} article{% if category.article_count != 1 %}s{% endif %}</span>
                </div>
                
                <!-- Category Synthesis -->
                {% if category.synthesis %}
                <p style="font-size: 15px; color: #52525b; margin-bottom: 20px; font-style: italic;">
                    {{ category.synthesis }}
                </p>
                {% endif %}
                
                <!-- Key Takeaways -->
                {% if category.top_takeaways %}
                <div style="background-color: #fefce8; border-left: 3px solid #eab308; padding: 12px 16px; margin-bottom: 20px; border-radius: 0 4px 4px 0;">
                    <p style="font-size: 12px; font-weight: 600; color: #854d0e; text-transform: uppercase; margin-bottom: 8px;">Key Takeaways</p>
                    <ul style="margin: 0; padding-left: 16px;">
                        {% for takeaway in category.top_takeaways[:3] %}
                        <li style="font-size: 14px; color: #713f12; margin-bottom: 4px;">{{ takeaway }}</li>
                        {% endfor %}
                    </ul>
                </div>
                {% endif %}
                
                <!-- Articles -->
                {% for article in category.articles %}
                <div class="article">
                    <div class="article-title">
                        <a href="{{ article.url }}" style="color: #18181b;">{{ article.title }}</a>
                    </div>
                    <div class="article-meta">
                        {{ article.author }} · {{ article.feed_name }} · {{ article.published.strftime('%b %d') }}
                    </div>
                    {% if article.summary %}
                    <div class="article-summary">
                        {{ article.summary }}
                    </div>
                    {% endif %}
                    {% if article.key_takeaways %}
                    <ul class="article-takeaways">
                        {% for takeaway in article.key_takeaways[:2] %}
                        <li>{{ takeaway }}</li>
                        {% endfor %}
                    </ul>
                    {% endif %}
                    <a href="{{ article.url }}" class="read-link">Read article →</a>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </td>
    </tr>
    
    <!-- Footer -->
    <tr>
        <td class="footer">
            <p>
                Generated in {{ "%.1f"|format(digest.processing_time_seconds) }}s
                <br>
                <span style="color: #a1a1aa;">Powered by Claude + Feed Agent</span>
            </p>
        </td>
    </tr>
</table>
{% endblock %}
```

- [ ] Create `digest.html` template

### 3.4 Plain Text Template

Create `src/deliver/templates/digest.txt`:

```
YOUR DAILY DIGEST
{{ digest.date.strftime('%A, %B %d, %Y') }}
{{ '=' * 50 }}

{{ digest.total_articles }} articles from {{ digest.total_feeds }} sources

{% if digest.overall_themes %}
TODAY'S THEMES
{% for theme in digest.overall_themes %}• {{ theme }}
{% endfor %}
{% endif %}

{% for category in digest.categories %}
{{ '-' * 50 }}
{{ category.name|upper }} ({{ category.article_count }} article{% if category.article_count != 1 %}s{% endif %})
{{ '-' * 50 }}

{% if category.synthesis %}
{{ category.synthesis }}

{% endif %}
{% if category.top_takeaways %}
KEY TAKEAWAYS:
{% for takeaway in category.top_takeaways[:3] %}• {{ takeaway }}
{% endfor %}

{% endif %}
{% for article in category.articles %}
▸ {{ article.title }}
  {{ article.author }} · {{ article.feed_name }}
{% if article.summary %}
  {{ article.summary }}
{% endif %}
  {{ article.url }}

{% endfor %}
{% endfor %}
{{ '=' * 50 }}
Generated in {{ "%.1f"|format(digest.processing_time_seconds) }}s
Powered by Claude + Feed Agent
```

- [ ] Create `digest.txt` template

### 3.5 Email Renderer

Create `src/deliver/renderer.py`:

```python
"""
Email template rendering using Jinja2.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.logging_config import get_logger
from src.models import DailyDigest

logger = get_logger("renderer")

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


class EmailRenderer:
    """Renders digest to HTML and plain text email formats."""
    
    def __init__(self, template_dir: Path | None = None):
        self.template_dir = template_dir or TEMPLATE_DIR
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def render_html(self, digest: DailyDigest, subject: str) -> str:
        """
        Render digest to HTML email.
        
        Args:
            digest: DailyDigest to render
            subject: Email subject line
        
        Returns:
            Rendered HTML string
        """
        template = self.env.get_template("digest.html")
        return template.render(digest=digest, subject=subject)
    
    def render_text(self, digest: DailyDigest) -> str:
        """
        Render digest to plain text email.
        
        Args:
            digest: DailyDigest to render
        
        Returns:
            Rendered plain text string
        """
        template = self.env.get_template("digest.txt")
        return template.render(digest=digest)
    
    def render(self, digest: DailyDigest, subject: str | None = None) -> tuple[str, str]:
        """
        Render digest to both HTML and plain text.
        
        Args:
            digest: DailyDigest to render
            subject: Optional subject line
        
        Returns:
            Tuple of (html, text)
        """
        if subject is None:
            subject = f"📬 Your Daily Digest - {digest.date.strftime('%B %d, %Y')}"
        
        html = self.render_html(digest, subject)
        text = self.render_text(digest)
        
        logger.debug(f"Rendered email: {len(html)} chars HTML, {len(text)} chars text")
        
        return html, text
```

- [ ] Create `src/deliver/renderer.py`

### 3.6 Resend Integration

Create `src/deliver/email.py`:

```python
"""
Email delivery via Resend.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import resend

from src.config import get_settings
from src.logging_config import get_logger
from src.models import DailyDigest

from .renderer import EmailRenderer

logger = get_logger("email")


@dataclass
class SendResult:
    """Result of sending an email."""
    
    success: bool
    email_id: str | None
    error: str | None = None


class EmailSender:
    """Handles email delivery via Resend."""
    
    def __init__(
        self, 
        api_key: str | None = None,
        from_address: str | None = None,
        to_address: str | None = None,
    ):
        settings = get_settings()
        
        resend.api_key = api_key or settings.resend_api_key
        self.from_address = from_address or settings.email_from
        self.to_address = to_address or settings.email_to
        
        self.renderer = EmailRenderer()
    
    def send_digest(
        self, 
        digest: DailyDigest,
        subject: str | None = None,
        to: str | None = None,
    ) -> SendResult:
        """
        Send a daily digest email.
        
        Args:
            digest: DailyDigest to send
            subject: Optional custom subject line
            to: Optional recipient override
        
        Returns:
            SendResult with success status
        """
        recipient = to or self.to_address
        
        if subject is None:
            subject = f"📬 Your Daily Digest - {digest.date.strftime('%B %d, %Y')}"
        
        logger.info(f"Sending digest to {recipient}")
        
        try:
            # Render email
            html, text = self.renderer.render(digest, subject)
            
            # Send via Resend
            response = resend.Emails.send({
                "from": self.from_address,
                "to": [recipient],
                "subject": subject,
                "html": html,
                "text": text,
                "tags": [
                    {"name": "type", "value": "daily_digest"},
                    {"name": "date", "value": digest.date.strftime("%Y-%m-%d")},
                ],
            })
            
            email_id = response.get("id") if isinstance(response, dict) else str(response)
            
            logger.info(f"Email sent successfully: {email_id}")
            
            return SendResult(
                success=True,
                email_id=email_id,
            )
            
        except resend.ResendError as e:
            logger.error(f"Resend error: {e}")
            return SendResult(
                success=False,
                email_id=None,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return SendResult(
                success=False,
                email_id=None,
                error=str(e),
            )
    
    def send_test_email(self, to: str | None = None) -> SendResult:
        """
        Send a test email to verify configuration.
        
        Args:
            to: Optional recipient override
        
        Returns:
            SendResult with success status
        """
        recipient = to or self.to_address
        
        logger.info(f"Sending test email to {recipient}")
        
        try:
            response = resend.Emails.send({
                "from": self.from_address,
                "to": [recipient],
                "subject": "🧪 Feed Agent - Test Email",
                "html": """
                    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #18181b;">Test Email</h1>
                        <p style="color: #3f3f46;">
                            If you're reading this, your Feed Agent email configuration is working correctly!
                        </p>
                        <p style="color: #71717a; font-size: 14px;">
                            Sent at: {time}
                        </p>
                    </div>
                """.format(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "text": "Test email from Feed Agent. If you're reading this, your configuration is working!",
            })
            
            email_id = response.get("id") if isinstance(response, dict) else str(response)
            
            logger.info(f"Test email sent: {email_id}")
            
            return SendResult(
                success=True,
                email_id=email_id,
            )
            
        except Exception as e:
            logger.error(f"Test email failed: {e}")
            return SendResult(
                success=False,
                email_id=None,
                error=str(e),
            )
```

- [ ] Create `src/deliver/email.py`

### 3.7 Delivery Module Init

Create `src/deliver/__init__.py`:

```python
"""
Email delivery module.

Handles rendering and sending of digest emails.
"""

from .email import EmailSender, SendResult
from .renderer import EmailRenderer

__all__ = ["EmailSender", "EmailRenderer", "SendResult", "send_digest"]


def send_digest(digest, **kwargs) -> SendResult:
    """Convenience function to send a digest."""
    sender = EmailSender()
    return sender.send_digest(digest, **kwargs)
```

- [ ] Create `src/deliver/__init__.py`

### 3.8 Test Email Delivery

Create `scripts/test_email.py`:

```python
"""Test email delivery with Resend."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from src.config import get_settings
from src.deliver import EmailSender
from src.logging_config import setup_logging
from src.models import Article, CategoryDigest, DailyDigest


def create_sample_digest() -> DailyDigest:
    """Create a sample digest for testing."""
    articles = [
        Article(
            id="1",
            url="https://example.com/article1",
            title="The Future of AI in Content Creation",
            author="Jane Smith",
            feed_name="Tech Insights",
            feed_url="https://techinsights.substack.com/feed",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=1500,
            category="Technology",
            summary="AI is revolutionizing content creation, enabling personalized experiences at scale while raising questions about authenticity and creative ownership.",
            key_takeaways=[
                "AI tools can now generate human-quality content in seconds",
                "Authenticity verification becoming crucial for trust",
                "Creative professionals shifting to curation and editing roles",
            ],
            action_items=["Explore AI writing assistants for your workflow"],
        ),
        Article(
            id="2",
            url="https://example.com/article2",
            title="Remote Work: Three Years Later",
            author="Bob Johnson",
            feed_name="Workplace Weekly",
            feed_url="https://workplace.substack.com/feed",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=1200,
            category="Business",
            summary="New data reveals hybrid work is here to stay, with most companies settling on 2-3 office days per week as the new standard.",
            key_takeaways=[
                "Productivity remains stable in hybrid arrangements",
                "Company culture requires intentional effort to maintain",
            ],
            action_items=[],
        ),
    ]
    
    categories = [
        CategoryDigest(
            name="Technology",
            article_count=1,
            articles=[articles[0]],
            synthesis="Today's tech coverage focuses on the transformative impact of AI on creative industries.",
            top_takeaways=[
                "AI content generation has reached a quality threshold that demands attention",
                "The line between human and AI-generated content is blurring",
            ],
        ),
        CategoryDigest(
            name="Business",
            article_count=1,
            articles=[articles[1]],
            synthesis="Workplace trends continue to evolve as companies find their footing in the post-pandemic era.",
            top_takeaways=[
                "Hybrid work is becoming the dominant model",
            ],
        ),
    ]
    
    return DailyDigest(
        id="test-001",
        date=datetime.now(timezone.utc),
        categories=categories,
        total_articles=2,
        total_feeds=2,
        processing_time_seconds=3.7,
        overall_themes=[
            "Technology reshaping traditional workflows",
            "Adaptability as a key professional skill",
        ],
        must_read=["https://example.com/article1"],
    )


def main() -> None:
    """Test email delivery."""
    setup_logging("INFO")
    settings = get_settings()
    
    print("=" * 60)
    print("Testing Email Delivery")
    print("=" * 60)
    
    print(f"\nConfiguration:")
    print(f"  From: {settings.email_from}")
    print(f"  To: {settings.email_to}")
    
    sender = EmailSender()
    
    # Test 1: Send test email
    print("\n" + "-" * 60)
    print("Test 1: Sending test email...")
    print("-" * 60)
    
    result = sender.send_test_email()
    
    if result.success:
        print(f"✅ Test email sent successfully")
        print(f"   Email ID: {result.email_id}")
    else:
        print(f"❌ Test email failed: {result.error}")
        return
    
    # Test 2: Send sample digest
    print("\n" + "-" * 60)
    print("Test 2: Sending sample digest...")
    print("-" * 60)
    
    digest = create_sample_digest()
    
    result = sender.send_digest(digest)
    
    if result.success:
        print(f"✅ Digest sent successfully")
        print(f"   Email ID: {result.email_id}")
    else:
        print(f"❌ Digest failed: {result.error}")
        return
    
    print("\n" + "=" * 60)
    print("All tests passed! Check your inbox.")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] Create `scripts/test_email.py`
- [ ] Run `uv run python scripts/test_email.py`
- [ ] Check your inbox for the test emails
- [ ] Verify emails render correctly on mobile (use email preview tools)

### 3.9 Preview Server (Optional)

Create `scripts/preview_email.py`:

```python
"""Preview email template in browser without sending."""

import sys
import webbrowser
from pathlib import Path
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from src.deliver import EmailRenderer
from src.models import Article, CategoryDigest, DailyDigest


def create_sample_digest() -> DailyDigest:
    """Create a sample digest with realistic data."""
    # ... (same as test_email.py)
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
            title="Building with Claude: Lessons from the Trenches",
            author="Simon Willison",
            feed_name="Simon Willison's Blog",
            feed_url="https://simonwillison.net/atom/everything/",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=1800,
            category="AI & Development",
            summary="Practical insights from building production applications with Claude, including prompt engineering patterns, error handling strategies, and cost optimization techniques.",
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
```

- [ ] Create `scripts/preview_email.py`
- [ ] Run `uv run python scripts/preview_email.py` to preview in browser

---

## Design Tips

### Email Client Compatibility

Test your emails in:
- Gmail (web and mobile)
- Apple Mail
- Outlook (notorious for rendering issues)
- Mobile email apps

Use tools like:
- [Litmus](https://www.litmus.com/) (paid)
- [Email on Acid](https://www.emailonacid.com/) (paid)
- [Mail Tester](https://www.mail-tester.com/) (free, checks deliverability)

### Deliverability

Ensure good deliverability:
1. Verify your domain in Resend
2. Set up SPF, DKIM, and DMARC records
3. Use a consistent "from" address
4. Include plain text version
5. Avoid spam trigger words

### Accessibility

- Use semantic HTML where possible
- Include alt text for any images
- Ensure sufficient color contrast
- Provide plain text fallback

---

## Completion Checklist

- [ ] Templates render correctly
- [ ] HTML email displays properly in browser preview
- [ ] Test email sends successfully
- [ ] Sample digest email looks good
- [ ] Plain text version is readable
- [ ] Mobile rendering is acceptable

## Next Phase

Once email delivery works, proceed to `05-PHASE-ORCHESTRATE.md` to tie everything together with CLI and scheduling.
