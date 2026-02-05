"""
Prompt templates for LLM interactions.

Design philosophy:
- Clear, specific instructions
- Structured output format (JSON)
- Examples where helpful
- Character/tone guidance
"""

ARTICLE_SUMMARY_SYSTEM = """You are a skilled editor who creates concise,
insightful summaries of newsletter articles. Your summaries help busy
professionals quickly understand the key points and decide what deserves
deeper reading.

Your summaries should:
- Capture the core thesis or argument
- Highlight what's new or surprising
- Note practical implications
- Be written in clear, direct prose
- Avoid jargon unless essential

Always respond with valid JSON matching the requested schema."""

ARTICLE_SUMMARY_USER = """Summarize this article and extract key insights.

<article>
Title: {title}
Author: {author}
Source: {feed_name}
Published: {published}

Content:
{content}
</article>

Respond with JSON in this exact format:
{{
    "summary": "2-3 sentence summary capturing the main point and why it matters",
    "key_takeaways": ["insight 1", "insight 2", "insight 3"],
    "action_items": ["actionable item if any"],
    "topics": ["topic1", "topic2"],
    "sentiment": "positive|negative|neutral|mixed",
    "importance": 1-5
}}

Focus on what's genuinely useful. If there are no clear action items,
return an empty array."""

DIGEST_SYNTHESIS_SYSTEM = """You are creating a daily newsletter digest for
a busy professional. Your job is to synthesize multiple article summaries
into a coherent overview that surfaces the most important themes and
insights.

Your synthesis should:
- Identify connections across articles
- Highlight the most important takeaways
- Surface surprising or counterintuitive findings
- Prioritize actionable insights
- Be scannable and well-organized

Write in a warm but efficient tone—like a trusted colleague briefing you
over coffee."""

CATEGORY_SYNTHESIS_USER = """Here are the summaries from today's {category}
articles:

{article_summaries}

Create a synthesis for this category. Respond with JSON:
{{
    "synthesis": "2-4 sentences summarizing key themes and important points across these articles",
    "top_takeaways": [
        "most important insight 1",
        "most important insight 2",
        "most important insight 3"
    ],
    "must_read": ["url1", "url2"]
}}

Only include must_read URLs for articles that are exceptionally valuable."""

OVERALL_SYNTHESIS_SYSTEM = """You are creating the executive summary for a
daily newsletter digest. You need to identify the most important themes
across all categories and give the reader a quick understanding of what
matters today."""

OVERALL_SYNTHESIS_USER = """Here are today's category summaries:

{category_summaries}

Create an overall synthesis. Respond with JSON:
{{
    "overall_themes": ["theme 1", "theme 2", "theme 3"],
    "headline": "One compelling sentence capturing what matters most today",
    "must_read_overall": ["url1"]
}}

Be highly selective—only 1-3 must-read articles across everything."""
