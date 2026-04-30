"""Unified storage facade.

Collapses file-based JSON archives, SQLite state/FTS, and topic memory
into a single interface so callers do not need to know which backend
handles which concern.
"""
from __future__ import annotations

from ai_news_digest.config import RETENTION_DAYS
from ai_news_digest.storage import archive
from ai_news_digest.storage import sqlite_store


class UnifiedStorage:
    """Single entry point for all persistence operations."""

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def start_run(self) -> str:
        return sqlite_store.start_run()

    def end_run(self, run_id: str, status: str = "success") -> None:
        sqlite_store.end_run(run_id, status)

    # ------------------------------------------------------------------
    # Topic memory
    # ------------------------------------------------------------------

    def load_topic_memory(self) -> dict:
        return sqlite_store.load_topic_memory()

    def save_topic_memory(self, run_id: str, snapshot: dict) -> None:
        sqlite_store.save_topic_memory(run_id, snapshot)

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def record_entities(self, run_id: str, entities: list[dict]) -> None:
        sqlite_store.record_entities(run_id, entities)

    def get_entity_trends(self, min_mention_count: int = 2, lookback_runs: int = 5) -> list[dict]:
        return sqlite_store.get_entity_trends(min_mention_count, lookback_runs)

    # ------------------------------------------------------------------
    # Archives (file + SQLite)
    # ------------------------------------------------------------------

    def save_daily_report(
        self,
        summary: str,
        articles: list[dict],
        trends: dict | None = None,
        clusters: list[dict] | None = None,
    ) -> dict[str, str]:
        return archive.save_daily_report(summary, articles, trends=trends, clusters=clusters)

    def save_weekly_report(self, payload: dict, text: str) -> dict[str, str]:
        return archive.save_weekly_report(payload, text)

    def load_recent_report_payloads(self, days: int, include_today: bool = False) -> list[dict]:
        return archive.load_recent_report_payloads(days, include_today=include_today)

    def prune_old_reports(self, retention_days: int | None = None) -> list[str]:
        return archive.prune_old_reports(retention_days or RETENTION_DAYS)

    # ------------------------------------------------------------------
    # Dedup
    # ------------------------------------------------------------------

    def exclude_cross_day_duplicates(
        self, articles: list[dict], days: int | None = None
    ) -> tuple[list[dict], int]:
        from ai_news_digest.config import CROSS_DAY_DEDUP_DAYS
        return archive.exclude_cross_day_duplicates(articles, days or CROSS_DAY_DEDUP_DAYS)

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def migrate(self) -> None:
        from ai_news_digest.config import STATE_DIR
        sqlite_store.migrate_from_json(STATE_DIR)


# Module-level singleton for convenience.
storage = UnifiedStorage()
