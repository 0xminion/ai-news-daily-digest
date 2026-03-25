import os
import logging

from dotenv import load_dotenv

load_dotenv()

# Ollama
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "minimax-m2.7:cloud")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = 120  # seconds

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
    ("Reuters", "https://www.rss-bridge.org/bridge01/?action=display&bridge=FilterBridge&url=https%3A%2F%2Fwww.reuters.com%2Ftechnology%2F&filter=&filter_type=permit&format=Atom"),
    ("VentureBeat", "https://venturebeat.com/feed/"),
]

# Keywords for AI relevance filtering
AI_KEYWORDS = [
    # General terms
    "artificial intelligence", "ai ", " ai,", " ai.", "machine learning",
    "deep learning", "neural network", "large language model", "llm",
    "generative ai", "gen ai", "chatbot", "natural language processing",
    "computer vision", "reinforcement learning", "transformer model",
    # Specific technologies
    "gpt", "chatgpt", "copilot", "midjourney", "stable diffusion",
    "diffusion model",
    # Company/entity names
    "openai", "anthropic", "deepmind", "google ai", "meta ai",
    "nvidia", "hugging face", "huggingface", "mistral ai", "mistral",
    "cohere", "inflection", "perplexity", "claude", "gemini",
    "llama", "groq", "xai", "grok",
]

MAX_ARTICLES_TO_SUMMARIZE = 20
RSS_WINDOW_HOURS = 27  # 24h + 3h buffer for timezone edge cases
USER_AGENT = "AI-News-Digest/1.0 (RSS Reader)"


def validate_config():
    """Validate that all required config values are set."""
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
