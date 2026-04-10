import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

import cloudscraper
import feedparser
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from config import (
    AI_KEYWORDS,
    CONTENT_FETCH_TIMEOUT,
    FULL_CONTENT_FETCH_LIMIT,
    MAX_ARTICLES_TO_SUMMARIZE,
    MIN_ARTICLE_TEXT_LENGTH,
    PAGE_SOURCES,
    RSS_FEEDS,
    RSS_WINDOW_HOURS,
    USER_AGENT,
    logger,
)

# SSRF protection: block requests to metadata/internal endpoints
_SSRF_BLOCKED_HOSTS = frozenset(
    {
        "169.254.169.254",
        "metadata.google.internal",
        "metadata.azure.com",
        "metadata.internal",
        "kubernetes.default",
        "consul.service.consul",
    }
)
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_MAX_ENTRIES_PER_FEED = 100
_BLOCK_PATTERNS = (
    "cf-browser-verification",
    "cloudflare",
    "attention required",
    "just a moment",
    "captcha",
    "access denied",
)
_PAYWALL_PATTERNS = (
    "subscribe to continue",
    "subscription required",
    "for subscribers",
    "sign in to continue",
    "join to read",
    "create a free account to continue",
    "paywall",
)
_ARTICLE_URL_PATTERN = re.compile(r"/20\d{2}/\d{2}/\d{2}/")
_DATE_RE = re.compile(r'"(?:datePublished|Published)":"([^"]+)"')


def get_publish_date(entry) -> Optional[datetime]:
    """Extract publish date from an RSS entry, handling varied field names."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    for field in ("published", "updated", "created"):
        value = getattr(entry, field, None)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue
    return None


def is_within_window(entry, hours: int = RSS_WINDOW_HOURS) -> bool:
    """Check if an entry was published within the last N hours."""
    pub_date = get_publish_date(entry)
    if pub_date is None:
        return False
    now = datetime.now(timezone.utc)
    delta = now - pub_date
    return 0 <= delta.total_seconds() <= hours * 3600


def matches_ai_keywords(text: str) -> bool:
    """Check if text contains any AI-related keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in AI_KEYWORDS)


