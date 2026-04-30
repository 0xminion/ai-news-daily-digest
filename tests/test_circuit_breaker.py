"""Tests for circuit breaker behavior in analysis/health.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_news_digest.analysis.health import filter_disabled_sources, source_check


@pytest.fixture(autouse=True)
def _reset_health_state(tmp_path):
    """Wipe the source_health table before each test."""
    from ai_news_digest.analysis.health import _ensure_source_health_table
    from ai_news_digest.storage.sqlite_store import _conn

    _ensure_source_health_table()
    with _conn() as conn:
        conn.execute("DELETE FROM source_health")
        conn.commit()
    yield


class TestSourceCheck:
    def test_success_clears_consecutive_failures(self):
        source_check("TestSource", success=True, article_count=5)
        active = filter_disabled_sources([("TestSource", "https://example.com/feed")])
        assert len(active) == 1

    def test_failure_increments_consecutive_failures(self):
        source_check("FailSource", success=False, article_count=0)
        source_check("FailSource", success=False, article_count=0)
        source_check("FailSource", success=False, article_count=0)
        active = filter_disabled_sources([("FailSource", "https://example.com/feed")])
        assert len(active) == 0

    def test_success_after_failure_resets(self):
        source_check("RecoverSource", success=False, article_count=0)
        source_check("RecoverSource", success=False, article_count=0)
        source_check("RecoverSource", success=True, article_count=3)
        active = filter_disabled_sources([("RecoverSource", "https://example.com/feed")])
        assert len(active) == 1

    def test_mixed_sources(self):
        source_check("Good", success=True, article_count=5)
        source_check("Bad", success=False, article_count=0)
        source_check("Bad", success=False, article_count=0)
        source_check("Bad", success=False, article_count=0)

        feeds = [
            ("Good", "https://good.com/feed"),
            ("Bad", "https://bad.com/feed"),
        ]
        active = filter_disabled_sources(feeds)
        assert len(active) == 1
        assert active[0][0] == "Good"


class TestFilterDisabledSources:
    def test_circuit_breaker_disabled_returns_all(self):
        with patch("ai_news_digest.analysis.health.cfg_bool", return_value=False):
            feeds = [("A", "url1"), ("B", "url2")]
            assert filter_disabled_sources(feeds) == feeds

    def test_threshold_respected(self):
        # Default threshold is 3 in config
        for _ in range(3):
            source_check("Tripped", success=False, article_count=0)

        feeds = [("Tripped", "https://example.com/feed")]
        active = filter_disabled_sources(feeds)
        assert len(active) == 0

    def test_unknown_source_is_allowed(self):
        feeds = [("NewSource", "https://example.com/feed")]
        active = filter_disabled_sources(feeds)
        assert len(active) == 1
