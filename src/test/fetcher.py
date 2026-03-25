"""RSS feed fetcher for AI news."""

from __future__ import annotations

import feedparser
from datetime import datetime, timedelta, timezone

from test.news_sources import SOURCES

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "gpt", "openai", "anthropic", "google deepmind", "neural network",
    "chatgpt", "claude", "gemini model", "stable diffusion", "generative ai",
    "large language model", " diffusion model", " AI model", "robotics",
]

BLOCKLIST = [
    "deal", "sale", "coupon", "discount", "earnings", "revenue share",
    "stock", "crypto", "bitcoin", "ipo", "acquisition", "merger",
    "layoffs", "lawsuit", "scandal", "rumor",
]

def is_ai_related(title: str, summary: str) -> bool:
    """Require AI keyword in title, or in BOTH title AND summary (not summary alone)."""
    title_lower = title.lower()
    summary_lower = summary.lower()
    # Must have AI keyword in title
    if any(kw in title_lower for kw in AI_KEYWORDS):
        # And not be a blocked topic
        if not any(bad in title_lower for bad in BLOCKLIST):
            return True
    # Allow if AI keyword in both title AND summary
    ai_in_title = any(kw in title_lower for kw in AI_KEYWORDS)
    ai_in_summary = any(kw in summary_lower for kw in AI_KEYWORDS)
    if ai_in_title and ai_in_summary:
        if not any(bad in title_lower for bad in BLOCKLIST):
            return True
    return False


def fetch_feed(source: dict) -> list[dict]:
    """Fetch and parse a single RSS feed, return AI-related articles from past 24h."""
    feed = feedparser.parse(source["url"])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles = []

    for entry in feed.entries:
        try:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_date = datetime(*published[:6], tzinfo=timezone.utc)
            else:
                # Skip entries with no publication date
                continue

            if pub_date < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", "")

            if not is_ai_related(title, summary):
                continue

            articles.append({
                "title": title.strip(),
                "summary": summary.strip(),
                "link": link,
                "source": source["name"],
                "published": pub_date.isoformat(),
            })
        except Exception:
            continue

    return articles


def fetch_all_articles() -> list[dict]:
    """Fetch articles from all configured sources."""
    all_articles = []
    for source in SOURCES:
        try:
            articles = fetch_feed(source)
            all_articles.extend(articles)
        except Exception:
            continue
    return all_articles
