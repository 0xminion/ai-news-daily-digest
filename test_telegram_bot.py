from unittest.mock import MagicMock, patch

from ai_news_digest.output.telegram import _embed_links, _escape, _format_digest, _send_message, send_digest


class TestEscape:
    def test_escapes_angle_brackets(self):
        assert '&lt;' in _escape('<script>')
        assert '&gt;' in _escape('revenue > $30B')


class TestFormatDigest:
    def test_single_message_when_short(self):
        summary = 'BRIEF RUNDOWN:\nShort summary.\n\nHIGHLIGHTS:\n1. Headline\nDetails here.\nSource: Test (https://example.com)'
        messages = _format_digest(summary)
        assert len(messages) == 1
        assert 'AI Daily Digest' in messages[0]

    def test_trend_watch_is_rendered(self):
        summary = (
            'BRIEF RUNDOWN:\nShort summary.\n\n'
            'TREND WATCH:\nMAIN NEWS TREND WATCH:\nHEATING UP:\n- Anthropic — more launches\nCOOLING DOWN:\n- OpenAI — fewer mentions\n\n'
            'HIGHLIGHTS:\n1. Headline\nDetails here.\nSource: Test (https://example.com)'
        )
        messages = _format_digest(summary)
        assert any('Trend Watch' in msg for msg in messages)
        assert any('Anthropic' in msg for msg in messages)

    def test_compact_profile_hides_trends(self):
        summary = (
            'BRIEF RUNDOWN:\nShort summary.\n\n'
            'TREND WATCH:\nHEATING UP:\n- Anthropic — more launches\n\n'
            'HIGHLIGHTS:\n1. Headline\nDetails here.\nSource: Test (https://example.com)'
        )
        messages = _format_digest(summary, profile_name='compact')
        assert not any('Trend Watch' in msg for msg in messages)


class TestSendDigest:
    @patch('ai_news_digest.output.telegram._send_message')
    def test_send_success_to_multiple_destinations(self, mock_send):
        mock_send.return_value = True
        result = send_digest(
            'BRIEF RUNDOWN:\nTest.\n\nHIGHLIGHTS:\n1. Test',
            destinations=[
                {'name': 'one', 'chat_id': '1', 'bot_token': 'a'},
                {'name': 'two', 'chat_id': '2', 'bot_token': 'b', 'profile': 'compact'},
            ],
        )
        assert result is True
        assert mock_send.call_count == 2

    @patch('ai_news_digest.output.telegram._send_message')
    def test_send_failure(self, mock_send):
        mock_send.return_value = False
        result = send_digest('BRIEF RUNDOWN:\nTest.', destinations=[{'name': 'one', 'chat_id': '1', 'bot_token': 'a'}])
        assert result is False


class TestSendMessage:
    @patch('ai_news_digest.output.telegram.requests.post')
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        assert _send_message('Hello', bot_token='abc', chat_id='123') is True

    @patch('ai_news_digest.output.telegram.requests.post')
    def test_retry_on_500(self, mock_post):
        mock_post.side_effect = [MagicMock(status_code=500, text='Server error'), MagicMock(status_code=200)]
        assert _send_message('Hello', bot_token='abc', chat_id='123') is True
        assert mock_post.call_count == 2


    def test_research_bullets_render_without_eli5(self):
        summary = (
            'BRIEF RUNDOWN:\nShort summary.\n\n'
            'HIGHLIGHTS:\n1. Headline\nDetails here.\nSource: Test (https://example.com)\n\n'
            'ALSO WORTH KNOWING:\n- Side item | Test (https://example.com/also)\n\n'
            'RESEARCH / BUILDER SIGNALS:\n- [paper] Paper title | arXiv AI (https://example.com/paper)'
        )
        messages = _format_digest(summary)
        assert any('[paper] Paper title' in msg for msg in messages)


    def test_title_case_headings_and_source_name_links(self):
        summary = (
            'Brief Rundown:\nShort summary.\n\n'
            'Trend Watch:\nMain News Trend Watch:\nHeating Up:\n- OpenAI — more launches\n\n'
            'Highlights:\n1. Headline\nDetails here.\nSource: Test Source (https://example.com)\n\n'
            'Also Worth Knowing:\n- Side item | Side Source (https://example.com/also)'
        )
        messages = _format_digest(summary)
        # Source name is linked (not title, not raw URL)
        assert any('Source: <a href="https://example.com">Test Source</a>' in msg for msg in messages)
        assert any('Side item — <a href="https://example.com/also">Side Source</a>' in msg for msg in messages)
        assert any('Highlights' in msg for msg in messages)


class TestEmbedLinks:
    def test_converts_bare_url_to_embedded_link(self):
        text = 'Check out https://example.com/path for details'
        result = _embed_links(text)
        assert '<a href="https://example.com/path">example.com</a>' in result
        assert 'https://example.com/path' not in result.split('</a>')[1] if '</a>' in result else True

    def test_handles_multiple_urls(self):
        text = 'See https://a.com and https://b.org/page'
        result = _embed_links(text)
        assert '<a href="https://a.com">a.com</a>' in result
        assert '<a href="https://b.org/page">b.org</a>' in result

    def test_strips_www_prefix(self):
        result = _embed_links('Visit https://www.example.com')
        assert '>example.com</a>' in result

    def test_no_urls_unchanged(self):
        text = 'No links here'
        assert _embed_links(text) == text
