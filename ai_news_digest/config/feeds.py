from __future__ import annotations

"""Load feed configuration from YAML. No hardcoded feeds remain."""
from ai_news_digest.config.yaml_loader import get_config


def _load_feeds(key: str) -> list[tuple[str, str]]:
    cfg = get_config()
    raw = cfg.get(key, [])
    feeds: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            name = item.get("name", "")
            url = item.get("url", "")
            if name and url:
                feeds.append((name, url))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            feeds.append((item[0], item[1]))
    return feeds


def _load_simple(key: str, default: Any):
    return get_config().get(key, default)


from typing import Any

RSS_FEEDS = _load_feeds("rss_feeds")
PAGE_SOURCES = _load_feeds("page_sources")
ORTHOGONAL_RSS_FEEDS = _load_feeds("orthogonal_rss_feeds")

_GITHUB = get_config().get("github_trending", {})
GITHUB_TRENDING_ENABLED = bool(_GITHUB.get("enabled", True))
GITHUB_TRENDING_SINCE = str(_GITHUB.get("since", "daily"))
GITHUB_TRENDING_LANGUAGE = str(_GITHUB.get("language", ""))
GITHUB_TRENDING_TOP_N = int(_GITHUB.get("top_n", 3))
