import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from fetcher import (
    _fetch_html_with_fallback,
    _fortune_candidates_from_html,
    _normalize_candidate_url,
    get_publish_date,
    is_within_window,
    matches_ai_keywords,
    deduplicate,
    fetch_articles,
)


class TestGetPublishDate:
    def test_published_parsed(self):
        entry = MagicMock()
        entry.published_parsed = time.gmtime()
        entry.updated_parsed = None
        entry.created_parsed = None
        result = get_publish_date(entry)
        assert result is not None
        assert isinstance(result, datetime)

    def test_fallback_to_updated(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = time.gmtime()
        entry.created_parsed = None
        result = get_publish_date(entry)
        assert result is not None

    def test_no_date_returns_none(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.created_parsed = None
        result = get_publish_date(entry)
        assert result is None


class TestIsWithinWindow:
    def test_recent_article_passes(self):
        entry = MagicMock()
        entry.published_parsed = time.gmtime()
        entry.updated_parsed = None
        entry.created_parsed = None
        assert is_within_window(entry) is True

    def test_old_article_rejected(self):
        entry = MagicMock()
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        entry.published_parsed = old_time.timetuple()
        entry.updated_parsed = None
        entry.created_parsed = None
        assert is_within_window(entry) is False

    def test_no_date_excluded(self):
        """Entries with no parseable date are excluded — strict window policy."""
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.created_parsed = None
        assert is_within_window(entry) is False


class TestMatchesAiKeywords:
    def test_matches_ai(self):
        assert matches_ai_keywords("New artificial intelligence breakthrough") is True

    def test_matches_entity_names(self):
        assert matches_ai_keywords("DeepMind releases new model") is True

    def test_matches_openai(self):
        assert matches_ai_keywords("OpenAI announces GPT-5") is True

    def test_rejects_non_ai(self):
        assert matches_ai_keywords("Weather forecast for tomorrow") is False

    def test_case_insensitive(self):
        assert matches_ai_keywords("ARTIFICIAL INTELLIGENCE is growing") is True


class TestDeduplicate:
    def test_exact_url_dedup(self):
        articles = [
            {"title": "Story A", "url": "https://example.com/1"},
            {"title": "Story B", "url": "https://example.com/1"},
        ]
        result = deduplicate(articles)
        assert len(result) == 1

    def test_similar_titles_deduped(self):
        articles = [
            {"title": "OpenAI releases GPT-5 model", "url": "https://a.com/1"},
            {"title": "OpenAI releases GPT-5 model today", "url": "https://b.com/2"},
        ]
        result = deduplicate(articles)
        assert len(result) == 1

    def test_different_titles_kept(self):
        articles = [
            {"title": "OpenAI releases GPT-5", "url": "https://a.com/1"},
            {"title": "NVIDIA reports record revenue", "url": "https://b.com/2"},
        ]
        result = deduplicate(articles)
        assert len(result) == 2

    def test_empty_list(self):
        assert deduplicate([]) == []


class TestFortuneHelpers:
    def test_normalize_candidate_url_unwraps_wayback_link(self):
        url = "https://web.archive.org/web/20260408210842/https://fortune.com/2026/04/10/test-ai-story/"
        assert _normalize_candidate_url(url) == "https://fortune.com/2026/04/10/test-ai-story/"

    def test_fortune_candidates_extract_article_links(self):
        html = '''
        <html><body>
          <a href="/2026/04/10/test-ai-story/">Test AI Story</a>
          <a href="/2026/04/10/test-ai-story/">Test AI Story</a>
          <a href="/2026/04/10/other-story/">Another AI Story</a>
          <a href="/section/artificial-intelligence/">Section Link</a>
        </body></html>
        '''
        result = _fortune_candidates_from_html(html, "https://fortune.com/section/artificial-intelligence/")
        assert len(result) == 2
        assert result[0]["source"] == "Fortune"
        assert result[0]["url"].startswith("https://fortune.com/2026/04/10/")

    @patch("fetcher._extract_archive_org_url", return_value="https://web.archive.org/web/20260101000000/https://example.com/story")
    @patch("fetcher._fetch_html")
    def test_fetch_html_with_fallback_uses_archive_after_block(self, mock_fetch_html, _mock_archive_org):
        blocked = MagicMock(status_code=403, text="cloudflare")
        archived = MagicMock(status_code=200, text="archived story")
        mock_fetch_html.side_effect = [blocked, blocked, archived]

        html, final_url = _fetch_html_with_fallback("https://example.com/story", "Example")
        assert html == "archived story"
        assert "web.archive.org" in final_url

    @patch("fetcher._extract_archive_org_url", return_value="https://web.archive.org/web/20260101000000/https://example.com/story")
    @patch("fetcher._fetch_html")
    def test_fetch_html_with_fallback_uses_archive_after_paywall(self, mock_fetch_html, _mock_archive_org):
        paywalled = MagicMock(status_code=200, text="subscribe to continue reading")
        archived = MagicMock(status_code=200, text="archived story")
        mock_fetch_html.side_effect = [paywalled, paywalled, archived]

        html, final_url = _fetch_html_with_fallback("https://example.com/story", "Example")
        assert html == "archived story"
        assert "web.archive.org" in final_url


class TestFetchArticles:
    @patch("fetcher.feedparser.parse")
    def test_fetch_parses_valid_feed(self, mock_parse):
        entry = MagicMock()
        entry.title = "New AI model released by OpenAI"
        entry.summary = "OpenAI released a new large language model"
        entry.link = "https://example.com/article"
        entry.published_parsed = time.gmtime()
        entry.updated_parsed = None
        entry.created_parsed = None

        mock_parse.return_value = MagicMock(entries=[entry])

        with patch("fetcher.RSS_FEEDS", [("Test", "https://test.com/feed")]), patch("fetcher.PAGE_SOURCES", []):
            articles = fetch_articles()
        assert len(articles) >= 1
        assert articles[0]["title"] == "New AI model released by OpenAI"

    @patch("fetcher.feedparser.parse")
    def test_fetch_handles_empty_feed(self, mock_parse):
        mock_parse.return_value = MagicMock(entries=[])
        with patch("fetcher.RSS_FEEDS", [("Test", "https://test.com/feed")]), patch("fetcher.PAGE_SOURCES", []):
            articles = fetch_articles()
        assert articles == []

    @patch("fetcher.feedparser.parse")
    def test_fetch_handles_feed_error(self, mock_parse):
        mock_parse.side_effect = Exception("Network error")
        with patch("fetcher.RSS_FEEDS", [("Test", "https://test.com/feed")]), patch("fetcher.PAGE_SOURCES", []):
            articles = fetch_articles()
        assert articles == []
