import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
REPORT_ARCHIVE_DIR = DATA_DIR / "daily_reports"
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))

# Legacy Ollama settings remain supported
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "minimax-m2.7:cloud")

# Generic LLM settings. Explicit LLM_* wins. Otherwise inherit agent defaults.
LLM_PROVIDER = os.getenv("LLM_PROVIDER") or os.getenv("AGENT_PRIMARY_PROVIDER")
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("AGENT_PRIMARY_MODEL") or OLLAMA_MODEL
LLM_API_BASE = os.getenv("LLM_API_BASE", "").rstrip("/")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", str(OLLAMA_TIMEOUT)))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1800"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Delivery
DELIVERY_HOUR = int(os.getenv("DELIVERY_HOUR", "7"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("ai-digest")

# RSS Sources
RSS_FEEDS = [
    ("Wired", "https://www.wired.com/feed/rss"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
    (
        "Reuters",
        "https://www.rss-bridge.org/bridge01/?action=display&bridge=FilterBridge&url=https%3A%2F%2Fwww.reuters.com%2Ftechnology%2F&filter=&filter_type=permit&format=Atom",
    ),
    ("VentureBeat", "https://venturebeat.com/feed/"),
]

# Non-RSS page sources that need custom extraction
PAGE_SOURCES = [
    {
        "name": "Fortune",
        "url": "https://fortune.com/section/artificial-intelligence/",
        "extractor": "fortune_ai",
    },
]

# Keywords for AI relevance filtering
AI_KEYWORDS = [
    "artificial intelligence", "ai ", " ai,", " ai.", "machine learning",
    "deep learning", "neural network", "large language model", "llm",
    "generative ai", "gen ai", "chatbot", "natural language processing",
    "computer vision", "reinforcement learning", "transformer model",
    "gpt", "chatgpt", "copilot", "midjourney", "stable diffusion",
    "diffusion model", "openai", "anthropic", "deepmind", "google ai",
    "meta ai", "nvidia", "hugging face", "huggingface", "mistral ai",
    "mistral", "cohere", "inflection", "perplexity", "claude", "gemini",
    "llama", "groq", "xai", "grok",
]

MAX_ARTICLES_TO_SUMMARIZE = 20
RSS_WINDOW_HOURS = 24
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; AI-News-Digest/1.1; +https://github.com/0xminion/ai-news-daily-digest)",
)
CONTENT_FETCH_TIMEOUT = int(os.getenv("CONTENT_FETCH_TIMEOUT", "30"))
MIN_ARTICLE_TEXT_LENGTH = int(os.getenv("MIN_ARTICLE_TEXT_LENGTH", "300"))
FULL_CONTENT_FETCH_LIMIT = int(os.getenv("FULL_CONTENT_FETCH_LIMIT", "8"))


def get_llm_settings() -> dict:
    provider = (LLM_PROVIDER or "").strip().lower()
    model = (LLM_MODEL or "").strip()

    if not provider and "/" in model:
        possible_provider, possible_model = model.split("/", 1)
        if possible_provider.lower() in {"ollama", "openai", "openrouter", "anthropic"}:
            provider = possible_provider.lower()
            model = possible_model

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


def validate_config():
    """Validate that all required config values are set and sane."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in the values."
        )

    llm = get_llm_settings()
    provider = llm["provider"]
    provider_keys = {
        "openai": ("OPENAI_API_KEY", OPENAI_API_KEY),
        "openrouter": ("OPENROUTER_API_KEY", OPENROUTER_API_KEY),
        "anthropic": ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
    }
    if provider in provider_keys:
        key_name, key_value = provider_keys[provider]
        if not key_value:
            raise ValueError(
                f"LLM provider '{provider}' requires {key_name} to be set."
            )

    for collection_name, feeds in (("RSS_FEEDS", RSS_FEEDS), ("PAGE_SOURCES", [(item["name"], item["url"]) for item in PAGE_SOURCES])):
        for name, url in feeds:
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    logger.warning(
                        "%s entry '%s' has invalid URL '%s' — skipping at runtime.",
                        collection_name,
                        name,
                        url,
                    )
            except Exception as e:
                logger.warning("%s entry '%s' raised %s: %s — skipping at runtime.", collection_name, name, type(e).__name__, e)

    REPORT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
