from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_news_digest.config import STATE_DIR

TOPIC_MEMORY_PATH = STATE_DIR / 'topic_memory.json'
FOLLOW_BUILDERS_STATE_PATH = STATE_DIR / 'follow_builders_state.json'


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
    current = load_topic_memory()
    history = current.get('history', [])
    history.append(snapshot)
    current['history'] = history[-60:]
    TOPIC_MEMORY_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding='utf-8')


def save_follow_builders_state(payload: dict) -> None:
    wrapper = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'payload': payload,
    }
    FOLLOW_BUILDERS_STATE_PATH.write_text(json.dumps(wrapper, indent=2, ensure_ascii=False), encoding='utf-8')


def load_follow_builders_state() -> dict:
    return _load_json(FOLLOW_BUILDERS_STATE_PATH, {'payload': {}})