def _parse_article_published(value: str | None) -> Optional[datetime]:
    if not value or value == "Unknown":
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by URL match and title similarity."""
    seen_urls = set()
    unique = []

    for article in articles:
        url = article.get("url", "")
        title = article.get("title", "")

        if url in seen_urls:
            continue

        is_dupe = False
        for kept in unique:
            ratio = fuzz.ratio(title.lower(), kept["title"].lower())
            if ratio >= 90:
                is_dupe = True
                break

        if not is_dupe:
            seen_urls.add(url)
            unique.append(article)

    unique.sort(key=lambda article: _parse_article_published(article.get("published")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return unique


def _is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in _ALLOWED_SCHEMES and parsed.hostname not in _SSRF_BLOCKED_HOSTS


def _base_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _cloudscraper_session():
    session = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _looks_blocked(status_code: int, text: str) -> bool:
    blob = (text or "").lower()
    return status_code in {403, 429, 503} or any(token in blob for token in _BLOCK_PATTERNS)


def _looks_paywalled(text: str) -> bool:
    blob = (text or "").lower()
    return any(token in blob for token in _PAYWALL_PATTERNS)


def _extract_archive_org_url(target_url: str) -> Optional[str]:
    try:
        api = "https://archive.org/wayback/available"
        response = requests.get(api, params={"url": target_url}, timeout=CONTENT_FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        data = response.json()
        snapshot = data.get("archived_snapshots", {}).get("closest", {})
        archive_url = snapshot.get("url")
        return archive_url if archive_url and snapshot.get("available") else None
    except Exception as exc:
        logger.info("Archive.org lookup failed for %s: %s", target_url, exc)
        return None


def _archive_ph_candidates(target_url: str) -> list[str]:
    encoded = quote(target_url, safe="")
    return [
        f"https://archive.ph/{target_url}",
        f"https://archive.ph/{encoded}",
        f"https://archive.today/{encoded}",
    ]


def _fetch_html(url: str, use_cloudscraper: bool = False) -> Optional[requests.Response]:
    session = _cloudscraper_session() if use_cloudscraper else _base_session()
    response = session.get(url, timeout=CONTENT_FETCH_TIMEOUT)
    response.raise_for_status()
    return response


def _fetch_html_with_fallback(url: str, source_name: str) -> tuple[str, str]:
    if not _is_allowed_url(url):
        raise ValueError(f"Blocked SSRF attempt from config ({source_name}): {url}")

    try:
        response = _fetch_html(url, use_cloudscraper=False)
        if response is not None and not _looks_blocked(response.status_code, response.text) and not _looks_paywalled(response.text):
            return response.text, url
        logger.info("Direct fetch for %s looked blocked/paywalled; retrying with cloudscraper", url)
    except Exception as exc:
        logger.info("Direct fetch failed for %s: %s", url, exc)

    try:
        response = _fetch_html(url, use_cloudscraper=True)
        if response is not None and not _looks_blocked(response.status_code, response.text) and not _looks_paywalled(response.text):
            return response.text, url
        logger.info("Cloudscraper fetch for %s still looked blocked/paywalled; trying archives", url)
    except Exception as exc:
        logger.info("Cloudscraper fetch failed for %s: %s", url, exc)

    archive_org_url = _extract_archive_org_url(url)
    archive_candidates = ([archive_org_url] if archive_org_url else []) + _archive_ph_candidates(url)
    for archive_url in archive_candidates:
        if not archive_url:
            continue
        try:
            response = _fetch_html(archive_url, use_cloudscraper=False)
            if response is not None and response.text:
                logger.info("Using archived copy for %s via %s", url, archive_url)
                return response.text, archive_url
        except Exception as exc:
            logger.info("Archive lookup failed for %s via %s: %s", url, archive_url, exc)

    raise RuntimeError(f"Unable to fetch content for {url}")


def _normalize_candidate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc in {"web.archive.org", "archive.org"}:
        marker = "/http"
        if marker in parsed.path:
            original = parsed.path.split(marker, 1)[1]
            return f"http{original}"
    return url


def _extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = []
    for p in soup.find_all("p"):
        text = " ".join(p.get_text(" ", strip=True).split())
        if len(text) >= 40:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_pub_date_from_html(html: str) -> Optional[datetime]:
    match = _DATE_RE.search(html)
    if not match:
        return None
    try:
        parsed = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _enrich_article(article: dict) -> dict:
    url = article.get("url")
    if not url:
        return article
    try:
        html, fetched_from = _fetch_html_with_fallback(url, article.get("source", "article"))
    except Exception as exc:
        logger.info("Could not enrich article %s: %s", url, exc)
        return article

    body = _extract_article_text(html)
    pub_date = _extract_pub_date_from_html(html)

    if pub_date and not is_within_window(type("Entry", (), {"published_parsed": pub_date.timetuple(), "updated_parsed": None, "created_parsed": None})()):
        return article

    if body and (len(body) >= MIN_ARTICLE_TEXT_LENGTH or not _looks_paywalled(html)):
        article["summary"] = body[:2000]
        article["content"] = body[:4000]
        article["fetched_from"] = fetched_from
        if pub_date:
            article["published"] = pub_date.isoformat()
    elif _looks_paywalled(html):
        logger.info("Article %s appears paywalled even after fallback attempts", url)
    return article


def _fortune_candidates_from_html(html: str, listing_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    articles = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if not href or not title:
            continue
        absolute_url = _normalize_candidate_url(urljoin(listing_url, href))
        parsed = urlparse(absolute_url)
        if parsed.netloc != "fortune.com":
            continue
        if not _ARTICLE_URL_PATTERN.search(parsed.path):
            continue
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        articles.append(
            {
                "title": title[:300],
                "summary": "",
                "url": absolute_url,
                "source": "Fortune",
                "published": "Unknown",
            }
        )
    return articles


def _fetch_page_sources() -> list[dict]:
    articles = []
    for source in PAGE_SOURCES:
        source_name = source["name"]
        url = source["url"]
        try:
            logger.info("Fetching from %s page source...", source_name)
            html, fetched_from = _fetch_html_with_fallback(url, source_name)
            if source.get("extractor") == "fortune_ai":
                candidates = _fortune_candidates_from_html(html, fetched_from)
            else:
                logger.warning("Unknown page extractor for %s", source_name)
                continue

            for candidate in candidates[:FULL_CONTENT_FETCH_LIMIT]:
                enriched = _enrich_article(candidate)
                text = f"{enriched['title']} {enriched.get('summary', '')} {enriched.get('content', '')}"
                if not matches_ai_keywords(text):
                    continue
                published = enriched.get("published")
                if published and published != "Unknown":
                    try:
                        published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                        if published_dt.tzinfo is None:
                            published_dt = published_dt.replace(tzinfo=timezone.utc)
                        if not is_within_window(type("Entry", (), {"published_parsed": published_dt.timetuple(), "updated_parsed": None, "created_parsed": None})()):
                            continue
                    except ValueError:
                        pass
                articles.append(enriched)
        except Exception as exc:
            logger.warning("Error fetching from %s: %s", source_name, exc)
            continue
    return articles


def fetch_articles() -> list[dict]:
    """Fetch AI-relevant articles from all configured sources."""
    all_articles = []

    for source_name, feed_url in RSS_FEEDS:
        try:
            if not _is_allowed_url(feed_url):
                logger.warning("Blocked SSRF attempt from config (%s): %s", source_name, feed_url)
                continue
            logger.info("Fetching from %s...", source_name)
            feed = feedparser.parse(
                feed_url,
                agent=USER_AGENT,
                request_headers={"User-Agent": USER_AGENT},
            )

            if not hasattr(feed, "entries") or not feed.entries:
                logger.warning("No entries from %s", source_name)
                continue

            for entry in feed.entries[:_MAX_ENTRIES_PER_FEED]:
                if not is_within_window(entry):
                    continue

                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "").strip()
                link = getattr(entry, "link", "").strip()

                if not title or not link:
                    continue

                combined_text = f"{title} {summary}"
                if not matches_ai_keywords(combined_text):
                    continue

                all_articles.append(
                    {
                        "title": title[:300],
                        "summary": summary[:1000],
                        "url": link,
                        "source": source_name,
                        "published": str(get_publish_date(entry) or "Unknown"),
                    }
                )

        except Exception as e:
            logger.warning("Error fetching from %s: %s", source_name, e)
            continue

    all_articles.extend(_fetch_page_sources())
    logger.info("Found %d AI-relevant articles before dedup", len(all_articles))

    unique_articles = deduplicate(all_articles)
    logger.info("After dedup: %d articles", len(unique_articles))
    return unique_articles[:MAX_ARTICLES_TO_SUMMARIZE]
