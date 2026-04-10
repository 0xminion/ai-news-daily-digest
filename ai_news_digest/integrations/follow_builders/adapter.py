from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ai_news_digest.config import get_follow_builders_config
from ai_news_digest.storage.topic_memory import save_follow_builders_state

MANIFEST = {
    'id': 'follow-builders',
    'schema_version': 'v1',
    'source_types': ['x', 'podcasts', 'blogs'],
    'stages': ['summarize', 'assemble', 'translate'],
}


def normalized_items_from_remote_feeds() -> list[dict]:
    cfg = get_follow_builders_config()
    items = []
    for feed in cfg.get('feeds', []):
        source_type = feed.get('source_type', 'unknown')
        for item in feed.get('items', []):
            items.append({
                'integration': 'follow-builders',
                'source_type': source_type,
                'title': item.get('title') or item.get('name') or item.get('headline') or '',
                'summary': item.get('summary') or item.get('content') or '',
                'url': item.get('url') or item.get('link') or '',
                'published': item.get('published') or item.get('published_at') or 'Unknown',
                'source': f"Follow Builders / {source_type}",
                'metadata': item,
            })
    save_follow_builders_state({'manifest': MANIFEST, 'item_count': len(items)})
    return items
