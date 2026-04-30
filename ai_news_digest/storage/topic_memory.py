"""Backward-compatible shim over sqlite_store."""
from __future__ import annotations
from ai_news_digest.storage.sqlite_store import load_topic_memory, save_topic_memory

__all__ = ["load_topic_memory", "save_topic_memory", "_lock_file", "_unlock_file"]


def _lock_file(f, exclusive: bool = True):
    """No-op shim — locking is handled by SQLite."""
    return False


def _unlock_file(f, acquired: bool):
    """No-op shim — locking is handled by SQLite."""
    pass
