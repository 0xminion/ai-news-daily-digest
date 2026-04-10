from __future__ import annotations

from ai_news_digest.config import ORTHOGONAL_RSS_FEEDS, ORTHOGONAL_SIGNALS_ENABLED
from .rss import fetch_rss_articles


def fetch_orthogonal_signal_articles() -> list[dict]:
    if not ORTHOGONAL_SIGNALS_ENABLED:
        return []
    articles = fetch_rss_articles(feeds=ORTHOGONAL_RSS_FEEDS)
    for article in articles:
        article.setdefault('signals', []).append('orthogonal-source')
    return articles
