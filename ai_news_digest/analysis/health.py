"""Source health monitoring and circuit breaker.

Tracks consecutive failures and zero-article timeouts per source in SQLite.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from ai_news_digest.config.yaml_loader import cfg_bool, cfg_int

logger = logging.getLogger("ai-digest")

_db_lock = threading.RLock()


def _ensure_source_health_table() -> None:
    from ai_news_digest.storage.sqlite_store import _conn, _ensure_schema
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_health (
                    source_name TEXT PRIMARY KEY,
                    consecutive_failures INTEGER DEFAULT 0,
                    last_success TEXT,
                    last_failure TEXT,
                    last_article_count INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()


def _load_state() -> dict[str, Any]:
    """Load source health state from SQLite."""
    _ensure_source_health_table()
    from ai_news_digest.storage.sqlite_store import _conn
    with _db_lock:
        with _conn() as conn:
            rows = conn.execute("SELECT * FROM source_health").fetchall()
    return {row["source_name"]: dict(row) for row in rows}


def _save_state(state: dict) -> None:
    from ai_news_digest.storage.sqlite_store import _conn
    with _db_lock:
        with _conn() as conn:
            for source_name, rec in state.items():
                conn.execute(
                    """INSERT INTO source_health
                       (source_name, consecutive_failures, last_success, last_failure, last_article_count)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(source_name) DO UPDATE SET
                       consecutive_failures=excluded.consecutive_failures,
                       last_success=excluded.last_success,
                       last_failure=excluded.last_failure,
                       last_article_count=excluded.last_article_count""",
                    (
                        source_name,
                        rec.get("consecutive_failures", 0),
                        rec.get("last_success"),
                        rec.get("last_failure"),
                        rec.get("last_article_count", 0),
                    ),
                )
            conn.commit()


def source_check(source_name: str, success: bool, article_count: int = 0) -> None:
    """Record a fetch result for a source."""
    if not cfg_bool("circuit_breaker.auto_disable"):
        return
    with _db_lock:
        state = _load_state()
        rec = state.get(source_name, {})
        if success and article_count > 0:
            rec["consecutive_failures"] = 0
            rec["last_success"] = datetime.now(timezone.utc).isoformat()
            rec["last_article_count"] = article_count
        else:
            rec["consecutive_failures"] = rec.get("consecutive_failures", 0) + 1
            rec["last_failure"] = datetime.now(timezone.utc).isoformat()
        state[source_name] = rec
        _save_state(state)


def filter_disabled_sources(feeds: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return feeds that are not currently tripped by the circuit breaker."""
    if not cfg_bool("circuit_breaker.auto_disable"):
        return feeds
    threshold = cfg_int("circuit_breaker.consecutive_failure_threshold")
    zero_timeout_hours = cfg_int("circuit_breaker.zero_articles_timeout_hours")
    with _db_lock:
        state = _load_state()
    active = []
    for name, url in feeds:
        rec = state.get(name, {})
        fails = rec.get("consecutive_failures", 0)
        if fails >= threshold:
            logger.warning("Circuit breaker: source '%s' disabled (%d consecutive failures)", name, fails)
            continue
        last_article_count = rec.get("last_article_count", 1)
        last_success = rec.get("last_success")
        if last_article_count == 0 and last_success:
            try:
                last_dt = datetime.fromisoformat(last_success)
                hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                if hours_since < zero_timeout_hours:
                    logger.warning("Circuit breaker: source '%s' zero-article timeout (%dh)", name, zero_timeout_hours)
                    continue
            except Exception:
                pass
        active.append((name, url))
    return active
