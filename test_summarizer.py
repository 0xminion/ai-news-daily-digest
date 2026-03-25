from unittest.mock import patch, MagicMock

import pytest
import requests

from summarizer import summarize, _quiet_day_message


class TestSummarize:
    def test_empty_articles_returns_quiet_day(self):
        result = summarize([])
        assert "Quiet day" in result

    @patch("summarizer.requests.post")
    def test_summarize_returns_string(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "BRIEF RUNDOWN:\nAI is evolving.\n\nHIGHLIGHTS:\n1. Test"
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        articles = [
            {
                "title": "Test Article",
                "summary": "Test summary about AI",
                "url": "https://example.com/1",
                "source": "Test Source",
            }
        ]
        result = summarize(articles)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("summarizer.requests.post")
    def test_summarize_handles_ollama_down(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("Connection refused")
        articles = [{"title": "Test", "summary": "Test", "url": "http://x", "source": "S"}]
        with pytest.raises(requests.ConnectionError):
            summarize(articles)

    @patch("summarizer.requests.post")
    def test_summarize_handles_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout("Timed out")
        articles = [{"title": "Test", "summary": "Test", "url": "http://x", "source": "S"}]
        with pytest.raises(requests.Timeout):
            summarize(articles)

    @patch("summarizer.requests.post")
    def test_summarize_handles_empty_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": ""}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        articles = [{"title": "Test", "summary": "Test", "url": "http://x", "source": "S"}]
        with pytest.raises(RuntimeError, match="empty response"):
            summarize(articles)

    @patch("summarizer.requests.post")
    def test_summarize_caps_articles(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Summary text"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        articles = [
            {"title": f"Article {i}", "summary": "AI news", "url": f"http://x/{i}", "source": "S"}
            for i in range(25)
        ]
        # Should not crash with >20 articles (they're capped in fetcher, but summarizer handles gracefully)
        summarize(articles)
        # Verify the call was made
        mock_post.assert_called_once()


class TestQuietDayMessage:
    def test_format(self):
        msg = _quiet_day_message()
        assert "BRIEF RUNDOWN:" in msg
        assert "HIGHLIGHTS:" in msg
        assert "Quiet day" in msg
