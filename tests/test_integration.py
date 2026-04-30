"""End-to-end integration tests with recorded/mocked HTTP responses."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_news_digest.llm import AgentSummarizationRequired
from ai_news_digest.pipeline import fetch_digest_inputs
from ai_news_digest.sources.adapter import RSSSourceAdapter, PageSourceAdapter, OrthogonalSourceAdapter, GitHubTrendingAdapter


class TestFetchDigestInputsIntegration:
    """Run the full fetch pipeline with synthetic adapters."""

    def test_full_pipeline_with_synthetic_articles(self):
        rss_adapter = MagicMock(spec=RSSSourceAdapter)
        rss_adapter.name = "rss"
        rss_adapter.fetch.return_value = [
            {
                "title": "OpenAI releases GPT-5",
                "summary": "OpenAI announced GPT-5 today.",
                "url": "https://example.com/1",
                "source": "TestRSS",
                "published": "2026-04-30T08:00:00+00:00",
            },
            {
                "title": "Google launches Gemini 2",
                "summary": "Google announced Gemini 2.",
                "url": "https://example.com/2",
                "source": "TestRSS",
                "published": "2026-04-30T08:00:00+00:00",
            },
        ]

        page_adapter = MagicMock(spec=PageSourceAdapter)
        page_adapter.name = "pages"
        page_adapter.fetch.return_value = []

        orth_adapter = MagicMock(spec=OrthogonalSourceAdapter)
        orth_adapter.name = "orthogonal"
        orth_adapter.fetch.return_value = [
            {
                "title": "New paper on transformers",
                "summary": "Research paper.",
                "url": "https://arxiv.org/abs/1234",
                "source": "arXiv AI",
                "published": "2026-04-30T08:00:00+00:00",
            }
        ]

        gh_adapter = MagicMock(spec=GitHubTrendingAdapter)
        gh_adapter.name = "github_trending"
        gh_adapter.fetch.return_value = [
            {
                "title": "someuser/awesome-ml: A cool ML repo",
                "summary": "Stars and description",
                "url": "https://github.com/someuser/awesome-ml",
                "source": "GitHub Trending",
                "published": "Unknown",
                "subtype": "repo",
            }
        ]

        adapters = [rss_adapter, page_adapter, orth_adapter, gh_adapter]

        with patch("ai_news_digest.pipeline.enrich_articles_with_hn", side_effect=lambda articles: articles):
            with patch("ai_news_digest.pipeline._storage.exclude_cross_day_duplicates", side_effect=lambda articles, days: (articles, 0)):
                payload = fetch_digest_inputs(adapters=adapters)

        assert "run_id" in payload
        assert len(payload["main_articles"]) >= 0
        assert len(payload["research_articles"]) >= 0
        assert isinstance(payload["trend_snapshot"], dict)
        assert isinstance(payload["main_clusters"], list)
        assert isinstance(payload["research_clusters"], list)

    def test_adapter_failure_is_graceful(self):
        bad_adapter = MagicMock()
        bad_adapter.name = "bad"
        bad_adapter.fetch.side_effect = RuntimeError("network down")

        good_adapter = MagicMock()
        good_adapter.name = "rss"
        good_adapter.fetch.return_value = [
            {"title": "OK", "summary": "x", "url": "https://example.com/ok", "source": "GoodSource", "published": "2026-04-30T08:00:00+00:00"}
        ]

        with patch("ai_news_digest.pipeline.enrich_articles_with_hn", side_effect=lambda articles: articles):
            with patch("ai_news_digest.pipeline._storage.exclude_cross_day_duplicates", side_effect=lambda articles, days: (articles, 0)):
                payload = fetch_digest_inputs(adapters=[bad_adapter, good_adapter])

        assert len(payload["main_articles"]) == 1
        assert payload["main_articles"][0]["title"] == "OK"


class TestAgentSummarizeIntegration:
    def test_agent_mode_raises_when_no_response_file(self, tmp_path):
        from ai_news_digest.llm.service import _agent_summarize

        with patch("ai_news_digest.config.yaml_loader.get_data_dir", return_value=tmp_path):
            with pytest.raises(AgentSummarizationRequired):
                _agent_summarize("prompt text", [], [], weekly=False)

    def test_agent_mode_reads_response_file(self, tmp_path):
        from ai_news_digest.llm.service import _agent_summarize

        response = (
            '{"brief_rundown": "test", "highlights": '
            '[{"headline": "H", "summary": "S", "source": "Src", "url": "https://x"}]}'
        )
        (tmp_path / "agent_response.json").write_text(response, encoding="utf-8")

        with patch("ai_news_digest.config.yaml_loader.get_data_dir", return_value=tmp_path):
            result = _agent_summarize("prompt text", [], [], weekly=False)

        assert isinstance(result, dict)
        assert result["brief_rundown"] == "test"
        assert len(result["highlights"]) == 1

    def test_agent_weekly_mode_reads_response_file(self, tmp_path):
        from ai_news_digest.llm.service import _agent_summarize

        response = (
            '{"executive_summary": "weekly test", "highlights_of_the_week": '
            '[{"headline": "WH", "source": "Src", "url": "https://x"}]}'
        )
        (tmp_path / "agent_response.json").write_text(response, encoding="utf-8")

        with patch("ai_news_digest.config.yaml_loader.get_data_dir", return_value=tmp_path):
            result = _agent_summarize("prompt text", [], [], weekly=True)

        assert isinstance(result, dict)
        assert result["executive_summary"] == "weekly test"
