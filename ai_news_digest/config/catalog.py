from __future__ import annotations

# Re-export everything from split modules for backward compatibility.
# New code should import directly from the specific module.

from .feeds import (
    RSS_FEEDS as RSS_FEEDS,
    PAGE_SOURCES as PAGE_SOURCES,
    ORTHOGONAL_RSS_FEEDS as ORTHOGONAL_RSS_FEEDS,
    GITHUB_TRENDING_ENABLED as GITHUB_TRENDING_ENABLED,
    GITHUB_TRENDING_SINCE as GITHUB_TRENDING_SINCE,
    GITHUB_TRENDING_LANGUAGE as GITHUB_TRENDING_LANGUAGE,
    GITHUB_TRENDING_TOP_N as GITHUB_TRENDING_TOP_N,
)
from .keywords import matches_ai_keywords as matches_ai_keywords, get_matched_tags as get_matched_tags
from .topics import TREND_TOPICS as TREND_TOPICS, HN_SIGNAL_QUERIES as HN_SIGNAL_QUERIES
from .trust import SOURCE_TRUST_WEIGHTS as SOURCE_TRUST_WEIGHTS
