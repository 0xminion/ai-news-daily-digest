from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from .catalog import HN_SIGNAL_QUERIES, AI_KEYWORDS, PAGE_SOURCES, RSS_FEEDS, ORTHOGONAL_RSS_FEEDS, SOURCE_TRUST_WEIGHTS, TREND_TOPICS

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
REPORT_ARCHIVE_DIR = DATA_DIR / "daily_reports"
WEEKLY_ARCHIVE_DIR = DATA_DIR / "weekly_reports"
STATE_DIR = DATA_DIR / "state"
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
CROSS_DAY_DEDUP_DAYS = int(os.getenv("CROSS_DAY_DEDUP_DAYS", "7"))
TREND_LOOKBACK_DAYS = int(os.getenv("TREND_LOOKBACK_DAYS", "7"))
CLUSTER_SIMILARITY_THRESHOLD = int(os.getenv("CLUSTER_SIMILARITY_THRESHOLD", "90"))

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "minimax-m2.7:cloud")

LLM_PROVIDER = os.getenv("LLM_PROVIDER") or os.getenv("AGENT_PRIMARY_PROVIDER")
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("AGENT_PRIMARY_MODEL") or OLLAMA_MODEL
LLM_API_BASE = os.getenv("LLM_API_BASE", "").rstrip("/")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", str(OLLAMA_TIMEOUT)))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1800"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_DESTINATIONS_JSON = os.getenv("TELEGRAM_DESTINATIONS_JSON", "")

DELIVERY_HOUR = int(os.getenv("DELIVERY_HOUR", "7"))

