from unittest.mock import patch

from ai_news_digest.analysis.trends import compute_trend_snapshot, format_trend_context


def test_compute_trend_snapshot_detects_heating():
    history = [
        {
            'saved_at': '2026-04-08T09:00:00+00:00',
            'articles': [
                {'title': 'OpenAI launches X', 'summary': ''},
                {'title': 'Policy hearing on AI', 'summary': ''},
            ],
        },
        {
            'saved_at': '2026-04-09T09:00:00+00:00',
            'articles': [
                {'title': 'OpenAI gets sued', 'summary': ''},
                {'title': 'Policy hearing on AI', 'summary': ''},
            ],
        },
    ]
    current = [
        {'title': 'Anthropic launches Claude upgrade', 'summary': 'Anthropic model news'},
        {'title': 'Anthropic signs big enterprise deal', 'summary': 'Funding and deal momentum'},
    ]

    with patch('ai_news_digest.analysis.trends.load_recent_report_payloads', return_value=history):
        snapshot = compute_trend_snapshot(current, lookback_days=3)

    heating_topics = [item['topic'] for item in snapshot['main_news']['heating_up']]
    assert 'Anthropic' in heating_topics


def test_format_trend_context_handles_empty_snapshot():
    assert format_trend_context({}) == ''
