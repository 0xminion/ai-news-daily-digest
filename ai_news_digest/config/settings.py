from __future__ import annotations

"""Backward-compatible settings shim.

All constants are loaded from yaml_loader at import time. New code should
import directly from yaml_loader.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Avoid circular import: yaml_loader only re-exports constants, never imports from config
from .yaml_loader import (
    BASE_DIR,
    cfg_bool,
    cfg_dict,
    cfg_int,
    cfg_list,
    cfg_str,
    ensure_directories,
    get_config_value,
    get_data_dir,
    get_destination_profiles,
    get_follow_builders_config,
    get_llm_settings,
    get_report_archive_dir,
    get_state_dir,
    get_telegram_destinations,
    get_weekly_archive_dir,
    reload_config,
)

# Force config reload when this module is reloaded (e.g., in tests)
reload_config()

# Directories
DATA_DIR = get_data_dir()
REPORT_ARCHIVE_DIR = get_report_archive_dir()
WEEKLY_ARCHIVE_DIR = get_weekly_archive_dir()
STATE_DIR = get_state_dir()

# Archives
RETENTION_DAYS = cfg_int("archive.retention_days")
CROSS_DAY_DEDUP_DAYS = cfg_int("archive.cross_day_dedup_days")
TREND_LOOKBACK_DAYS = cfg_int("archive.trend_lookback_days")

# Clustering
CLUSTER_SIMILARITY_THRESHOLD = cfg_int("clustering.similarity_threshold")

# LLM
OLLAMA_HOST = cfg_str("llm.ollama_host")
OLLAMA_TIMEOUT = cfg_int("llm.timeout")
OLLAMA_MODEL = cfg_str("llm.model")

LLM_PROVIDER = cfg_str("llm.provider")
LLM_MODEL = cfg_str("llm.model")
LLM_API_BASE = cfg_str("llm.api_base").rstrip("/")
LLM_TIMEOUT = cfg_int("llm.timeout")
LLM_MAX_TOKENS = cfg_int("llm.max_tokens")
LLM_CONTEXT_LIMIT = get_config_value("llm", "context_limit") or None

# Secrets
OPENAI_API_KEY = cfg_str("secrets.openai_api_key")
OPENROUTER_API_KEY = cfg_str("secrets.openrouter_api_key")
ANTHROPIC_API_KEY = cfg_str("secrets.anthropic_api_key")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_DESTINATIONS_JSON = os.getenv("TELEGRAM_DESTINATIONS_JSON", "")

OUTPUT_MODE = cfg_str("delivery.output_mode")
DELIVERY_HOUR = cfg_int("delivery.delivery_hour")

# HackerNews
HN_ENABLED = cfg_bool("hn.enabled")
HN_MIN_POINTS = cfg_int("hn.min_points")
HN_MIN_COMMENTS = cfg_int("hn.min_comments")
HN_MAX_STORIES = cfg_int("hn.max_stories")
HN_SIGNAL_WINDOW_HOURS = cfg_int("hn.signal_window_hours")

# Signals
ORTHOGONAL_SIGNALS_ENABLED = cfg_bool("signals.orthogonal_signals_enabled")

# Weekly
WEEKLY_HIGHLIGHTS_COUNT = cfg_int("weekly.highlights_count")
WEEKLY_DIRECTIONS_COUNT = cfg_int("weekly.directions_count")
WEEKLY_FOCUS_COUNT = cfg_int("weekly.focus_count")
WEEKLY_QUESTIONS_COUNT = cfg_int("weekly.questions_count")
WEEKLY_RESEARCH_SIGNALS_COUNT = cfg_int("weekly.research_signals_count")
WEEKLY_EMERGING_COUNT = cfg_int("weekly.emerging_count")

# Follow builders
FOLLOW_BUILDERS_ENABLED = cfg_bool("follow_builders.enabled")
FOLLOW_BUILDERS_FEEDS_JSON = cfg_str("follow_builders.feeds_json")
FOLLOW_BUILDERS_PROMPT_STYLE = cfg_str("follow_builders.prompt_style")
FOLLOW_BUILDERS_SCHEMA_VERSION = cfg_str("follow_builders.schema_version")

# Logging
LOG_LEVEL = cfg_str("log.level")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=cfg_str("log.format"),
        handlers=[logging.StreamHandler()],
    )
logger = logging.getLogger("ai-digest")

# Fetching / pipeline constants
MAX_ARTICLES_TO_SUMMARIZE = cfg_int("fetching.max_articles_to_summarize")
RESEARCH_SIGNALS_COUNT = cfg_int("signals.research_signals_count")
RESEARCH_TOPIC_CAP_PER_TOPIC = cfg_int("signals.research_topic_cap_per_topic")
RSS_WINDOW_HOURS = cfg_int("fetching.rss_window_hours")
USER_AGENT = cfg_str("fetching.user_agent")
CONTENT_FETCH_TIMEOUT = cfg_int("fetching.content_fetch_timeout")
MIN_ARTICLE_TEXT_LENGTH = cfg_int("fetching.min_article_text_length")
FULL_CONTENT_FETCH_LIMIT = cfg_int("fetching.full_content_fetch_limit")

# Observability
OBSERVABILITY_ENABLED = cfg_bool("observability.enabled")

# Embedding
EMBEDDING_MODEL = cfg_str("embedding.model")
EMBEDDING_HOST = cfg_str("embedding.host")
EMBEDDING_THRESHOLD = float(get_config_value("embedding", "similarity_threshold", default=0.85) or 0.85)

# Lazy directory creation
def _ensure_directories():
    ensure_directories()


from .feeds import RSS_FEEDS, PAGE_SOURCES, ORTHOGONAL_RSS_FEEDS
from .keywords import matches_ai_keywords, get_matched_tags
from .topics import TREND_TOPICS, HN_SIGNAL_QUERIES, RESEARCH_SIGNAL_SOURCES
from .trust import SOURCE_TRUST_WEIGHTS
from .validate import validate_config

# Ranking — re-export constant (kept in a separate dict now)
SOURCE_TRUST_WEIGHTS = cfg_dict("ranking.source_trust_weights") or SOURCE_TRUST_WEIGHTS
