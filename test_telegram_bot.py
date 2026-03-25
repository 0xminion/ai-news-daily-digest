from unittest.mock import patch, MagicMock

import pytest

from telegram_bot import _escape, _format_digest, send_digest, _send_message


class TestEscape:
    def test_escapes_angle_brackets(self):
        assert "&lt;" in _escape("<script>")
        assert "&gt;" in _escape("revenue > $30B")

    def test_escapes_ampersand(self):
        assert "&amp;" in _escape("R&D spending")

    def test_plain_text_unchanged(self):
        assert _escape("Hello world") == "Hello world"


class TestFormatDigest:
    def test_single_message_when_short(self):
        summary = "BRIEF RUNDOWN:\nShort summary.\n\nHIGHLIGHTS:\n1. Headline\nDetails here.\nSource: Test - https://example.com"
        messages = _format_digest(summary)
        assert len(messages) == 1
        assert "AI Daily Digest" in messages[0]

    def test_html_in_output(self):
        summary = "BRIEF RUNDOWN:\nSummary.\n\nHIGHLIGHTS:\n1. Test Headline\nDetails.\nSource: Wired - https://wired.com/article"
        messages = _format_digest(summary)
        assert "<b>" in messages[0]

    def test_escapes_html_in_content(self):
        summary = "BRIEF RUNDOWN:\nRevenue > $30B & growing.\n\nHIGHLIGHTS:\n1. NVIDIA's <big> quarter\nDetails.\nSource: Reuters - https://reuters.com/article"
        messages = _format_digest(summary)
        full = " ".join(messages)
        assert "&gt;" in full
        assert "&amp;" in full

    def test_splits_long_message(self):
        long_rundown = "BRIEF RUNDOWN:\n" + "A" * 3000
        long_highlights = "\n\nHIGHLIGHTS:\n" + "B" * 3000
        summary = long_rundown + long_highlights
        messages = _format_digest(summary)
        assert len(messages) == 2
        for msg in messages:
            assert len(msg) <= 4096

    def test_clickable_links(self):
        summary = "BRIEF RUNDOWN:\nSummary.\n\nHIGHLIGHTS:\n1. Test\nDetails.\nSource: Wired - https://wired.com/article"
        messages = _format_digest(summary)
        assert 'href="https://wired.com/article"' in messages[0]

    def test_handles_no_highlights(self):
        summary = "BRIEF RUNDOWN:\nJust a rundown, no highlights section."
        messages = _format_digest(summary)
        assert len(messages) == 1
        assert "AI Daily Digest" in messages[0]

    def test_handles_raw_text(self):
        summary = "Just some plain text without any markers."
        messages = _format_digest(summary)
        assert len(messages) == 1


class TestSendDigest:
    @patch("telegram_bot._send_message")
    def test_send_success(self, mock_send):
        mock_send.return_value = True
        result = send_digest("BRIEF RUNDOWN:\nTest.\n\nHIGHLIGHTS:\n1. Test")
        assert result is True

    @patch("telegram_bot._send_message")
    def test_send_failure(self, mock_send):
        mock_send.return_value = False
        result = send_digest("BRIEF RUNDOWN:\nTest.")
        assert result is False


class TestSendMessage:
    @patch("telegram_bot.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        assert _send_message("Hello") is True

    @patch("telegram_bot.requests.post")
    def test_retry_on_500(self, mock_post):
        mock_post.side_effect = [
            MagicMock(status_code=500, text="Server error"),
            MagicMock(status_code=200),
        ]
        assert _send_message("Hello") is True
        assert mock_post.call_count == 2

    @patch("telegram_bot.requests.post")
    def test_403_no_retry(self, mock_post):
        mock_post.return_value = MagicMock(status_code=403, text="Forbidden")
        assert _send_message("Hello") is False
        assert mock_post.call_count == 1
