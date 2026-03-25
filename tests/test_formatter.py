"""Tests for digest formatter."""

from test.formatter import format_digest, _generate_rundown, _generate_highlights


def test_generate_highlights_with_articles():
    articles = [
        {
            "title": "OpenAI announces GPT-5 breakthrough",
            "link": "https://example.com/article1",
            "source": "TechCrunch",
            "published": "2026-03-25T10:00:00+00:00",
        },
        {
            "title": "EU passes new AI regulation law",
            "link": "https://example.com/article2",
            "source": "Reuters",
            "published": "2026-03-25T09:00:00+00:00",
        },
    ]
    result = _generate_highlights(articles)
    assert "1." in result
    assert "OpenAI announces GPT-5 breakthrough" in result
    assert "https://example.com/article1" in result


def test_generate_highlights_empty():
    result = _generate_highlights([])
    assert "No articles" in result


def test_generate_rundown_empty():
    result = _generate_rundown([])
    assert "No significant" in result


def test_format_digest_empty():
    result = format_digest([])
    assert "No significant" in result