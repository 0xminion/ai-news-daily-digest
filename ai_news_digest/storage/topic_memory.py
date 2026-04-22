from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_news_digest.config import STATE_DIR, _ensure_directories

TOPIC_MEMORY_PATH = STATE_DIR / 'topic_memory.json'
FOLLOW_BUILDERS_STATE_PATH = STATE_DIR / 'follow_builders_state.json'


def _lock_file(f, exclusive: bool = True):
    """Acquire an advisory file lock. Falls back to no-op on Windows or if fcntl is unavailable."""
    try:
        import fcntl
        lock_op = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(f, lock_op)
        return True
    except (ImportError, OSError, AttributeError):
        return False


def _unlock_file(f, acquired: bool):
    """Release advisory file lock. Safe to call even if locking was unsupported."""
    if acquired:
        try:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_UN)
        except (ImportError, OSError, AttributeError):
            pass


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def load_topic_memory() -> dict:
    return _load_json(TOPIC_MEMORY_PATH, {'history': []})


def save_topic_memory(snapshot: dict) -> None:
    _ensure_directories()
    TOPIC_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Create file if it does not exist so r+ succeeds
    if not TOPIC_MEMORY_PATH.exists():
        TOPIC_MEMORY_PATH.write_text(json.dumps({'history': []}, indent=2, ensure_ascii=False), encoding='utf-8')
    with TOPIC_MEMORY_PATH.open('r+') as f:
        locked = _lock_file(f, exclusive=True)
        try:
            raw = f.read()
            current = json.loads(raw) if raw else {'history': []}
            history = current.get('history', [])
            history.append(snapshot)
            current['history'] = history[-60:]
            f.seek(0)
            f.truncate()
            f.write(json.dumps(current, indent=2, ensure_ascii=False))
        finally:
            _unlock_file(f, locked)


def save_follow_builders_state(payload: dict) -> None:
    _ensure_directories()
    FOLLOW_BUILDERS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FOLLOW_BUILDERS_STATE_PATH.open('w') as f:
        locked = _lock_file(f, exclusive=True)
        try:
            wrapper = {
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'payload': payload,
            }
            f.write(json.dumps(wrapper, indent=2, ensure_ascii=False))
        finally:
            _unlock_file(f, locked)


def load_follow_builders_state() -> dict:
    return _load_json(FOLLOW_BUILDERS_STATE_PATH, {'payload': {}})
