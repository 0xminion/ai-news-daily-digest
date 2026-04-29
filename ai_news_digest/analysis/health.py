"""Source health monitoring and circuit breaker.

Tracks consecutive failures and zero-article timeouts per source.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_news_digest.config.yaml_loader import cfg_bool, cfg_int, get_config_value, get_data_dir

logger = logging.getLogger("ai-digest")

_STATE_PATH: Path | None = None
_lock = threading.Lock()


def _state_path() -> Path:
    global _STATE_PATH
    if _STATE_PATH is None:
        _STATE_PATH = get_data_dir() / "state" / "source_health.json"
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _STATE_PATH


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def source_check(source_name: str, success: bool, article_count: int = 0) -> None:
    """Record a fetch result for a source."""
    if not cfg_bool("circuit_breaker.auto_disable"):
        return
    with _lock:
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
    with _lock:
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