HN_ENABLED = os.getenv("HN_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
HN_MIN_POINTS = int(os.getenv("HN_MIN_POINTS", "15"))
HN_MIN_COMMENTS = int(os.getenv("HN_MIN_COMMENTS", "5"))
HN_MAX_STORIES = int(os.getenv("HN_MAX_STORIES", "20"))
HN_SIGNAL_WINDOW_HOURS = int(os.getenv("HN_SIGNAL_WINDOW_HOURS", "36"))
ORTHOGONAL_SIGNALS_ENABLED = os.getenv("ORTHOGONAL_SIGNALS_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}

WEEKLY_HIGHLIGHTS_COUNT = int(os.getenv("WEEKLY_HIGHLIGHTS_COUNT", "7"))
WEEKLY_DIRECTIONS_COUNT = int(os.getenv("WEEKLY_DIRECTIONS_COUNT", "4"))
WEEKLY_FOCUS_COUNT = int(os.getenv("WEEKLY_FOCUS_COUNT", "2"))
WEEKLY_QUESTIONS_COUNT = int(os.getenv("WEEKLY_QUESTIONS_COUNT", "6"))
WEEKLY_RESEARCH_SIGNALS_COUNT = int(os.getenv("WEEKLY_RESEARCH_SIGNALS_COUNT", "5"))
WEEKLY_EMERGING_COUNT = int(os.getenv("WEEKLY_EMERGING_COUNT", "3"))

FOLLOW_BUILDERS_ENABLED = os.getenv("FOLLOW_BUILDERS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
FOLLOW_BUILDERS_FEEDS_JSON = os.getenv("FOLLOW_BUILDERS_FEEDS_JSON", "")
FOLLOW_BUILDERS_PROMPT_STYLE = os.getenv("FOLLOW_BUILDERS_PROMPT_STYLE", "builders")
FOLLOW_BUILDERS_SCHEMA_VERSION = os.getenv("FOLLOW_BUILDERS_SCHEMA_VERSION", "v1")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("ai-digest")

MAX_ARTICLES_TO_SUMMARIZE = 20
RESEARCH_SIGNALS_COUNT = int(os.getenv("RESEARCH_SIGNALS_COUNT", "5"))
RESEARCH_TOPIC_CAP_PER_TOPIC = int(os.getenv("RESEARCH_TOPIC_CAP_PER_TOPIC", "1"))
RSS_WINDOW_HOURS = 24
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; AI-News-Digest/2.0; +https://github.com/0xminion/ai-news-daily-digest)")
CONTENT_FETCH_TIMEOUT = int(os.getenv("CONTENT_FETCH_TIMEOUT", "30"))
MIN_ARTICLE_TEXT_LENGTH = int(os.getenv("MIN_ARTICLE_TEXT_LENGTH", "300"))
FULL_CONTENT_FETCH_LIMIT = int(os.getenv("FULL_CONTENT_FETCH_LIMIT", "8"))

for d in (REPORT_ARCHIVE_DIR, WEEKLY_ARCHIVE_DIR, STATE_DIR):
    d.mkdir(parents=True, exist_ok=True)


def get_llm_settings() -> dict:
    provider = (LLM_PROVIDER or "").strip().lower()
    model = (LLM_MODEL or "").strip()
    if not provider and "/" in model:
        p, m = model.split("/", 1)
        if p.lower() in {"ollama", "openai", "openrouter", "anthropic"}:
            provider, model = p.lower(), m
    provider = provider or "ollama"
    model = model or OLLAMA_MODEL
    return {
        "provider": provider,
        "model": model,
        "api_base": LLM_API_BASE,
        "timeout": LLM_TIMEOUT,
        "max_tokens": LLM_MAX_TOKENS,
        "openai_api_key": OPENAI_API_KEY,
        "openrouter_api_key": OPENROUTER_API_KEY,
        "anthropic_api_key": ANTHROPIC_API_KEY,
        "ollama_host": OLLAMA_HOST,
    }


def get_destination_profiles() -> dict:
    return {
        "default": {
            "show_trend_watch": True,
            "show_also_worth_knowing": True,
            "max_highlights": 10,
            "max_also": 10,
            "max_research": RESEARCH_SIGNALS_COUNT,
            "include_signal_annotations": True,
            "headline_prefix": "",
        },
        "compact": {
            "show_trend_watch": False,
            "show_also_worth_knowing": False,
            "max_highlights": 5,
            "max_also": 0,
            "max_research": min(RESEARCH_SIGNALS_COUNT, 3),
            "include_signal_annotations": False,
            "headline_prefix": "⚡ ",
        },
        "research": {
            "show_trend_watch": True,
            "show_also_worth_knowing": True,
            "max_highlights": 12,
            "max_also": 12,
            "max_research": max(RESEARCH_SIGNALS_COUNT, 5),
            "include_signal_annotations": True,
            "headline_prefix": "🔬 ",
        },
    }


def get_telegram_destinations() -> list[dict]:
    destinations = []
    if TELEGRAM_DESTINATIONS_JSON.strip():
        raw = json.loads(TELEGRAM_DESTINATIONS_JSON)
        if not isinstance(raw, list):
            raise ValueError("TELEGRAM_DESTINATIONS_JSON must be a JSON array")
        for idx, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Destination #{idx} must be an object")
            chat_id = str(item.get("chat_id", "")).strip()
            if not chat_id:
                raise ValueError(f"Destination #{idx} is missing chat_id")
            destinations.append({
                "name": item.get("name") or f"destination-{idx}",
                "chat_id": chat_id,
                "bot_token": str(item.get("bot_token", "")).strip() or TELEGRAM_BOT_TOKEN,
                "profile": item.get("profile", "default"),
            })
    else:
        for idx, chat_id in enumerate([p.strip() for p in TELEGRAM_CHAT_ID.split(',') if p.strip()], start=1):
            destinations.append({"name": f"destination-{idx}", "chat_id": chat_id, "bot_token": TELEGRAM_BOT_TOKEN, "profile": "default"})
    return destinations


def get_follow_builders_config() -> dict:
    feeds = []
    if FOLLOW_BUILDERS_FEEDS_JSON.strip():
        try:
            feeds = json.loads(FOLLOW_BUILDERS_FEEDS_JSON)
        except json.JSONDecodeError as exc:
            raise ValueError(f"FOLLOW_BUILDERS_FEEDS_JSON is invalid JSON: {exc}") from exc
    return {
        "enabled": FOLLOW_BUILDERS_ENABLED,
        "schema_version": FOLLOW_BUILDERS_SCHEMA_VERSION,
        "prompt_style": FOLLOW_BUILDERS_PROMPT_STYLE,
        "feeds": feeds,
    }


def validate_config() -> None:
    destinations = get_telegram_destinations()
    if not destinations:
        raise ValueError("Missing Telegram destination configuration. Set TELEGRAM_CHAT_ID or TELEGRAM_DESTINATIONS_JSON.")
    missing_tokens = [dest["name"] for dest in destinations if not dest.get("bot_token")]
    if missing_tokens:
        raise ValueError(f"Missing bot token for destinations: {', '.join(missing_tokens)}.")
    llm = get_llm_settings()
    provider_keys = {
        "openai": ("OPENAI_API_KEY", OPENAI_API_KEY),
        "openrouter": ("OPENROUTER_API_KEY", OPENROUTER_API_KEY),
        "anthropic": ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
    }
    if llm["provider"] in provider_keys and not provider_keys[llm["provider"]][1]:
        raise ValueError(f"LLM provider '{llm['provider']}' requires {provider_keys[llm['provider']][0]} to be set.")
    for collection_name, feeds in (
        ("RSS_FEEDS", RSS_FEEDS),
        ("ORTHOGONAL_RSS_FEEDS", ORTHOGONAL_RSS_FEEDS),
        ("PAGE_SOURCES", [(item['name'], item['url']) for item in PAGE_SOURCES]),
    ):
        for name, url in feeds:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning("%s entry '%s' has invalid URL '%s' — skipping at runtime.", collection_name, name, url)
