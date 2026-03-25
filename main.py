#!/usr/bin/env python3
"""AI News Daily Digest — fetch, summarize, deliver to Telegram.

Entry point for hermes-agent. Exit 0 on success, exit 1 on failure.
Config comes from .env file.

Usage:
    python main.py
"""
import sys

from config import validate_config, logger
from fetcher import fetch_articles
from summarizer import summarize
from telegram_bot import send_digest


def main() -> int:
    """Run the full digest pipeline: fetch -> summarize -> deliver."""
    logger.info("Starting AI News Daily Digest...")

    # Validate config
    try:
        validate_config()
    except ValueError as e:
        logger.error(str(e))
        return 1

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

    # Deliver
    success = send_digest(summary)
    if not success:
        logger.error("Failed to deliver digest to Telegram")
        return 1

    logger.info("Digest delivered successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
