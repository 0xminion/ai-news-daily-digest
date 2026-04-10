import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from ai_news_digest.sources.common import parse_entry_date
from ai_news_digest.sources.hackernews import enrich_articles_with_hn
from ai_news_digest.sources.pages import (
    fetch_html_with_fallback,
    fortune_candidates_from_html,
    normalize_candidate_url,
)
from ai_news_digest.sources.pipeline import fetch_articles
from ai_news_digest.sources.rss import matches_ai_keywords


class TestGetPublishDate:
    def test_published_parsed(self):
        entry = MagicMock()
        entry.published_parsed = time.gmtime()
        entry.updated_parsed = None
        entry.created_parsed = None
        result = parse_entry_date(entry)
        assert result is not None
        assert isinstance(result, datetime)

    def test_no_date_returns_none(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.created_parsed = None
        assert parse_entry_date(entry) is None


class TestWindowAndKeywords:
    def test_old_article_date_exists(self):
        entry = MagicMock()
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        entry.published_parsed = old_time.timetuple()
        entry.updated_parsed = None
        entry.created_parsed = None
        assert parse_entry_date(entry) is not None

    def test_matches_ai_keywords(self):
        assert matches_ai_keywords('OpenAI launches new model') is True
        assert matches_ai_keywords('Weather forecast for tomorrow') is False


class TestFortuneAndArchiveHelpers:
    def test_normalize_candidate_url_unwraps_wayback_link(self):
        url = 'https://web.archive.org/web/20260408210842/https://fortune.com/2026/04/10/test-ai-story/'
        assert normalize_candidate_url(url) == 'https://fortune.com/2026/04/10/test-ai-story/'

    def test_fortune_candidates_extract_article_links(self):
        html = '''
        <html><body>
          <a href="/2026/04/10/test-ai-story/">Test AI Story</a>
          <a href="/2026/04/10/test-ai-story/">Test AI Story</a>
          <a href="/2026/04/10/other-story/">Another AI Story</a>
        </body></html>
        '''
        result = fortune_candidates_from_html(html, 'https://fortune.com/section/artificial-intelligence/')
        assert len(result) == 2
        assert result[0]['source'] == 'Fortune'

    @patch('ai_news_digest.sources.pages._extract_archive_org_url', return_value='https://web.archive.org/web/20260101000000/https://example.com/story')
    @patch('ai_news_digest.sources.pages._fetch_html')
    def test_fetch_html_with_fallback_uses_archive_after_block(self, mock_fetch_html, _mock_archive_org):
        blocked = MagicMock(status_code=403, text='cloudflare')
        archived = MagicMock(status_code=200, text='archived story')
        mock_fetch_html.side_effect = [blocked, blocked, archived]
        html, final_url = fetch_html_with_fallback('https://example.com/story', 'Example')
        assert html == 'archived story'
        assert 'web.archive.org' in final_url


class TestHackerNewsSignals:
    @patch('ai_news_digest.sources.hackernews.fetch_hn_signals')
    def test_enrich_hackernews_signals_enriches_matching_article(self, mock_hn):
        mock_hn.return_value = [
            {
                'title': 'OpenAI launches new model',
                'url': 'https://example.com/story',
                'hn_points': 120,
                'hn_comments': 40,
                'hn_discussion_url': 'https://news.ycombinator.com/item?id=1',
            }
        ]
        articles = [{'title': 'OpenAI launches new model', 'url': 'https://example.com/story', 'source': 'TechCrunch', 'published': '2026-04-10T07:00:00Z'}]
        enriched = enrich_articles_with_hn(articles)
        assert len(enriched) == 1
        assert enriched[0]['hn_points'] == 120
        assert enriched[0]['hn_comments'] == 40

    @patch('ai_news_digest.sources.hackernews.fetch_hn_signals')
    def test_hn_is_enrichment_only(self, mock_hn):
        mock_hn.return_value = [
            {'title': 'Standalone HN item', 'url': 'https://example.com/hn-only', 'hn_points': 90, 'hn_comments': 12, 'hn_discussion_url': 'https://news.ycombinator.com/item?id=2'}
        ]
        assert enrich_articles_with_hn([]) == []


class TestFetchArticles:
    @patch('ai_news_digest.sources.pipeline.fetch_orthogonal_signal_articles', return_value=[])
    @patch('ai_news_digest.sources.pipeline.fetch_page_articles', return_value=[])
    @patch('ai_news_digest.sources.pipeline.enrich_articles_with_hn', side_effect=lambda articles: articles)
    @patch('ai_news_digest.sources.pipeline.exclude_cross_day_duplicates', side_effect=lambda articles, days: (articles, 0))
    @patch('ai_news_digest.sources.pipeline.fetch_rss_articles')
    def test_fetch_articles_returns_ranked_articles(self, mock_rss, _mock_cross_day, _mock_hn, _mock_pages, _mock_orth):
        mock_rss.return_value = [
            {'title': 'New AI model released by OpenAI', 'summary': 'OpenAI released a new large language model', 'url': 'https://example.com/article', 'source': 'Test', 'published': '2026-04-10T08:00:00+00:00'}
        ]
        articles, trend_snapshot, clusters = fetch_articles()
        assert len(articles) == 1
        assert articles[0]['title'] == 'New AI model released by OpenAI'
        assert isinstance(trend_snapshot, dict)
        assert len(clusters) == 1
