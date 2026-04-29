from __future__ import annotations

from .catalog import (
    RSS_FEEDS, PAGE_SOURCES, ORTHOGONAL_RSS_FEEDS,
    GITHUB_TRENDING_ENABLED, GITHUB_TRENDING_SINCE, GITHUB_TRENDING_LANGUAGE, GITHUB_TRENDING_TOP_N,
    matches_ai_keywords, get_matched_tags,
    TREND_TOPICS, HN_SIGNAL_QUERIES,
    SOURCE_TRUST_WEIGHTS,
)
from .settings import (
    BASE_DIR, DATA_DIR, REPORT_ARCHIVE_DIR, WEEKLY_ARCHIVE_DIR, STATE_DIR,
    RETENTION_DAYS, CROSS_DAY_DEDUP_DAYS, TREND_LOOKBACK_DAYS, CLUSTER_SIMILARITY_THRESHOLD,
    OLLAMA_HOST, OLLAMA_TIMEOUT, OLLAMA_MODEL,
    LLM_PROVIDER, LLM_MODEL, LLM_API_BASE, LLM_TIMEOUT, LLM_MAX_TOKENS,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_DESTINATIONS_JSON, OUTPUT_MODE,
    HN_ENABLED, HN_MIN_POINTS, HN_MIN_COMMENTS, HN_MAX_STORIES, HN_SIGNAL_WINDOW_HOURS,
    ORTHOGONAL_SIGNALS_ENABLED,
    WEEKLY_HIGHLIGHTS_COUNT, WEEKLY_DIRECTIONS_COUNT, WEEKLY_FOCUS_COUNT,
    WEEKLY_QUESTIONS_COUNT, WEEKLY_RESEARCH_SIGNALS_COUNT, WEEKLY_EMERGING_COUNT,
    FOLLOW_BUILDERS_ENABLED, FOLLOW_BUILDERS_FEEDS_JSON, FOLLOW_BUILDERS_PROMPT_STYLE,
    FOLLOW_BUILDERS_SCHEMA_VERSION,
    LOG_LEVEL, logger,
    MAX_ARTICLES_TO_SUMMARIZE, RESEARCH_SIGNALS_COUNT, RESEARCH_TOPIC_CAP_PER_TOPIC,
    RSS_WINDOW_HOURS, USER_AGENT, CONTENT_FETCH_TIMEOUT, MIN_ARTICLE_TEXT_LENGTH,
    FULL_CONTENT_FETCH_LIMIT, DELIVERY_HOUR,
    get_llm_settings, get_destination_profiles, get_telegram_destinations,
    get_follow_builders_config, validate_config, _ensure_directories,
)
from .yaml_loader import (
    get_config,
    get_config_value,
    cfg_bool,
    cfg_dict,
    cfg_int,
    cfg_list,
    cfg_str,
    ensure_directories,
)

# New public API: run_id-based state
from ai_news_digest.storage.sqlite_store import (
    start_run,
    end_run,
    load_topic_memory,
    save_topic_memory,
    load_follow_builders_state,
    save_follow_builders_state,
    migrate_from_json,
)
# Lazy migration on first import — only once per process
import threading
_migration_done = False
_migration_lock = threading.Lock()

def _lazy_migrate():
    global _migration_done
    if _migration_done:
        return
    with _migration_lock:
        if _migration_done:
            return
        try:
            migrate_from_json(STATE_DIR)
        except Exception:
            pass
        _migration_done = True
_lazy_migrate()
