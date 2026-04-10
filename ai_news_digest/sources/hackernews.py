from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from rapidfuzz import fuzz

from ai_news_digest.config import HN_ENABLED, HN_MAX_STORIES, HN_MIN_COMMENTS, HN_MIN_POINTS, HN_SIGNAL_QUERIES, HN_SIGNAL_WINDOW_HOURS, USER_AGENT, logger
from ai_news_digest.storage.archive import normalize_title, normalize_url

HN_API = 'https://hn.algolia.com/api/v1/search_by_date'


def fetch_hn_signals() -> list[dict]:
    if not HN_ENABLED:
        return []
    collected, seen = [], set()
    cutoff = int((datetime.now(timezone.utc) - timedelta(hours=HN_SIGNAL_WINDOW_HOURS)).timestamp())
    for query in HN_SIGNAL_QUERIES:
        try:
            r = requests.get(HN_API, params={'query': query, 'tags': 'story', 'hitsPerPage': 30, 'numericFilters': f'created_at_i>{cutoff}'}, timeout=30, headers={'User-Agent': USER_AGENT})
            r.raise_for_status(); hits = r.json().get('hits', [])
        except Exception as exc:
            logger.info('Hacker News lookup failed for query %s: %s', query, exc); continue
        for hit in hits:
            title = (hit.get('title') or hit.get('story_title') or '').strip()
            points = int(hit.get('points') or 0); comments = int(hit.get('num_comments') or 0)
            if not title or (points < HN_MIN_POINTS and comments < HN_MIN_COMMENTS):
                continue
            discussion_url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            target_url = (hit.get('url') or '').strip()
            if not target_url or urlparse(target_url).netloc.endswith('news.ycombinator.com'):
                continue
            key = normalize_url(target_url) or normalize_title(title)
            if not key or key in seen:
                continue
            seen.add(key)
            collected.append({'title': title[:300], 'url': target_url, 'hn_points': points, 'hn_comments': comments, 'hn_discussion_url': discussion_url, 'published': hit.get('created_at') or 'Unknown'})
    collected.sort(key=lambda item: (item.get('hn_points', 0), item.get('hn_comments', 0)), reverse=True)
    return collected[:HN_MAX_STORIES]


def enrich_articles_with_hn(articles: list[dict]) -> list[dict]:
    hn_articles = fetch_hn_signals()
    if not hn_articles:
        return articles
    by_url = {normalize_url(article.get('url')): article for article in articles if normalize_url(article.get('url'))}
    for hn in hn_articles:
        target = by_url.get(normalize_url(hn.get('url')))
        if target is None:
            ht = normalize_title(hn.get('title'))
            for article in articles:
                if fuzz.ratio(normalize_title(article.get('title')), ht) >= 92:
                    target = article
                    break
        if target is None:
            continue  # enrichment-only, never standalone
        target['hn_points'] = max(target.get('hn_points', 0), hn.get('hn_points', 0))
        target['hn_comments'] = max(target.get('hn_comments', 0), hn.get('hn_comments', 0))
        target['hn_discussion_url'] = hn.get('hn_discussion_url')
        target.setdefault('signals', []).append('hackernews')
    return articles
