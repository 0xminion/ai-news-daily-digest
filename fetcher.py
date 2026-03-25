import time
from datetime import datetime, timezone
from typing import Optional

import feedparser
from rapidfuzz import fuzz

from config import (
    RSS_FEEDS,
    AI_KEYWORDS,
    MAX_ARTICLES_TO_SUMMARIZE,
    RSS_WINDOW_HOURS,
    USER_AGENT,
    logger,
)


def get_publish_date(entry) -> Optional[datetime]:
    """Extract publish date from an RSS entry, handling varied field names."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def is_within_window(entry, hours: int = RSS_WINDOW_HOURS) -> bool:
    """Check if an entry was published within the last N hours.
    Returns False for entries with no parseable date — strict 24h window only.
    """
    pub_date = get_publish_date(entry)
    if pub_date is None:
        # No date available — exclude rather than include (strict window)
        return False
    now = datetime.now(timezone.utc)
    delta = now - pub_date
    return delta.total_seconds() <= hours * 3600


def matches_ai_keywords(text: str) -> bool:
    """Check if text contains any AI-related keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in AI_KEYWORDS)


def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by URL match and title similarity."""
    seen_urls = set()
    unique = []

    for article in articles:
        url = article.get("url", "")
        title = article.get("title", "")

        # Exact URL match
        if url in seen_urls:
            continue

        # Title similarity check against already-kept articles
        is_dupe = False
        for kept in unique:
            ratio = fuzz.ratio(title.lower(), kept["title"].lower())
            if ratio >= 90:
                is_dupe = True
                break

        if not is_dupe:
            seen_urls.add(url)
            unique.append(article)

    return unique


def fetch_articles() -> list[dict]:
    """Fetch AI-relevant articles from all configured RSS feeds."""
    all_articles = []

    for source_name, feed_url in RSS_FEEDS:
        try:
            logger.info(f"Fetching from {source_name}...")
            feed = feedparser.parse(
                feed_url,
                agent=USER_AGENT,
                request_headers={"User-Agent": USER_AGENT},
            )

            if not hasattr(feed, "entries") or not feed.entries:
                logger.warning(f"No entries from {source_name}")
                continue

            for entry in feed.entries:
                if not is_within_window(entry):
                    continue

                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "").strip()
                link = getattr(entry, "link", "").strip()

                if not title or not link:
                    continue

                # Keyword filter on title + summary
                combined_text = f"{title} {summary}"
                if not matches_ai_keywords(combined_text):
                    continue

                # Strip control characters and cap field lengths
                title = title[:300]
                summary = summary[:1000]

                all_articles.append(
                    {
                        "title": title,
                        "summary": summary,
                        "url": link,
                        "source": source_name,
                        "published": str(get_publish_date(entry) or "Unknown"),
                    }
                )

        except Exception as e:
            logger.warning(f"Error fetching from {source_name}: {e}")
            continue

    logger.info(f"Found {len(all_articles)} AI-relevant articles before dedup")

    # Deduplicate
    unique_articles = deduplicate(all_articles)
    logger.info(f"After dedup: {len(unique_articles)} articles")

    # Cap at max
    return unique_articles[:MAX_ARTICLES_TO_SUMMARIZE]
