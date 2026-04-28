from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlparse

import cloudscraper
import requests
from bs4 import BeautifulSoup

from ai_news_digest.config import CONTENT_FETCH_TIMEOUT, FULL_CONTENT_FETCH_LIMIT, MIN_ARTICLE_TEXT_LENGTH, PAGE_SOURCES, RSS_WINDOW_HOURS, USER_AGENT, logger
from ai_news_digest.config.keywords import matches_ai_keywords
from ai_news_digest.utils.retry import with_retry
from .common import within_hours

_SSRF_BLOCKED_HOSTS = frozenset({
    # Cloud metadata endpoints
    '169.254.169.254', 'metadata.google.internal', 'metadata.azure.com',
    'metadata.internal', 'kubernetes.default', 'consul.service.consul',
    # Localhost
    'localhost', '127.0.0.1', '0.0.0.0', '::1',
    # Common internal names
    'host.docker.internal', 'gateway.docker.internal',
})
_ALLOWED_SCHEMES = frozenset({'http', 'https'})
_BLOCK_PATTERNS = ('cf-browser-verification', 'cloudflare', 'attention required', 'just a moment', 'captcha', 'access denied')
_PAYWALL_PATTERNS = ('subscribe to continue', 'subscription required', 'for subscribers', 'sign in to continue', 'join to read', 'create a free account to continue', 'paywall')
_ARTICLE_URL_PATTERN = re.compile(r'/20\d{2}/\d{2}/\d{2}/')
_DATE_RE = re.compile(r'"(?:datePublished|Published)":"([^"]+)"')


# ---------------------------------------------------------------------------
# HTML sanitization utilities
# ---------------------------------------------------------------------------

def _strip_html_tags(text: str | None) -> str:
    """Remove HTML tags and unescape HTML entities from raw text."""
    if not text:
        return ''
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    # Also unescape numeric entities (BeautifulSoup handles most but not all)
    import html
    text = html.unescape(text)
    # Collapse redundant whitespace
    return ' '.join(text.split())


# ---------------------------------------------------------------------------
# URL safety
# ---------------------------------------------------------------------------

def _is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname in _SSRF_BLOCKED_HOSTS:
        return False
    # Also check if hostname is a private IP
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        pass  # hostname is not an IP, that's fine
    return True


# ---------------------------------------------------------------------------
# Block / paywall detection
# ---------------------------------------------------------------------------

def _looks_blocked(status_code: int, text: str) -> bool:
    blob = (text or '').lower()
    return status_code in {403, 429, 503} or any(t in blob for t in _BLOCK_PATTERNS)


def _looks_paywalled(text: str) -> bool:
    blob = (text or '').lower()
    return any(t in blob for t in _PAYWALL_PATTERNS)


# ---------------------------------------------------------------------------
# HTTP sessions
# ---------------------------------------------------------------------------

def _base_session():
    s = requests.Session()
    s.headers.update({'User-Agent': USER_AGENT})
    return s


def _cloudscraper_session():
    s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    s.headers.update({'User-Agent': USER_AGENT})
    return s


# ---------------------------------------------------------------------------
# Archive fallbacks
# ---------------------------------------------------------------------------

@with_retry(max_attempts=2, delay=3.0)
def _extract_archive_org_url(target_url: str) -> str | None:
    r = requests.get(
        'https://archive.org/wayback/available',
        params={'url': target_url},
        timeout=CONTENT_FETCH_TIMEOUT,
        headers={'User-Agent': USER_AGENT},
    )
    r.raise_for_status()
    data = r.json()
    snap = data.get('archived_snapshots', {}).get('closest', {})
    url = snap.get('url')
    return url if url and snap.get('available') else None


def _archive_ph_candidates(target_url: str) -> list[str]:
    encoded = quote(target_url, safe='')
    return [f'https://archive.ph/{encoded}', f'https://archive.today/{encoded}']


# ---------------------------------------------------------------------------
# Fetching with fallback chain
# ---------------------------------------------------------------------------

@with_retry(max_attempts=2, delay=3.0, backoff=2.0)
def _fetch_html(url: str, use_cloudscraper=False):
    s = _cloudscraper_session() if use_cloudscraper else _base_session()
    r = s.get(url, timeout=CONTENT_FETCH_TIMEOUT, allow_redirects=False)
    r.raise_for_status()
    # Redirects: if we got a redirect, validate the destination before following
    if r.is_redirect or (300 <= r.status_code < 400):
        location = r.headers.get('Location', '')
        if not location:
            raise RuntimeError(f'Redirect from {url} has no Location header')
        resolved = urljoin(url, location)
        if not _is_allowed_url(resolved):
            raise ValueError(f'Blocked SSRF redirect target: {resolved}')
        # Follow the redirect with a validated target
        r = s.get(resolved, timeout=CONTENT_FETCH_TIMEOUT, allow_redirects=False)
        r.raise_for_status()
    return r


