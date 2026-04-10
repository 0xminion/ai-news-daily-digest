from __future__ import annotations

import feedparser

from ai_news_digest.config import AI_KEYWORDS, RSS_FEEDS, RSS_WINDOW_HOURS, USER_AGENT, logger
from .common import parse_entry_date, within_hours


def matches_ai_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in AI_KEYWORDS)


def fetch_rss_articles(feeds=None) -> list[dict]:
    all_articles = []
    feeds = feeds or RSS_FEEDS
    for source_name, feed_url in feeds:
        try:
            logger.info('Fetching from %s...', source_name)
            feed = feedparser.parse(feed_url, agent=USER_AGENT, request_headers={'User-Agent': USER_AGENT})
            if not hasattr(feed, 'entries') or not feed.entries:
                logger.warning('No entries from %s', source_name)
                continue
            for entry in feed.entries[:100]:
                published = parse_entry_date(entry)
                if not within_hours(published, RSS_WINDOW_HOURS):
                    continue
                title = getattr(entry, 'title', '').strip()
                summary = getattr(entry, 'summary', '').strip()
                link = getattr(entry, 'link', '').strip()
                if not title or not link:
                    continue
                if not matches_ai_keywords(f'{title} {summary}'):
                    continue
                all_articles.append({
                    'title': title[:300],
                    'summary': summary[:1000],
                    'url': link,
                    'source': source_name,
                    'published': str(published or 'Unknown'),
                })
        except Exception as exc:
            logger.warning('Error fetching from %s: %s', source_name, exc)
    return all_articles
