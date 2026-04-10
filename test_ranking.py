from ai_news_digest.analysis.ranking import score_article_with_reasons


def test_score_article_uses_split_main_news_trends():
    article = {
        'title': 'Anthropic launches Claude upgrade',
        'summary': 'Anthropic expands enterprise AI usage',
        'source': 'Reuters',
    }
    score = score_article_with_reasons(
        article,
        trend_snapshot={
            'main_news': {'heating_up': [{'topic': 'Anthropic'}], 'cooling_down': []},
            'research_builder': {'heating_up': [], 'cooling_down': []},
        },
        topic_memory={'history': [{'topic_counts': {'Anthropic': 2}}]},
    )
    assert score['score'] > 0
    assert any('heating-up topic' in reason for reason in score['reasons'])


def test_score_article_uses_split_research_trends():
    article = {
        'title': 'New benchmark paper studies hallucination loops',
        'summary': 'Research benchmark for chatbots',
        'source': 'arXiv AI',
    }
    score = score_article_with_reasons(
        article,
        trend_snapshot={
            'main_news': {'heating_up': [], 'cooling_down': []},
            'research_builder': {'heating_up': [{'topic': 'Research / Papers'}], 'cooling_down': []},
        },
        topic_memory=None,
    )
    assert score['components']['trend_bonus'] > 0
    assert any('heating-up topic' in reason for reason in score['reasons'])
