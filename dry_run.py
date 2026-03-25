#!/usr/bin/env python3
"""Dry run — fetch real articles, summarize, print output. No Telegram needed."""
import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dry-run")
os.environ.setdefault("TELEGRAM_CHAT_ID", "dry-run")
os.environ.setdefault("OLLAMA_MODEL", "minimax-m2.7:cloud")

from config import logger
from fetcher import fetch_articles
from summarizer import summarize, OLLAMA_TIMEOUT
from telegram_bot import _format_digest
import summarizer

# Bump timeout for small model
summarizer.OLLAMA_TIMEOUT = 300

def main():
    print("=" * 60)
    print("DRY RUN — AI News Daily Digest")
    print("=" * 60)

    # Step 1: Fetch
    print("\n[1/3] Fetching articles from RSS feeds...\n")
    articles = fetch_articles()
    print(f"\nFound {len(articles)} AI-relevant articles:")
    for i, a in enumerate(articles, 1):
        print(f"  {i}. [{a['source']}] {a['title']}")
        print(f"     {a['url']}")

    # Step 2: Summarize
    print(f"\n{'=' * 60}")
    print("[2/3] Generating summary with Ollama (minimax-m2.7:cloud)...\n")
    summary = summarize(articles)

    print("--- RAW LLM OUTPUT ---")
    print(summary)
    print("--- END RAW OUTPUT ---")

    # Step 3: Format for Telegram
    print(f"\n{'=' * 60}")
    print("[3/3] Formatted Telegram message(s):\n")
    messages = _format_digest(summary)
    for i, msg in enumerate(messages, 1):
        print(f"--- MESSAGE {i}/{len(messages)} ({len(msg)} chars) ---")
        print(msg)
        print(f"--- END MESSAGE {i} ---\n")

    print(f"{'=' * 60}")
    print(f"Total articles fetched: {len(articles)}")
    print(f"Messages to send: {len(messages)}")
    print(f"Total chars: {sum(len(m) for m in messages)}")

if __name__ == "__main__":
    main()
