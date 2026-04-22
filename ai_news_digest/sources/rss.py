from __future__ import annotations

import feedparser

from ai_news_digest.config import RSS_FEEDS, RSS_WINDOW_HOURS, USER_AGENT, logger
from ai_news_digest.config.keywords import matches_ai_keywords
from ai_news_digest.utils.retry import with_retry
from .common import parse_entry_date, within_hours
from .pages import _is_allowed_url


@with_retry(max_attempts=2, delay=2.0, backoff=2.0)
def _fetch_feed(feed_url: str, user_agent: str) -> feedparser.FeedParserDict:
    """Fetch and parse an RSS feed with retry."""
    return feedparser.parse(feed_url, agent=user_agent, request_headers={'User-Agent': user_agent})


def fetch_rss_articles(feeds=None) -> list[dict]:
    all_articles = []
    feeds = feeds or RSS_FEEDS
    for source_name, feed_url in feeds:
        if not _is_allowed_url(feed_url):
            logger.warning('Blocked SSRF attempt in RSS feed for %s: %s', source_name, feed_url)
            continue
        try:
            logger.info('Fetching from %s...', source_name)
            feed = _fetch_feed(feed_url, USER_AGENT)
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