def fetch_html_with_fallback(url: str, source_name: str) -> tuple[str, str]:
    if not _is_allowed_url(url):
        raise ValueError(f'Blocked SSRF attempt from config ({source_name}): {url}')
    try:
        r = _fetch_html(url, use_cloudscraper=False)
        if r is not None and not _looks_blocked(r.status_code, r.text) and not _looks_paywalled(r.text):
            return r.text, url
        logger.info('Direct fetch for %s looked blocked/paywalled; retrying with cloudscraper', url)
    except Exception as exc:
        logger.info('Direct fetch failed for %s: %s', url, exc)
    try:
        r = _fetch_html(url, use_cloudscraper=True)
        if r is not None and not _looks_blocked(r.status_code, r.text) and not _looks_paywalled(r.text):
            return r.text, url
        logger.info('Cloudscraper fetch for %s still looked blocked/paywalled; trying archives', url)
    except Exception as exc:
        logger.info('Cloudscraper fetch failed for %s: %s', url, exc)
    try:
        archive_url = _extract_archive_org_url(url)
    except Exception:
        archive_url = None
    for candidate in ([archive_url] if archive_url else []) + _archive_ph_candidates(url):
        if not candidate:
            continue
        if not _is_allowed_url(candidate):
            logger.info('Skipping archive candidate that fails SSRF check: %s', candidate)
            continue
        try:
            r = _fetch_html(candidate, use_cloudscraper=False)
            if r is not None and r.text:
                logger.info('Using archived copy for %s via %s', url, candidate)
                return r.text, candidate
        except Exception as exc:
            logger.info('Archive lookup failed for %s via %s: %s', url, candidate, exc)
    raise RuntimeError(f'Unable to fetch content for {url}')


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def normalize_candidate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc in {'web.archive.org', 'archive.org'}:
        marker = '/http'
        if marker in parsed.path:
            return f"http{parsed.path.split(marker, 1)[1]}"
    return url


def extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    parts = []
    for p in soup.find_all('p'):
        text = ' '.join(p.get_text(' ', strip=True).split())
        if len(text) >= 40:
            parts.append(text)
    return '\n\n'.join(parts)


def extract_pub_date_from_html(html: str):
    m = _DATE_RE.search(html)
    if not m:
        return None
    try:
        dt = datetime.fromisoformat(m.group(1).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def enrich_article(article: dict) -> dict:
    url = article.get('url')
    if not url:
        return article
    try:
        html, fetched_from = fetch_html_with_fallback(url, article.get('source', 'article'))
    except Exception as exc:
        logger.info('Could not enrich article %s: %s', url, exc)
        return article
    body = extract_article_text(html)
    pub_date = extract_pub_date_from_html(html)
    if pub_date and not within_hours(pub_date, RSS_WINDOW_HOURS):
        return article
    if body and (len(body) >= MIN_ARTICLE_TEXT_LENGTH or not _looks_paywalled(html)):
        article['summary'] = body[:2000]
        article['content'] = body[:4000]
        article['fetched_from'] = fetched_from
        if pub_date:
            article['published'] = pub_date.isoformat()
    return article


# ---------------------------------------------------------------------------
# Page source fetching
# ---------------------------------------------------------------------------

def fortune_candidates_from_html(html: str, listing_url: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    seen, articles = set(), []
    for anchor in soup.find_all('a', href=True):
        href = anchor['href'].strip()
        title = ' '.join(anchor.get_text(' ', strip=True).split())
        if not href or not title:
            continue
        absolute_url = normalize_candidate_url(urljoin(listing_url, href))
        parsed = urlparse(absolute_url)
        if parsed.netloc != 'fortune.com' or not _ARTICLE_URL_PATTERN.search(parsed.path) or absolute_url in seen:
            continue
        seen.add(absolute_url)
        articles.append({'title': title[:300], 'summary': '', 'url': absolute_url, 'source': 'Fortune', 'published': 'Unknown'})
    return articles


def fetch_page_articles(sources=None) -> list[dict]:
    sources = sources or PAGE_SOURCES
    articles = []
    for source in sources:
        try:
            logger.info('Fetching from %s page source...', source['name'])
            html, fetched_from = fetch_html_with_fallback(source['url'], source['name'])
            candidates = fortune_candidates_from_html(html, fetched_from) if source.get('extractor') == 'fortune_ai' else []
            for candidate in candidates[:FULL_CONTENT_FETCH_LIMIT]:
                enriched = enrich_article(candidate)
                text = f"{enriched.get('title', '')} {enriched.get('summary', '')} {enriched.get('content', '')}"
                if matches_ai_keywords(text):
                    articles.append(enriched)
        except Exception as exc:
            logger.warning('Error fetching from %s: %s', source['name'], exc)
    return articles
