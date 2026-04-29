"""Article relevance scoring.

Future: LLM-based or cached-embedding preference scoring.
Current: pass-through with optional keyword boost.
"""
from __future__ import annotations

import logging

from ai_news_digest.config.yaml_loader import cfg_list, get_config_value

logger = logging.getLogger("ai-digest")


def filter_by_relevance(articles: list[dict]) -> list[dict]:
    """Return articles filtered by user preference profile.

    Currently a no-op unless preferences.interests or preferences.avoid are set.
    """
    interests = cfg_list("preferences.interests")
    avoid = cfg_list("preferences.avoid")
    threshold = float(get_config_value("preferences", "threshold") or 0.6)

    if not interests and not avoid:
        return articles

    def _score(a: dict) -> float:
        text = f"{a.get('title', '')} {a.get('text', '')} {a.get('summary', '')}".lower()
        score = 0.5
        for term in interests:
            if term.lower() in text:
                score += 0.15
        for term in avoid:
            if term.lower() in text:
                score -= 0.3
        return score

    filtered = [a for a in articles if _score(a) >= threshold]
    if len(filtered) < len(articles):
        logger.info("Relevance filter dropped %d articles", len(articles) - len(filtered))
    return filtered if filtered else articles
