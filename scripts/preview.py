#!/usr/bin/env python3
"""Fetch-only preview — shows what articles were collected without running the LLM."""
import logging
import os


def _setup():
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dry-run")
    os.environ.setdefault("TELEGRAM_CHAT_ID", "dry-run")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for noisy in ("urllib3", "requests", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


if __name__ == "__main__":
    _setup()
    from ai_news_digest.app import build_daily_sample

    print("=" * 60)
    print("AI NEWS DAILY DIGEST — Fetch Preview")
    print("=" * 60)

    payload, text = build_daily_sample()

    print("\n" + text)
    print("\n" + "=" * 60)
    print(f"Articles: {len(payload.get('main_articles', []))} main + "
          f"{len(payload.get('research_articles', []))} research")
    print("=" * 60)
