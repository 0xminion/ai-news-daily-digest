"""Config validation — extracted from old settings.py for cleaner imports."""
from __future__ import annotations

from urllib.parse import urlparse
import logging

from .yaml_loader import cfg_str, get_llm_settings, get_telegram_destinations

logger = logging.getLogger("ai-digest")


def validate_config(skip_telegram: bool = False) -> None:
    """Validate configuration. Raises ValueError on missing critical fields."""
    from .yaml_loader import get_config_value
    if not skip_telegram and cfg_str("delivery.output_mode") != "stdout":
        destinations = get_telegram_destinations()
        if not destinations:
            raise ValueError("Missing Telegram destination configuration. Set delivery.destinations or AI_DIGEST_ENV")
        missing_tokens = [dest["name"] for dest in destinations if not dest.get("bot_token")]
        if missing_tokens:
            raise ValueError(f"Missing bot token for destinations: {', '.join(missing_tokens)}")
    llm = get_llm_settings()
    provider_keys = {
        "openai": ("OPENAI_API_KEY", cfg_str("secrets.openai_api_key")),
        "openrouter": ("OPENROUTER_API_KEY", cfg_str("secrets.openrouter_api_key")),
        "anthropic": ("ANTHROPIC_API_KEY", cfg_str("secrets.anthropic_api_key")),
    }
    if llm["provider"] in provider_keys and not provider_keys[llm["provider"]][1]:
        raise ValueError(f"LLM provider '{llm['provider']}' requires {provider_keys[llm['provider']][0]}")
    # Validate feed URLs
    cfg = get_config_value("rss_feeds", default=[])
    for collection_name, feeds in (
        ("RSS_FEEDS", cfg),
    ):
        for item in feeds:
            if isinstance(item, dict):
                name = item.get("name", "")
                url = item.get("url", "")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                name, url = item[0], item[1]
            else:
                continue
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning("%s entry '%s' has invalid URL '%s'", collection_name, name, url)
