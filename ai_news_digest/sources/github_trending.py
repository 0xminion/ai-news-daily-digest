from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from ai_news_digest.config import GITHUB_TRENDING_ENABLED, GITHUB_TRENDING_SINCE, GITHUB_TRENDING_TOP_N, USER_AGENT, logger
from ai_news_digest.config.keywords import matches_ai_keywords
from ai_news_digest.utils.retry import with_retry

GITHUB_TRENDING_URL = 'https://github.com/trending'


@with_retry(max_attempts=2, delay=3.0, backoff=2.0)
def _fetch_trending_page(since: str = 'daily') -> str:
    """Fetch the GitHub trending page HTML."""
    resp = requests.get(
        GITHUB_TRENDING_URL,
        params={'since': since},
        timeout=30,
        headers={'User-Agent': USER_AGENT},
    )
    resp.raise_for_status()
    return resp.text


def _parse_trending(html: str) -> list[dict]:
    """Parse GitHub trending page into repo dicts."""
    soup = BeautifulSoup(html, 'html.parser')
    repos = []

    for article in soup.select('article.Box-row'):
        # Repo full name
        h2 = article.select_one('h2 a')
        if not h2:
            continue
        full_name = h2.get('href', '').strip('/')
        if not full_name:
            continue

        # Description
        desc_el = article.select_one('p')
        description = desc_el.get_text(strip=True) if desc_el else ''

        # Language
        lang_el = article.select_one('[itemprop="programmingLanguage"]')
        language = lang_el.get_text(strip=True) if lang_el else ''

        # Stars
        star_el = article.select_one('a.Link--muted[href*="/stargazers"]')
        stars_text = star_el.get_text(strip=True).replace(',', '') if star_el else '0'
        try:
            stars = int(stars_text)
        except ValueError:
            stars = 0

        # Today's stars
        today_el = article.select_one('span.d-inline-block.float-sm-right')
        today_stars = ''
        if today_el:
            today_stars = today_el.get_text(strip=True)

        repos.append({
            'full_name': full_name,
            'description': description,
            'language': language,
            'stars': stars,
            'today_stars': today_stars,
            'url': f'https://github.com/{full_name}',
            'topics': [],  # would need extra API call to get topics
        })

    return repos


def _is_ai_repo(repo: dict) -> bool:
    """Check if a repo is AI/ML related by name, description."""
    text = ' '.join([
        repo.get('full_name', ''),
        repo.get('description', ''),
        ' '.join(repo.get('topics', [])),
    ])
    return matches_ai_keywords(text)


def fetch_github_trending(top_n: int | None = None) -> list[dict]:
    """Fetch top AI/ML repos trending on GitHub today.

    Scrapes github.com/trending and filters for AI/ML repos.
    Returns articles in the same format as other sources.
    """
    if not GITHUB_TRENDING_ENABLED:
        return []

    top_n = top_n or GITHUB_TRENDING_TOP_N
    logger.info('Fetching GitHub trending repos (top %d)...', top_n)

    try:
        html = _fetch_trending_page(GITHUB_TRENDING_SINCE)
        repos = _parse_trending(html)
    except Exception as exc:
        logger.warning('GitHub trending fetch failed: %s', exc)
        return []

    ai_repos = [r for r in repos if _is_ai_repo(r)]
    logger.info('Found %d AI/ML repos from %d trending', len(ai_repos), len(repos))

    articles = []
    for repo in ai_repos[:top_n]:
        stars_str = f"{repo['stars']:,}" if repo['stars'] else '?'
        today_str = f" ({repo['today_stars']})" if repo.get('today_stars') else ''
        lang_str = f" | {repo['language']}" if repo.get('language') else ''
        articles.append({
            'title': f"{repo['full_name']}: {repo.get('description', 'No description')[:200]}",
            'summary': f"⭐ {stars_str} stars{today_str}{lang_str} | {repo.get('description', '')}",
            'url': repo['url'],
            'source': 'GitHub Trending',
            'published': 'Unknown',
            'subtype': 'repo',
            'signals': ['github-trending', 'new-repo'],
            'hn_points': 0,
            'hn_comments': 0,
        })

    return articles
