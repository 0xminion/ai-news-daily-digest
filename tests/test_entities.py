"""Tests for entity extraction and trend building."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_news_digest.analysis.entities import (
    build_entity_trend_section,
    extract_and_record_entities,
)
from ai_news_digest.storage.sqlite_store import record_entities


@pytest.fixture(autouse=True)
def _reset_entities(tmp_path):
    """Wipe entities table before each test."""
    from ai_news_digest.storage.sqlite_store import _conn, _ensure_schema

    _ensure_schema()
    with _conn() as conn:
        conn.execute("DELETE FROM entities")
        conn.execute("DELETE FROM runs")
        conn.commit()
    yield


class TestExtractAndRecordEntities:
    def test_llm_extraction_persists_to_sqlite(self):
        mock_llm_response = '[{"name": "OpenAI", "type": "org"}, {"name": "Sam Altman", "type": "person"}]'

        with patch("ai_news_digest.llm.service._ollama", return_value=mock_llm_response):
            with patch("ai_news_digest.analysis.entities.get_llm_settings", return_value={"provider": "ollama", "model": "test", "max_tokens": 100}):
                entities = extract_and_record_entities("run-123", "OpenAI and Sam Altman news")

        assert len(entities) == 2
        assert entities[0]["name"] == "OpenAI"

    def test_malformed_llm_response_returns_empty(self):
        with patch("ai_news_digest.llm.service._ollama", return_value="not json"):
            with patch("ai_news_digest.analysis.entities.get_llm_settings", return_value={"provider": "ollama", "model": "test", "max_tokens": 100}):
                entities = extract_and_record_entities("run-456", "Some text")

        assert entities == []

    def test_unsupported_provider_returns_empty(self):
        with patch("ai_news_digest.analysis.entities.get_llm_settings", return_value={"provider": "agent", "model": "test", "max_tokens": 100}):
            entities = extract_and_record_entities("run-789", "Some text")
        assert entities == []


class TestBuildEntityTrendSection:
    def test_empty_trends_returns_empty_string(self):
        section = build_entity_trend_section()
        assert section == ""

    def test_trend_section_formatting(self):
        # Seed some entities
        record_entities("run-aaa", [
            {"name": "OpenAI", "type": "org"},
            {"name": "OpenAI", "type": "org"},
            {"name": "DeepMind", "type": "org"},
            {"name": "DeepMind", "type": "org"},
        ])
        # Seed a run so the entity query has something to join on
        from ai_news_digest.storage.sqlite_store import _conn
        with _conn() as conn:
            conn.execute("INSERT INTO runs (run_id, started_at, status) VALUES (?, ?, ?)", ("run-aaa", "2026-04-30T00:00:00+00:00", "success"))
            conn.commit()

        section = build_entity_trend_section(lookback_runs=5)
        assert "OpenAI" in section
        assert "DeepMind" in section
        assert "org" in section
