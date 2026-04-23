from unittest.mock import MagicMock, patch

import pytest
import requests

from ai_news_digest.llm.service import _quiet_day_message, summarize

OLLAMA_SETTINGS = {
    'provider': 'ollama',
    'model': 'minimax-m2.7:cloud',
    'ollama_host': 'http://localhost:11434',
    'timeout': 30,
    'max_tokens': 1000,
    'api_base': '',
    'openai_api_key': '',
    'openrouter_api_key': '',
    'anthropic_api_key': '',
}


class TestSummarize:
    def test_empty_articles_returns_quiet_day(self):
        result = summarize([])
        assert 'Quiet day' in result

    @patch('ai_news_digest.llm.service.get_llm_settings', return_value=OLLAMA_SETTINGS)
    @patch('ai_news_digest.llm.service.requests.post')
    def test_summarize_returns_string(self, mock_post, _mock_settings):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'response': 'BRIEF RUNDOWN:\nAI is evolving.\n\nHIGHLIGHTS:\n1. Test'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        articles = [{'title': 'Test Article', 'summary': 'Test summary about AI', 'url': 'https://example.com/1', 'source': 'Test Source'}]
        result = summarize(articles, trend_snapshot={'heating_up': [{'topic': 'Anthropic'}], 'cooling_down': []})
        assert isinstance(result, str)
        payload = mock_post.call_args.kwargs['json']
        assert 'Trend context:' in payload['prompt']
        assert '[paper]' in payload['prompt']

    @patch('ai_news_digest.llm.service.get_llm_settings', return_value=OLLAMA_SETTINGS)
    @patch('ai_news_digest.llm.service.requests.post')
    def test_summarize_handles_ollama_down(self, mock_post, _mock_settings):
        mock_post.side_effect = requests.ConnectionError('Connection refused')
        with pytest.raises(requests.ConnectionError):
            summarize([{'title': 'Test', 'summary': 'Test', 'url': 'http://x', 'source': 'S'}])

    @patch('ai_news_digest.llm.service.get_llm_settings', return_value=OLLAMA_SETTINGS)
    @patch('ai_news_digest.llm.service.requests.post')
    def test_summarize_handles_empty_response(self, mock_post, _mock_settings):
        mock_response = MagicMock()
        mock_response.json.return_value = {'response': ''}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        with pytest.raises(RuntimeError, match='empty response'):
            summarize([{'title': 'Test', 'summary': 'Test', 'url': 'http://x', 'source': 'S'}])

    @patch('ai_news_digest.llm.service.get_llm_settings', return_value={
        'provider': 'openrouter',
        'model': 'anthropic/claude-sonnet-4',
        'ollama_host': 'http://localhost:11434',
        'timeout': 30,
        'max_tokens': 1000,
        'api_base': '',
        'openai_api_key': '',
        'openrouter_api_key': 'test-key',
        'anthropic_api_key': '',
    })
    @patch('ai_news_digest.llm.service.requests.post')
    def test_summarize_supports_openrouter(self, mock_post, _mock_settings):
        mock_response = MagicMock()
        mock_response.json.return_value = {'choices': [{'message': {'content': 'BRIEF RUNDOWN:\nTest'}}]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        result = summarize([{'title': 'Test', 'summary': 'AI news', 'url': 'http://x', 'source': 'S', 'hn_points': 10}])
        assert 'BRIEF RUNDOWN' in result
        called_headers = mock_post.call_args.kwargs['headers']
        assert called_headers['Authorization'] == 'Bearer test-key'


class TestQuietDayMessage:
    def test_format(self):
        msg = _quiet_day_message()
        assert 'Brief Rundown:' in msg
        assert 'Highlights:' in msg
