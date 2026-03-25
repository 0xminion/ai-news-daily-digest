"""Formatter for AI News Digest output."""

from __future__ import annotations

from datetime import datetime
from typing import List


def format_digest(articles: List[dict], top_n: int = 10, highlights_n: int = 5) -> str:
    """Format a news digest for Telegram delivery.

    Args:
        articles: List of article dicts with title, summary, link, source, published
        top_n: How many articles to include in the digest (default 10)
        highlights_n: How many bullet highlights (default 5)

    Returns:
        Formatted Telegram message string.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    header = f"🤖 AI News Briefing — {date_str}\n"
    header += "=" * 40 + "\n\n"

    # Use top articles sorted by recency
    sorted_articles = sorted(articles, key=lambda a: a["published"], reverse=True)[:top_n]

    # Brief rundown — 2-3 sentence summary of the day's theme
    rundown = _generate_rundown(sorted_articles)

    # 5 must-know highlights
    highlights = _generate_highlights(sorted_articles[:highlights_n])

    footer = "\n— Your daily AI briefing. More at @YourChannel"

    return header + rundown + "\n\n" + highlights + footer


def _generate_rundown(articles: list[dict]) -> str:
    """Generate a 2-3 sentence brief rundown of the day's AI news theme."""
    if not articles:
        return "No significant AI news found in the past 24 hours."

    sources = [a["source"] for a in articles]
    unique_sources = list(dict.fromkeys(sources))  # preserve order, remove dups
    source_list = ", ".join(unique_sources[:5])

    topics = []
    for a in articles[:5]:
        title_lower = a["title"].lower()
        if "openai" in title_lower or "chatgpt" in title_lower:
            topics.append("OpenAI and GPT models")
        elif "google" in title_lower or "gemini" in title_lower:
            topics.append("Google AI developments")
        elif "anthropic" in title_lower or "claude" in title_lower:
            topics.append("Anthropic and Claude")
        elif "regulation" in title_lower or "government" in title_lower or "eu" in title_lower:
            topics.append("AI policy and regulation")
        elif "research" in title_lower or "study" in title_lower:
            topics.append("AI research breakthroughs")
        elif "startup" in title_lower or "funding" in title_lower:
            topics.append("AI startup funding")
        elif "robotics" in title_lower or "autonomous" in title_lower:
            topics.append("Robotics and autonomous systems")

    unique_topics = list(dict.fromkeys(topics))[:3]
    topic_str = ", ".join(unique_topics) if unique_topics else "major AI developments"

    rundown = (
        f"Today saw AI in focus across {source_list} and other outlets. "
        f"Key themes included {topic_str}. "
        f"Here's what matters most:"
    )
    return rundown


def _generate_highlights(articles: list[dict]) -> str:
    """Generate numbered highlight bullets with source links."""
    if not articles:
        return "No articles to highlight."
    lines = ["📌 5 Must-Know Highlights:\n"]
    for i, article in enumerate(articles, 1):
        title = article["title"]
        link = article["link"]
        source = article["source"]
        # Escape any Markdown special chars in title for Telegram
        title_escaped = title.replace("*", " ").replace("_", " ").replace("[", "(").replace("]", ")")
        lines.append(f"{i}. {title_escaped}\n   Source: {source} | [Read more]({link})\n")
    return "\n".join(lines)