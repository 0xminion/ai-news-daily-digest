#!/usr/bin/env python3
"""AI News Daily Digest — fetch, summarize, deliver to Telegram.

Entry point for hermes-agent. Exit 0 on success, exit 1 on failure.
Config comes from .env file.

Usage:
    python main.py
"""
import sys

from config import get_llm_settings, validate_config, logger
from fetcher import fetch_articles
from summarizer import summarize
from storage import prune_old_reports, save_daily_report
from telegram_bot import _format_digest, send_digest


def main() -> int:
    """Run the full digest pipeline: fetch -> summarize -> deliver."""
    logger.info("Starting AI News Daily Digest...")

    # Validate config
    try:
        validate_config()
    except ValueError as e:
        logger.error(str(e))
        return 1

    # Check Ollama reachability only when Ollama is the active provider.
    llm = get_llm_settings()
    if llm["provider"] == "ollama":
        try:
            import requests
            from config import USER_AGENT
            resp = requests.get(
                f"{llm['ollama_host']}/api/tags",
                timeout=5,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code != 200:
                logger.warning(
                    "Ollama at %s returned status %s — summarization may fail.",
                    llm['ollama_host'], resp.status_code,
                )
        except Exception as e:
            logger.warning(
                "Cannot reach Ollama at %s (%s) — summarization will fail. "
                "Start Ollama: ollama serve",
                llm['ollama_host'], e,
            )

    # Fetch articles
    try:
        articles = fetch_articles()
        logger.info(f"Fetched {len(articles)} AI-relevant articles")
    except Exception as e:
        logger.error(f"Failed to fetch articles: {e}")
        return 1

    # Summarize
    try:
        summary = summarize(articles)
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return 1

    # Archive report copy and prune older ones before delivery
    try:
        prune_old_reports()
        save_daily_report(summary, articles, _format_digest(summary))
    except Exception as e:
        logger.warning(f"Failed to archive daily report copy: {e}")

    # Deliver
    success = send_digest(summary)
    if not success:
        logger.error("Failed to deliver digest to Telegram")
        return 1

    logger.info("Digest delivered successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
