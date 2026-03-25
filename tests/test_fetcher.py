"""Tests for fetcher."""

from test.fetcher import is_ai_related


def test_is_ai_related_true():
    assert is_ai_related("OpenAI releases GPT-5", "A new language model")


def test_is_ai_related_false():
    assert not is_ai_related("Local bakery wins award", "Best bread in town")


def test_is_ai_related_case_insensitive():
    assert is_ai_related("AI BREAKTHROUGH", "Machine learning study")