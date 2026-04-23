from unittest.mock import patch

from ai_news_digest.analysis.weekly import build_weekly_highlights_payload, render_weekly_highlights


def test_render_weekly_highlights_includes_confidence_and_subtypes():
    payload = {
        'executive_summary': 'Summary',
        'highlights_of_the_week': [
            {
                'headline': 'Headline',
                'why_it_matters': 'Why',
                'eli5': 'ELI5: simple',
                'source': 'Fortune',
                'url': 'https://example.com',
                'confidence': 'High confidence',
            }
        ],
        'trending_directions': [{'topic': 'AI Agents', 'direction': 'rising', 'confidence': 'Medium confidence', 'note': 'Supported by 2 cluster(s) this week.'}],
        'research_focus': [{'topic': 'AI Agents', 'confidence': 'High confidence', 'why_now': 'Because', 'what_to_watch': 'Watch'}],
        'research_builder_signals': [{'headline': 'Paper', 'source': 'arXiv AI', 'subtype': 'paper', 'confidence': 'Early signal', 'eli5': 'ELI5: paper'}],
        'missed_but_emerging': [{'headline': 'Small thing', 'source': 'Semafor', 'subtype': 'builder feed', 'confidence': 'Early signal', 'eli5': 'ELI5: small'}],
        'thinking_prompts': ['What next?'],
    }
    text = render_weekly_highlights(payload)
    assert 'Confidence: High confidence' in text
    assert '[paper]' in text
    assert '<a href="https://example.com">Headline</a>' in text
    assert '[builder feed]' in text
    assert '<b>Highlights of the Week</b>' in text
    assert '<b>Question Prompts</b>' in text


def test_weekly_fallback_keeps_github_trending_in_research_signals():
    payloads = [{
        'saved_at': '2026-04-22T00:00:00+00:00',
        'articles': [
            {'title': 'cool repo', 'source': 'GitHub Trending', 'url': 'https://github.com/x/y', 'summary': 'AI tool repo'},
            {'title': 'main story', 'source': 'TechCrunch', 'url': 'https://example.com/story', 'summary': 'OpenAI update'},
        ],
    }]
    with patch('ai_news_digest.analysis.weekly.load_recent_report_payloads', return_value=payloads), \
         patch('ai_news_digest.analysis.weekly.summarize_weekly', side_effect=RuntimeError('force deterministic')):
        out = build_weekly_highlights_payload(days=7)
    assert [item['source'] for item in out['highlights_of_the_week']] == ['TechCrunch']
    assert [item['source'] for item in out['research_builder_signals']] == ['GitHub Trending']
