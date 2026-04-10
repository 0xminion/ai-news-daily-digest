from __future__ import annotations

# Re-export everything from split modules for backward compatibility.
# New code should import directly from the specific module.

from .feeds import RSS_FEEDS, PAGE_SOURCES, ORTHOGONAL_RSS_FEEDS, GITHUB_TRENDING_ENABLED, GITHUB_TRENDING_SINCE, GITHUB_TRENDING_LANGUAGE, GITHUB_TRENDING_TOP_N
from .keywords import matches_ai_keywords, get_matched_tags
from .topics import TREND_TOPICS, HN_SIGNAL_QUERIES
from .trust import SOURCE_TRUST_WEIGHTS
