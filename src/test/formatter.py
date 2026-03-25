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
    for a in articles[:7]:  # scan top 7 for broader coverage
        title_lower = a["title"].lower()
        # Priority order matters — most specific first
        if any(x in title_lower for x in ["openai", "chatgpt", "gpt-4", "gpt-5", "o1", "o3"]):
            topics.append("OpenAI and GPT models")
        elif any(x in title_lower for x in ["google ai", "google deepmind", "deepmind", "gemini", "waymo"]):
            topics.append("Google AI")
        elif any(x in title_lower for x in ["anthropic", "claude"]):
            topics.append("Anthropic and Claude")
        elif any(x in title_lower for x in ["meta ai", "meta's", "llama", " Facebook ai"]):
            topics.append("Meta AI")
        elif any(x in title_lower for x in ["microsoft ai", "copilot", "azure ai", "bing ai"]):
            topics.append("Microsoft AI")
        elif any(x in title_lower for x in ["ai safety", "ai policy", "ai regulation", "ai law", "ai act", "ai safety bill", "government ai", "congress ai", "eu ai"]):
            topics.append("AI policy and safety")
        elif any(x in title_lower for x in ["ai research", "ai study", "breakthrough", "discovery", "paper", "university ai"]):
            topics.append("AI research")
        elif any(x in title_lower for x in ["robotics", "autonomous", "humanoid", "robot", "drone"]):
            topics.append("Robotics and autonomy")
        elif any(x in title_lower for x in ["ai chip", "gpu", "nvidia", "tpu", "hardware", "neuromorphic"]):
            topics.append("AI hardware")
        elif any(x in title_lower for x in ["stable diffusion", "midjourney", "dall-e", "image generation", "video generation", "sora", "video ai"]):
            topics.append("Generative media")
        elif any(x in title_lower for x in ["model", "llm", "multimodal", "reasoning", "benchmark"]) and \
             any(x in title_lower for x in ["new", "launch", "release", "announce", "unveils"]):
            topics.append("New AI models")
        elif any(x in title_lower for x in ["startup", "raises", "secures", "funding", "series a", "series b", "a16z", "vc"]):
            topics.append("AI startups and funding")
        elif any(x in title_lower for x in ["agent", "agentic", "agent ai", "autonomous ai"]):
            topics.append("AI agents")
        elif any(x in title_lower for x in ["ai ethics", "bias", "fairness", "transparency", "explainability"]):
            topics.append("AI ethics and governance")

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